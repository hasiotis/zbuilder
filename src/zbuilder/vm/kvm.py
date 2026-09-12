"""KVM provider, driving libvirt.

Everything happens over a single libvirt connection: disks are storage pool
volumes, the cloud-init seed is uploaded through a libvirt stream. Nothing
touches the local filesystem or shells out, so a remote hypervisor reached
over `qemu+ssh://` works exactly like a local `qemu:///system`.
"""

import io
import re
import time
import atexit
import click
import jinja2
import libvirt
import pycdlib

import xml.etree.ElementTree as ET

from pathlib import Path
from zbuilder.base import VMProvider
from zbuilder.dns import dnsUpdate, dnsRemove
from zbuilder.ipam import ipamReserve, ipamRelease, ipamLocate


GiB = 1024 * 1024 * 1024
SNAPSHOT = "zbuilder"
DOMAIN_FILE_TMPL = "domain.xml.tmpl"

DESCRIPTION = "Created with zbuilder on {}"

IPAM_RE = re.compile(r"^ipam=(?P<subnet>.+)$")
STATIC_RE = re.compile(r"^ip=(?P<ip>[^/]+)/(?P<mask>\d+),gw=(?P<gw>.+)$")

#: The NoCloud files, as (iso9660 path, rock ridge name, joliet path)
SEED_FILES = {
    "user-data": ("/USERDATA.;1", "/user-data"),
    "meta-data": ("/METADATA.;1", "/meta-data"),
    "network-config": ("/NETWORKC.;1", "/network-config"),
}

DOMAIN_XML = """
<domain type='kvm'>
  <name>{{ name }}</name>
  <description>{{ description }}</description>
  <memory unit='KiB'>{{ memory * 1024 }}</memory>
  <currentMemory unit='KiB'>{{ memory * 1024 }}</currentMemory>
  <vcpu placement='static'>{{ vcpu }}</vcpu>
  <os>
    <type arch='{{ arch }}' machine='{{ machine }}'>hvm</type>
    <boot dev='hd'/>
  </os>
  <features>
    <acpi/>
    <apic/>
  </features>
  <cpu mode='{{ cpu }}'/>
  <clock offset='utc'>
    <timer name='rtc' tickpolicy='catchup'/>
    <timer name='pit' tickpolicy='delay'/>
    <timer name='hpet' present='no'/>
  </clock>
  <on_poweroff>destroy</on_poweroff>
  <on_reboot>restart</on_reboot>
  <on_crash>destroy</on_crash>
  <devices>
{% for disk in disks %}
    <disk type='file' device='disk'>
      <driver name='qemu' type='{{ disk.format }}'/>
      <source file='{{ disk.path }}'/>
      <target dev='{{ disk.target }}' bus='virtio'/>
    </disk>
{% endfor %}
{% if seed %}
    <disk type='file' device='cdrom'>
      <driver name='qemu' type='raw'/>
      <source file='{{ seed }}'/>
      <target dev='sda' bus='sata'/>
      <readonly/>
    </disk>
{% endif %}
    <interface type='{{ interface.type }}'>
      <source {{ interface.type }}='{{ interface.source }}'/>
      <model type='virtio'/>
    </interface>
    <channel type='unix'>
      <target type='virtio' name='org.qemu.guest_agent.0'/>
    </channel>
    <serial type='pty'>
      <target port='0'/>
    </serial>
    <console type='pty'>
      <target type='serial' port='0'/>
    </console>
    <graphics type='vnc' port='-1' autoport='yes' listen='127.0.0.1'/>
    <video>
      <model type='virtio'/>
    </video>
    <rng model='virtio'>
      <backend model='random'>/dev/urandom</backend>
    </rng>
  </devices>
</domain>
"""

VOLUME_XML = """
<volume>
  <name>{{ name }}</name>
  <capacity unit='B'>{{ capacity }}</capacity>
  <target>
    <format type='{{ format }}'/>
    <permissions>
      <mode>0644</mode>
    </permissions>
  </target>
{% if backing %}
  <backingStore>
    <path>{{ backing }}</path>
    <format type='{{ backingFormat }}'/>
  </backingStore>
{% endif %}
</volume>
"""


def _render(template, **context):
    return jinja2.Environment(loader=jinja2.BaseLoader(), trim_blocks=True).from_string(template).render(**context)


def _parseIpconfig(ipconfig):
    """Split a proxmox style ipconfig into (ip, mask, gw, subnet)

    Everything is None for a host without an ipconfig, which means DHCP. For an
    `ipam=<subnet>` config only the mask and the subnet are known here, the
    address and the gateway come from the IPAM provider.
    """
    if not ipconfig:
        return None, None, None, None

    m = IPAM_RE.match(ipconfig)
    if m:
        subnet = m.group("subnet")
        return None, subnet.partition("/")[2], None, subnet

    m = STATIC_RE.match(ipconfig)
    if not m:
        raise click.ClickException("Malformed ipconfig [{}]".format(ipconfig))

    return m.group("ip"), m.group("mask"), m.group("gw"), None


def _asList(value):
    """A yaml scalar, a space separated string or a list, as a list"""
    if value is None:
        return []
    if isinstance(value, (list, tuple)):
        return [str(i) for i in value]
    return str(value).split()


def _diskSizes(disks):
    """The extra disks of a host, as a list of sizes in GiB"""
    if disks is None:
        return []
    if isinstance(disks, (list, tuple)):
        return [int(d) for d in disks]
    return [int(disks)]


def _diskTarget(index):
    """The virtio device name of the `index`th disk"""
    return "vd{}".format(chr(ord("a") + index))


def _userData(host, opts):
    """The cloud-init user-data of a host"""
    user = opts.get("ZBUILDER_SYSUSER", "zbuilder")
    lines = [
        "#cloud-config",
        "hostname: {}".format(host.partition(".")[0]),
        "fqdn: {}".format(host),
        "preserve_hostname: false",
        "ssh_pwauth: false",
        "users:",
        "  - name: {}".format(user),
        "    sudo: 'ALL=(ALL) NOPASSWD:ALL'",
        "    shell: /bin/bash",
        "    lock_passwd: true",
    ]

    pubkey = _readPubkey(opts.get("ZBUILDER_PUBKEY"))
    if pubkey:
        lines += ["    ssh_authorized_keys:", "      - {}".format(pubkey)]

    return "\n".join(lines) + "\n"


def _readPubkey(fname):
    """The public key of the host, empty when there is none to read"""
    if not fname:
        return ""

    path = Path(fname).expanduser()
    if not path.is_file():
        return ""

    return path.read_text().rstrip("\n")


def _metaData(host, opts):
    """The cloud-init meta-data of a host"""
    return "instance-id: {}\nlocal-hostname: {}\n".format(host, host.partition(".")[0])


def _networkConfig(opts):
    """The cloud-init network-config of a host, netplan v2 flavoured

    Without an address the guest is left on DHCP. The interface is matched by
    glob rather than named, because the predictable name of the single virtio
    nic differs between cloud images.
    """
    lines = ["version: 2", "ethernets:", "  zbuilder0:", "    match:", "      name: '{}'".format(_ifaceMatch(opts))]

    if not opts.get("ip"):
        return "\n".join(lines + ["    dhcp4: true"]) + "\n"

    lines += [
        "    dhcp4: false",
        "    addresses:",
        "      - {}/{}".format(opts["ip"], opts.get("mask", 24)),
    ]
    if opts.get("gw"):
        lines += ["    routes:", "      - to: default", "        via: {}".format(opts["gw"])]

    nameservers = _asList(opts.get("nameserver"))
    search = _asList(opts.get("searchdomain"))
    if nameservers or search:
        lines += ["    nameservers:"]
        if nameservers:
            lines += ["      addresses: [{}]".format(", ".join(nameservers))]
        if search:
            lines += ["      search: [{}]".format(", ".join(search))]

    return "\n".join(lines) + "\n"


def _ifaceMatch(opts):
    """The glob the guest matches its nic with"""
    return opts.get("interface", "e*")


def _seedISO(host, opts):
    """The NoCloud seed of a host, as the bytes of an iso9660 image"""
    iso = pycdlib.PyCdlib()
    iso.new(interchange_level=3, joliet=3, rock_ridge="1.09", vol_ident="CIDATA")

    contents = {
        "user-data": _userData(host, opts),
        "meta-data": _metaData(host, opts),
        "network-config": _networkConfig(opts),
    }
    for name, (isoPath, jolietPath) in SEED_FILES.items():
        data = contents[name].encode()
        iso.add_fp(io.BytesIO(data), len(data), isoPath, rr_name=name, joliet_path=jolietPath)

    out = io.BytesIO()
    iso.write_fp(out)
    iso.close()

    return out.getvalue()


def _volumeXML(name, capacity, fmt="qcow2", backing=None, backingFormat="qcow2"):
    """The XML of a storage volume, optionally backed by a template volume"""
    return _render(
        VOLUME_XML, name=name, capacity=int(capacity), format=fmt, backing=backing, backingFormat=backingFormat
    )


def _domainTemplate():
    """The domain template, overridable by a domain.xml.tmpl in the cwd"""
    if Path(DOMAIN_FILE_TMPL).exists():
        return Path(DOMAIN_FILE_TMPL).read_text()

    return DOMAIN_XML


def _interface(opts, default="default"):
    """The nic of a host, either a libvirt network or a bridge"""
    network = opts.get("network") or default
    if network.startswith("bridge="):
        return {"type": "bridge", "source": network.partition("=")[2]}

    return {"type": "network", "source": network}


def _domainXML(host, opts, disks, seed=None, network="default"):
    """The XML of the domain of a host"""
    return _render(
        _domainTemplate(),
        name=host,
        description=DESCRIPTION.format(time.strftime("%c", time.localtime())),
        memory=int(opts.get("memory", 1024)),
        vcpu=int(opts.get("vcpu", opts.get("vcpus", 1))),
        arch=opts.get("arch", "x86_64"),
        machine=opts.get("machine", "q35"),
        cpu=opts.get("cpu", "host-passthrough"),
        disks=disks,
        seed=seed,
        interface=_interface(opts, network),
    )


def _diskPaths(xml):
    """The source files of every disk of a domain, from its XML"""
    return [source.get("file") for source in ET.fromstring(xml).findall("./devices/disk/source") if source.get("file")]


def _hasRawDisks(xml):
    """Whether a domain has a non qcow2 disk, which internal snapshots refuse"""
    for disk in ET.fromstring(xml).findall("./devices/disk"):
        if disk.get("device") != "disk":
            continue
        driver = disk.find("driver")
        if driver is not None and driver.get("type") != "qcow2":
            return True

    return False


class vmProvider(VMProvider):
    def __init__(self, cfg):
        super().__init__(cfg)
        self._conn = None
        self.uri = "qemu:///system"
        self.pool = "default"
        self.network = "default"
        self.timeout = 120
        if cfg:
            self.uri = cfg.get("uri", self.uri)
            self.pool = cfg.get("pool", self.pool)
            self.network = cfg.get("network", self.network)
            self.timeout = int(cfg.get("timeout", self.timeout))

    @property
    def conn(self):
        """The libvirt connection, opened on first use

        Lazily, so that constructing the provider stays cheap and a hypervisor
        that is down is reported by `status` instead of breaking every command.
        """
        if self._conn is None:
            # The bindings print every error to stderr before raising, which
            # turns an expected miss into noise.
            libvirt.registerErrorHandler(lambda ctx, err: None, None)
            try:
                self._conn = libvirt.open(self.uri)
            except libvirt.libvirtError as e:
                raise click.ClickException("Can't connect to [{}]: {}".format(self.uri, e))
            # virConnect.__del__ calls back into the libvirt module, which is
            # already torn down by the time the garbage collector runs at
            # interpreter shutdown ("'NoneType' object is not callable").
            # Close it while the interpreter is still alive.
            atexit.register(self.close)

        return self._conn

    def close(self):
        """Close the libvirt connection, if one was ever opened"""
        conn, self._conn = self._conn, None
        if conn is not None:
            try:
                conn.close()
            except libvirt.libvirtError:
                pass

    def _states(self):
        return {
            libvirt.VIR_DOMAIN_RUNNING: "running",
            libvirt.VIR_DOMAIN_BLOCKED: "blocked",
            libvirt.VIR_DOMAIN_PAUSED: "paused",
            libvirt.VIR_DOMAIN_SHUTDOWN: "shutdown",
            libvirt.VIR_DOMAIN_SHUTOFF: "stopped",
            libvirt.VIR_DOMAIN_CRASHED: "crashed",
            libvirt.VIR_DOMAIN_PMSUSPENDED: "suspended",
        }

    def _domains(self):
        """Every domain of the hypervisor, by name"""
        return {d.name(): d for d in self.conn.listAllDomains()}

    def _state(self, dom):
        return self._states().get(dom.state()[0], "unknown")

    def _getPool(self, opts):
        name = opts.get("pool", self.pool)
        try:
            return self.conn.storagePoolLookupByName(name)
        except libvirt.libvirtError as e:
            raise click.ClickException("No such storage pool [{}]: {}".format(name, e))

    def _getVolume(self, pool, name):
        if not name:
            return None
        try:
            return pool.storageVolLookupByName(name)
        except libvirt.libvirtError:
            return None

    def _getVMs(self, hosts, domains=None):
        """The enabled hosts, with their addresses and the state of their domain

        Callers that need the domain objects themselves pass the index in, so
        the hypervisor is listed once per command rather than twice.
        """
        domains = self._domains() if domains is None else domains
        retValue = {}
        for h, v in hosts.items():
            if not hosts[h]["enabled"]:
                continue

            ip, mask, gw, subnet = _parseIpconfig(v.get("ipconfig"))
            if subnet:
                located = ipamLocate(h, subnet)
                if located:
                    ip, gw = located

            v["ip"] = ip
            v["mask"] = mask
            v["gw"] = gw
            v["subnet"] = subnet
            v["status"] = self._state(domains[h]) if h in domains else None
            retValue[h] = v

        return retValue

    def _createVolume(self, pool, name, capacity, fmt="qcow2", backing=None, clone=None):
        """Create a volume, either empty, backed by, or a full copy of `clone`"""
        xml = _volumeXML(name, capacity, fmt=fmt, backing=backing)
        if clone is not None:
            return pool.createXMLFrom(xml, clone, 0)

        return pool.createXML(xml, 0)

    def _createDisks(self, pool, host, opts, template):
        """The root volume of a host, cloned from its template, plus the extra ones"""
        capacity = int(opts["size"]) * GiB if opts.get("size") else template.info()[1]
        if opts.get("full") is True:
            root = self._createVolume(pool, "{}.qcow2".format(host), capacity, clone=template)
            # A full clone comes out at the capacity of the template: libvirt
            # copies the source volume and ignores the one in the XML, so
            # `size` only takes effect through a resize afterwards.
            if root.info()[1] < capacity:
                root.resize(capacity)
        else:
            root = self._createVolume(pool, "{}.qcow2".format(host), capacity, backing=template.path())

        volumes = [root]
        for i, size in enumerate(_diskSizes(opts.get("disks"))):
            volumes.append(self._createVolume(pool, "{}-disk{}.qcow2".format(host, i + 1), size * GiB))

        return volumes

    def _createSeed(self, pool, host, opts):
        """Upload the cloud-init seed of a host as a volume of the pool"""
        iso = _seedISO(host, opts)
        vol = self._createVolume(pool, "{}-seed.iso".format(host), len(iso), fmt="raw")

        stream = self.conn.newStream(0)
        vol.upload(stream, 0, len(iso))
        try:
            stream.sendAll(lambda s, nbytes, fp: fp.read(nbytes), io.BytesIO(iso))
            stream.finish()
        except libvirt.libvirtError:
            stream.abort()
            raise

        return vol

    def _deleteVolumes(self, volumes):
        """Delete volumes, tolerating the ones already gone"""
        for vol in volumes:
            try:
                vol.delete(0)
            except libvirt.libvirtError:
                pass

    def _findIP(self, dom):
        """The address of a running domain, from its lease or its guest agent"""
        for source in (
            libvirt.VIR_DOMAIN_INTERFACE_ADDRESSES_SRC_LEASE,
            libvirt.VIR_DOMAIN_INTERFACE_ADDRESSES_SRC_AGENT,
        ):
            try:
                interfaces = dom.interfaceAddresses(source)
            except libvirt.libvirtError:
                continue

            for iface in interfaces.values():
                for addr in iface.get("addrs") or []:
                    if addr["type"] == libvirt.VIR_IP_ADDR_TYPE_IPV4 and not addr["addr"].startswith("127."):
                        return addr["addr"]

        return None

    def _waitIP(self, dom):
        """Wait for a DHCP host to pick up an address"""
        click.echo("    Waiting for an address")
        deadline = time.time() + self.timeout
        while time.time() < deadline:
            ip = self._findIP(dom)
            if ip:
                return ip
            time.sleep(5)

        click.secho("    No address found for [{}]".format(dom.name()), fg="yellow")
        return None

    def _waitShutoff(self, dom):
        """Wait for an ACPI shutdown, and pull the plug when it does not come"""
        deadline = time.time() + self.timeout
        while time.time() < deadline:
            if dom.state()[0] == libvirt.VIR_DOMAIN_SHUTOFF:
                return True
            time.sleep(2)

        click.secho("    Shutdown timed out, stopping [{}]".format(dom.name()), fg="yellow")
        dom.destroy()
        return False

    def _snapshot(self, dom):
        try:
            return dom.snapshotLookupByName(SNAPSHOT)
        except libvirt.libvirtError:
            return None

    def build(self, hosts):
        ips = {}
        domains = self._domains()
        for h, v in self._getVMs(hosts, domains).items():
            if v["status"]:
                click.echo("  - Status of host: {} is {}".format(h, v["status"]))
                ip = v["ip"] or self._findIP(domains[h])
                if ip:
                    ips[h] = ip
                continue

            click.echo("  - Creating host: {} ".format(h))
            pool = self._getPool(v)
            template = self._getVolume(pool, v.get("template"))
            if template is None:
                click.secho("    No such template: [{}] in pool [{}]".format(v.get("template"), pool.name()), fg="red")
                continue

            if v["subnet"]:
                reserved = ipamReserve(h, v["subnet"])
                if not reserved:
                    click.secho("    Could not reserve an address in [{}]".format(v["subnet"]), fg="red")
                    continue
                v["ip"], v["gw"] = reserved

            volumes = []
            try:
                volumes = self._createDisks(pool, h, v, template)
                seed = self._createSeed(pool, h, v)
                volumes.append(seed)

                disks = [
                    {"path": vol.path(), "target": _diskTarget(i), "format": "qcow2"}
                    for i, vol in enumerate(volumes[:-1])
                ]
                dom = self.conn.defineXML(_domainXML(h, v, disks, seed=seed.path(), network=self.network))
                dom.create()
            except libvirt.libvirtError as e:
                # Undefining without deleting leaves the volumes behind, and
                # the next build then collides with them.
                click.secho("    Failed: {}".format(e), fg="red")
                self._deleteVolumes(volumes)
                if v["subnet"] and v["ip"]:
                    ipamRelease(h, v["ip"], v["subnet"])
                continue

            ip = v["ip"] or self._waitIP(dom)
            if ip:
                ips[h] = ip

        dnsUpdate(ips)

    def up(self, hosts):
        domains = self._domains()
        for h, v in self._getVMs(hosts, domains).items():
            if not v["status"]:
                click.echo("  - Host does not exists [{}]".format(h))
                continue

            click.echo("  - Starting host: {} ".format(h))
            if v["status"] == "stopped":
                try:
                    domains[h].create()
                except libvirt.libvirtError as e:
                    click.secho("    Failed: {}".format(e), fg="red")

    def halt(self, hosts):
        domains = self._domains()
        for h, v in self._getVMs(hosts, domains).items():
            if not v["status"]:
                click.echo("  - Host does not exists [{}]".format(h))
                continue

            click.echo("  - Halting host: {} ".format(h))
            if v["status"] == "running":
                try:
                    domains[h].shutdown()
                    self._waitShutoff(domains[h])
                except libvirt.libvirtError as e:
                    click.secho("    Failed: {}".format(e), fg="red")

    def destroy(self, hosts):
        updateHosts = {}
        domains = self._domains()
        for h, v in self._getVMs(hosts, domains).items():
            if not v["status"]:
                click.echo("  - Host does not exists [{}]".format(h))
                continue

            click.echo("  - Destroying host: {} ".format(h))
            updateHosts[h] = {}
            dom = domains[h]
            try:
                # The disks are read off the domain before it goes away, so
                # they are deleted even when they were not named by us.
                volumes = []
                for path in _diskPaths(dom.XMLDesc()):
                    try:
                        volumes.append(self.conn.storageVolLookupByPath(path))
                    except libvirt.libvirtError:
                        pass

                if v["status"] != "stopped":
                    dom.destroy()

                dom.undefineFlags(
                    libvirt.VIR_DOMAIN_UNDEFINE_MANAGED_SAVE
                    | libvirt.VIR_DOMAIN_UNDEFINE_SNAPSHOTS_METADATA
                    | libvirt.VIR_DOMAIN_UNDEFINE_NVRAM
                )
                self._deleteVolumes(volumes)
            except libvirt.libvirtError as e:
                click.secho("    Failed: {}".format(e), fg="red")
                continue

            if v["subnet"] and v["ip"]:
                ipamRelease(h, v["ip"], v["subnet"])

        dnsRemove(updateHosts)

    def dnsupdate(self, hosts):
        ips = {}
        domains = self._domains()
        for h, v in self._getVMs(hosts, domains).items():
            ip = v["ip"] or (self._findIP(domains[h]) if h in domains else None)
            if ip:
                ips[h] = ip
        dnsUpdate(ips)

    def dnsremove(self, hosts):
        ips = {}
        for h in hosts:
            if hosts[h]["enabled"]:
                ips[h] = None
        dnsRemove(ips)

    def snapCreate(self, hosts):
        domains = self._domains()
        for h, v in self._getVMs(hosts, domains).items():
            if not v["status"]:
                click.echo("  - Host does not exists [{}]".format(h))
                continue

            dom = domains[h]
            if _hasRawDisks(dom.XMLDesc()):
                click.secho("  - Host [{}] has a raw disk, internal snapshots need qcow2".format(h), fg="red")
                continue

            snapshot = self._snapshot(dom)
            if snapshot:
                click.echo("  - Deleting snapshot for vm: {} ".format(h))
                try:
                    snapshot.delete()
                except libvirt.libvirtError as e:
                    click.secho("    Failed: {}".format(e), fg="red")
                    continue

            click.echo("  - Creating snapshot for vm: {} ".format(h))
            xml = "<domainsnapshot><name>{}</name><description>Managed by zbuilder</description></domainsnapshot>"
            try:
                dom.snapshotCreateXML(xml.format(SNAPSHOT), 0)
            except libvirt.libvirtError as e:
                click.secho("    Failed: {}".format(e), fg="red")

    def snapRestore(self, hosts):
        domains = self._domains()
        for h, v in self._getVMs(hosts, domains).items():
            if not v["status"]:
                click.echo("  - Host does not exists [{}]".format(h))
                continue

            dom = domains[h]
            snapshot = self._snapshot(dom)
            if not snapshot:
                click.echo("  - No [{}] snapshot for vm: {}".format(SNAPSHOT, h))
                continue

            click.echo("  - Restoring snapshot for vm: {} ".format(h))
            try:
                dom.revertToSnapshot(snapshot, 0)
                if dom.state()[0] == libvirt.VIR_DOMAIN_SHUTOFF:
                    dom.create()
            except libvirt.libvirtError as e:
                click.secho("    Failed: {}".format(e), fg="red")

    def snapDelete(self, hosts):
        domains = self._domains()
        for h, v in self._getVMs(hosts, domains).items():
            if not v["status"]:
                click.echo("  - Host does not exists [{}]".format(h))
                continue

            snapshot = self._snapshot(domains[h])
            if not snapshot:
                continue

            click.echo("  - Deleting snapshot for vm: {} ".format(h))
            try:
                snapshot.delete()
            except libvirt.libvirtError as e:
                click.secho("    Failed: {}".format(e), fg="red")

    def config(self):
        return "uri: {}, pool: {}, network: {}".format(self.uri, self.pool, self.network)

    def status(self):
        try:
            self.conn.getVersion()
        except click.ClickException as e:
            return e.message
        except Exception as e:
            return str(e)

        return "PASS"

    def params(self, params):
        return {k: params.get(k, None) for k in ["pool", "template", "vcpu", "memory", "ipconfig", "disks"]}
