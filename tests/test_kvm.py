"""Unit tests of the kvm provider.

Everything here runs against the pure helpers, so no hypervisor and no libvirt
bindings are needed - which is also what keeps the provider importable, and
therefore discoverable, on a machine without the kvm extra.
"""

import io
import click
import pytest

import xml.etree.ElementTree as ET

from zbuilder.vm import kvm


def domain(host="host01.zbuilder.local", opts=None, disks=None, **kwargs):
    """The domain XML of a host, parsed"""
    opts = {"memory": 2048, "vcpu": 2} if opts is None else opts
    disks = [{"path": "/pool/root.qcow2", "target": "vda", "format": "qcow2"}] if disks is None else disks

    return ET.fromstring(kvm._domainXML(host, opts, disks, **kwargs))


def test_ipconfig_is_parsed_the_way_proxmox_writes_it():
    assert kvm._parseIpconfig("ip=10.0.0.10/24,gw=10.0.0.1") == ("10.0.0.10", "24", "10.0.0.1", None)


def test_an_ipam_ipconfig_only_yields_the_subnet():
    """The address and the gateway are the IPAM's to hand out, not ours"""
    assert kvm._parseIpconfig("ipam=10.0.0.0/24") == (None, "24", None, "10.0.0.0/24")


@pytest.mark.parametrize("ipconfig", [None, ""])
def test_no_ipconfig_means_dhcp(ipconfig):
    assert kvm._parseIpconfig(ipconfig) == (None, None, None, None)


def test_a_malformed_ipconfig_is_reported():
    with pytest.raises(click.ClickException) as excinfo:
        kvm._parseIpconfig("10.0.0.10")

    assert "10.0.0.10" in str(excinfo.value)


@pytest.mark.parametrize(
    "disks, expected",
    [(None, []), (10, [10]), ([10, 50], [10, 50]), (["10"], [10])],
)
def test_disks_are_accepted_as_a_scalar_or_a_list(disks, expected):
    assert kvm._diskSizes(disks) == expected


def test_disk_targets_follow_the_virtio_naming():
    assert [kvm._diskTarget(i) for i in range(3)] == ["vda", "vdb", "vdc"]


def test_user_data_carries_the_sysuser_and_its_key(tmp_path):
    pubkey = tmp_path / "id_rsa.pub"
    pubkey.write_text("ssh-ed25519 AAAAC3NzaC1 zbuilder\n")

    userData = kvm._userData(
        "host01.zbuilder.local",
        {"ZBUILDER_SYSUSER": "sysadmin", "ZBUILDER_PUBKEY": str(pubkey)},
    )

    assert userData.startswith("#cloud-config\n")
    assert "name: sysadmin" in userData
    assert "ssh-ed25519 AAAAC3NzaC1 zbuilder" in userData
    assert "hostname: host01" in userData
    assert "fqdn: host01.zbuilder.local" in userData


def test_a_missing_pubkey_is_not_fatal():
    userData = kvm._userData("host01.zbuilder.local", {"ZBUILDER_PUBKEY": "/no/such/key.pub"})

    assert "ssh_authorized_keys" not in userData


def test_network_config_is_static_when_there_is_an_address():
    networkConfig = kvm._networkConfig(
        {
            "ip": "10.0.0.10",
            "mask": "24",
            "gw": "10.0.0.1",
            "nameserver": "10.0.0.1 10.0.0.2",
            "searchdomain": "zbuilder.local",
        }
    )

    assert "dhcp4: false" in networkConfig
    assert "- 10.0.0.10/24" in networkConfig
    assert "via: 10.0.0.1" in networkConfig
    assert "addresses: [10.0.0.1, 10.0.0.2]" in networkConfig
    assert "search: [zbuilder.local]" in networkConfig


def test_network_config_falls_back_to_dhcp():
    networkConfig = kvm._networkConfig({})

    assert "dhcp4: true" in networkConfig
    assert "addresses" not in networkConfig


def test_seed_is_a_nocloud_iso():
    pytest.importorskip("pycdlib")
    import pycdlib

    iso = kvm._seedISO("host01.zbuilder.local", {"ZBUILDER_SYSUSER": "sysadmin"})

    image = pycdlib.PyCdlib()
    image.open_fp(io.BytesIO(iso))
    # cloud-init finds a NoCloud seed by the CIDATA label, and reads the three
    # files by their lower case names, which the iso9660 tree cannot hold - so
    # they have to be reachable through both joliet and rock ridge.
    assert image.pvd.volume_identifier.decode().strip() == "CIDATA"

    for name in ("user-data", "meta-data", "network-config"):
        joliet, rockRidge = io.BytesIO(), io.BytesIO()
        image.get_file_from_iso_fp(joliet, joliet_path="/{}".format(name))
        image.get_file_from_iso_fp(rockRidge, rr_path="/{}".format(name))
        assert joliet.getvalue() == rockRidge.getvalue()
        assert joliet.getvalue()

    userData = io.BytesIO()
    image.get_file_from_iso_fp(userData, joliet_path="/user-data")
    assert b"name: sysadmin" in userData.getvalue()

    image.close()


def test_domain_has_the_memory_and_cpus_of_the_host():
    dom = domain(opts={"memory": 2048, "vcpu": 4})

    assert dom.findtext("name") == "host01.zbuilder.local"
    assert dom.find("memory").get("unit") == "KiB"
    assert dom.findtext("memory") == "2097152"
    assert dom.findtext("vcpu") == "4"


def test_domain_accepts_the_vagrant_spelling_of_vcpus():
    assert domain(opts={"memory": 512, "vcpus": 2}).findtext("vcpu") == "2"


def test_domain_has_one_virtio_disk_per_volume():
    disks = [
        {"path": "/pool/root.qcow2", "target": "vda", "format": "qcow2"},
        {"path": "/pool/data.qcow2", "target": "vdb", "format": "qcow2"},
    ]
    dom = domain(disks=disks)

    targets = [d.find("target").get("dev") for d in dom.findall("./devices/disk[@device='disk']")]
    assert targets == ["vda", "vdb"]
    assert all(d.find("target").get("bus") == "virtio" for d in dom.findall("./devices/disk[@device='disk']"))


def test_the_seed_is_attached_as_a_cdrom():
    dom = domain(seed="/pool/host01-seed.iso")

    cdrom = dom.find("./devices/disk[@device='cdrom']")
    assert cdrom.find("source").get("file") == "/pool/host01-seed.iso"
    assert cdrom.find("driver").get("type") == "raw"


def test_a_host_without_a_seed_has_no_cdrom():
    assert domain().find("./devices/disk[@device='cdrom']") is None


def test_the_nic_is_a_libvirt_network_by_default():
    interface = domain().find("./devices/interface")

    assert interface.get("type") == "network"
    assert interface.find("source").get("network") == "default"


def test_the_nic_can_be_a_bridge():
    interface = domain(opts={"memory": 512, "vcpu": 1, "network": "bridge=br0"}).find("./devices/interface")

    assert interface.get("type") == "bridge"
    assert interface.find("source").get("bridge") == "br0"


def test_the_guest_agent_channel_is_wired():
    """Without it there is no address for a DHCP host on a bridged network"""
    channel = domain().find("./devices/channel/target")

    assert channel.get("name") == "org.qemu.guest_agent.0"


def test_the_domain_template_is_overridable(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    (tmp_path / kvm.DOMAIN_FILE_TMPL).write_text("<domain><name>{{ name }}</name></domain>")

    assert domain(host="custom").findtext("name") == "custom"


def test_volume_xml_backs_onto_the_template():
    vol = ET.fromstring(kvm._volumeXML("host01.qcow2", 20 * kvm.GiB, backing="/pool/base.qcow2"))

    assert vol.findtext("name") == "host01.qcow2"
    assert vol.findtext("capacity") == str(20 * kvm.GiB)
    assert vol.find("./target/format").get("type") == "qcow2"
    assert vol.findtext("./backingStore/path") == "/pool/base.qcow2"


def test_volume_xml_without_a_backing_store():
    vol = ET.fromstring(kvm._volumeXML("host01-seed.iso", 366592, fmt="raw"))

    assert vol.find("backingStore") is None
    assert vol.find("./target/format").get("type") == "raw"


def test_disks_of_a_domain_are_read_back_from_its_xml():
    """Destroy deletes what the domain actually points at, not what we named"""
    xml = kvm._domainXML(
        "host01",
        {"memory": 512, "vcpu": 1},
        [{"path": "/pool/root.qcow2", "target": "vda", "format": "qcow2"}],
        seed="/pool/host01-seed.iso",
    )

    assert kvm._diskPaths(xml) == ["/pool/root.qcow2", "/pool/host01-seed.iso"]


def test_raw_disks_are_detected():
    raw = kvm._domainXML("host01", {}, [{"path": "/pool/root.raw", "target": "vda", "format": "raw"}])
    qcow2 = kvm._domainXML("host01", {}, [{"path": "/pool/root.qcow2", "target": "vda", "format": "qcow2"}])

    assert kvm._hasRawDisks(raw)
    # The seed cdrom is raw by definition, and must not count as a raw disk
    assert not kvm._hasRawDisks(qcow2)
    assert not kvm._hasRawDisks(
        kvm._domainXML(
            "host01",
            {},
            [{"path": "/pool/root.qcow2", "target": "vda", "format": "qcow2"}],
            seed="/pool/seed.iso",
        )
    )


def test_provider_defaults_and_config():
    provider = kvm.vmProvider({"uri": "qemu+ssh://root@hyper01/system"})

    assert provider.uri == "qemu+ssh://root@hyper01/system"
    assert provider.pool == "default"
    assert "qemu+ssh://root@hyper01/system" in provider.config()


def test_params_tolerates_a_host_that_omits_them():
    assert kvm.vmProvider({}).params({"memory": 2048}) == {
        "pool": None,
        "template": None,
        "vcpu": None,
        "memory": 2048,
        "ipconfig": None,
        "disks": None,
    }


def test_a_missing_extra_is_reported_as_an_install_hint(monkeypatch):
    monkeypatch.setattr(kvm, "libvirt", None)

    assert "zbuilder[kvm]" in kvm.vmProvider({}).status()
    # ... and `zbuilder plugins` does not offer a provider that cannot run
    assert kvm.vmProvider({}).enabled() is False


class libvirtError(Exception):
    pass


class FakeLibvirt:
    """Just enough of the bindings to exercise the flow of the provider"""

    libvirtError = libvirtError

    VIR_DOMAIN_RUNNING = 1
    VIR_DOMAIN_BLOCKED = 2
    VIR_DOMAIN_PAUSED = 3
    VIR_DOMAIN_SHUTDOWN = 4
    VIR_DOMAIN_SHUTOFF = 5
    VIR_DOMAIN_CRASHED = 6
    VIR_DOMAIN_PMSUSPENDED = 7

    VIR_DOMAIN_UNDEFINE_MANAGED_SAVE = 1
    VIR_DOMAIN_UNDEFINE_SNAPSHOTS_METADATA = 2
    VIR_DOMAIN_UNDEFINE_NVRAM = 4

    VIR_DOMAIN_INTERFACE_ADDRESSES_SRC_LEASE = 0
    VIR_DOMAIN_INTERFACE_ADDRESSES_SRC_AGENT = 1
    VIR_IP_ADDR_TYPE_IPV4 = 0

    def __init__(self, conn):
        self.conn = conn

    def registerErrorHandler(self, handler, ctx):
        pass

    def open(self, uri):
        return self.conn


class FakeVolume:
    def __init__(self, name, capacity=10 * kvm.GiB, xml=None):
        self._name = name
        self.capacity = capacity
        self.xml = xml
        self.deleted = False
        self.uploaded = None
        self.clonedFrom = None

    def name(self):
        return self._name

    def path(self):
        return "/pool/{}".format(self._name)

    def info(self):
        return [0, self.capacity, self.capacity]

    def delete(self, flags=0):
        self.deleted = True

    def resize(self, capacity, flags=0):
        self.capacity = capacity

    def upload(self, stream, offset, length, flags=0):
        stream.volume = self


class FakeStream:
    def __init__(self):
        self.volume = None
        self.finished = False

    def sendAll(self, handler, opaque):
        chunks = []
        while True:
            chunk = handler(self, 64 * 1024, opaque)
            if not chunk:
                break
            chunks.append(chunk)
        if self.volume is not None:
            self.volume.uploaded = b"".join(chunks)

    def finish(self):
        self.finished = True

    def abort(self):
        pass


class FakePool:
    def __init__(self, name="default", volumes=()):
        self._name = name
        self.volumes = {v: FakeVolume(v) for v in volumes}

    def name(self):
        return self._name

    def storageVolLookupByName(self, name):
        if name not in self.volumes:
            raise libvirtError("no such volume [{}]".format(name))
        return self.volumes[name]

    def createXML(self, xml, flags=0):
        volume = ET.fromstring(xml)
        vol = FakeVolume(volume.findtext("name"), int(volume.findtext("capacity")), xml=xml)
        self.volumes[vol.name()] = vol
        return vol

    def createXMLFrom(self, xml, clone, flags=0):
        vol = self.createXML(xml)
        vol.clonedFrom = clone
        # libvirt copies the capacity of the source and ignores the xml
        vol.capacity = clone.capacity
        return vol


class FakeDomain:
    def __init__(self, name, xml="", state=FakeLibvirt.VIR_DOMAIN_SHUTOFF, addresses=None):
        self._name = name
        self.xml = xml
        self._state = state
        self.addresses = addresses or {}
        self.undefined = None
        self.snapshots = {}

    def name(self):
        return self._name

    def state(self):
        return [self._state, 0]

    def create(self):
        self._state = FakeLibvirt.VIR_DOMAIN_RUNNING

    def shutdown(self):
        self._state = FakeLibvirt.VIR_DOMAIN_SHUTOFF

    def destroy(self):
        self._state = FakeLibvirt.VIR_DOMAIN_SHUTOFF

    def undefineFlags(self, flags):
        self.undefined = flags

    def XMLDesc(self, flags=0):
        return self.xml

    def interfaceAddresses(self, source, flags=0):
        return self.addresses

    def snapshotLookupByName(self, name, flags=0):
        if name not in self.snapshots:
            raise libvirtError("no such snapshot")
        return self.snapshots[name]

    def snapshotCreateXML(self, xml, flags=0):
        name = ET.fromstring(xml).findtext("name")
        self.snapshots[name] = FakeSnapshot(name, self)
        return self.snapshots[name]

    def revertToSnapshot(self, snapshot, flags=0):
        self.reverted = snapshot


class FakeSnapshot:
    def __init__(self, name, dom):
        self._name = name
        self.dom = dom

    def delete(self, flags=0):
        del self.dom.snapshots[self._name]


class FakeConn:
    def __init__(self, pool=None, domains=()):
        self.pool = pool if pool is not None else FakePool()
        self.domains = {d.name(): d for d in domains}
        self.defineFails = False

    def listAllDomains(self, flags=0):
        return list(self.domains.values())

    def storagePoolLookupByName(self, name):
        return self.pool

    def storageVolLookupByPath(self, path):
        for vol in self.pool.volumes.values():
            if vol.path() == path:
                return vol
        raise libvirtError("no volume at [{}]".format(path))

    def defineXML(self, xml):
        if self.defineFails:
            raise libvirtError("boom")
        dom = FakeDomain(ET.fromstring(xml).findtext("name"), xml=xml)
        self.domains[dom.name()] = dom
        return dom

    def newStream(self, flags=0):
        return FakeStream()

    def getVersion(self):
        return 11000000


@pytest.fixture
def hypervisor(monkeypatch):
    """A provider wired to a fake hypervisor, with the DNS calls captured"""
    conn = FakeConn(pool=FakePool(volumes=["debian-13-base.qcow2"]))
    monkeypatch.setattr(kvm, "libvirt", FakeLibvirt(conn))

    dns = {"updated": None, "removed": None}
    monkeypatch.setattr(kvm, "dnsUpdate", lambda ips: dns.update(updated=ips))
    monkeypatch.setattr(kvm, "dnsRemove", lambda hosts: dns.update(removed=hosts))

    return kvm.vmProvider({"uri": "qemu:///system"}), conn, dns


def hostVars(**overrides):
    opts = {
        "enabled": True,
        "template": "debian-13-base.qcow2",
        "memory": 2048,
        "vcpu": 2,
        "ipconfig": "ip=10.0.0.10/24,gw=10.0.0.1",
        "ZBUILDER_SYSUSER": "sysadmin",
    }
    opts.update(overrides)
    return opts


def test_build_creates_the_disks_the_seed_and_a_running_domain(hypervisor):
    provider, conn, dns = hypervisor

    provider.build({"host01.zbuilder.local": hostVars(disks=[50])})

    root = conn.pool.volumes["host01.zbuilder.local.qcow2"]
    extra = conn.pool.volumes["host01.zbuilder.local-disk1.qcow2"]
    seed = conn.pool.volumes["host01.zbuilder.local-seed.iso"]

    assert ET.fromstring(root.xml).findtext("./backingStore/path") == "/pool/debian-13-base.qcow2"
    assert extra.capacity == 50 * kvm.GiB
    assert seed.uploaded.startswith(b"\x00")  # an iso9660 image, uploaded whole
    assert len(seed.uploaded) == seed.capacity

    dom = conn.domains["host01.zbuilder.local"]
    assert dom.state()[0] == FakeLibvirt.VIR_DOMAIN_RUNNING
    assert dns["updated"] == {"host01.zbuilder.local": "10.0.0.10"}


def test_a_thin_clone_is_created_at_the_requested_size(hypervisor):
    provider, conn, dns = hypervisor

    provider.build({"host01.zbuilder.local": hostVars(size=20)})

    assert conn.pool.volumes["host01.zbuilder.local.qcow2"].capacity == 20 * kvm.GiB


def test_a_full_clone_is_resized_to_the_requested_size(hypervisor):
    """createXMLFrom hands back a copy at the template's capacity, not ours"""
    provider, conn, dns = hypervisor

    provider.build({"host01.zbuilder.local": hostVars(size=20, full=True)})

    root = conn.pool.volumes["host01.zbuilder.local.qcow2"]
    assert root.clonedFrom is conn.pool.volumes["debian-13-base.qcow2"]
    assert root.capacity == 20 * kvm.GiB


def test_a_host_without_a_size_inherits_the_template(hypervisor):
    provider, conn, dns = hypervisor
    conn.pool.volumes["debian-13-base.qcow2"].capacity = 3 * kvm.GiB

    provider.build({"host01.zbuilder.local": hostVars()})

    assert conn.pool.volumes["host01.zbuilder.local.qcow2"].capacity == 3 * kvm.GiB


def test_build_leaves_limited_out_hosts_alone(hypervisor):
    """getHosts returns every host, the limit only flips `enabled`"""
    provider, conn, dns = hypervisor

    provider.build({"host01.zbuilder.local": hostVars(enabled=False)})

    assert conn.domains == {}
    assert dns["updated"] == {}


def test_build_deletes_the_volumes_it_made_when_the_domain_fails(hypervisor):
    """Undefining without deleting would leave the next build colliding"""
    provider, conn, dns = hypervisor
    conn.defineFails = True

    provider.build({"host01.zbuilder.local": hostVars(disks=[50])})

    assert conn.domains == {}
    made = [v for name, v in conn.pool.volumes.items() if name.startswith("host01")]
    assert len(made) == 3
    assert all(v.deleted for v in made)


def test_build_reports_a_missing_template(hypervisor, capsys):
    provider, conn, dns = hypervisor

    provider.build({"host01.zbuilder.local": hostVars(template="nosuch.qcow2")})

    assert "nosuch.qcow2" in capsys.readouterr().out
    assert conn.domains == {}


def test_build_leaves_an_existing_host_as_it_is(hypervisor):
    provider, conn, dns = hypervisor
    conn.domains["host01.zbuilder.local"] = FakeDomain("host01.zbuilder.local", state=FakeLibvirt.VIR_DOMAIN_RUNNING)

    provider.build({"host01.zbuilder.local": hostVars()})

    assert "host01.zbuilder.local.qcow2" not in conn.pool.volumes
    assert dns["updated"] == {"host01.zbuilder.local": "10.0.0.10"}


def test_a_dhcp_host_gets_its_address_from_the_lease(hypervisor):
    provider, conn, dns = hypervisor
    conn.domains["host01.zbuilder.local"] = FakeDomain(
        "host01.zbuilder.local",
        state=FakeLibvirt.VIR_DOMAIN_RUNNING,
        addresses={"vnet0": {"addrs": [{"type": FakeLibvirt.VIR_IP_ADDR_TYPE_IPV4, "addr": "10.0.0.77"}]}},
    )

    provider.dnsupdate({"host01.zbuilder.local": hostVars(ipconfig=None)})

    assert dns["updated"] == {"host01.zbuilder.local": "10.0.0.77"}


def test_up_starts_a_stopped_host(hypervisor):
    provider, conn, dns = hypervisor
    dom = FakeDomain("host01.zbuilder.local", state=FakeLibvirt.VIR_DOMAIN_SHUTOFF)
    conn.domains[dom.name()] = dom

    provider.up({"host01.zbuilder.local": hostVars()})

    assert dom.state()[0] == FakeLibvirt.VIR_DOMAIN_RUNNING


def test_halt_shuts_a_running_host_down(hypervisor):
    provider, conn, dns = hypervisor
    dom = FakeDomain("host01.zbuilder.local", state=FakeLibvirt.VIR_DOMAIN_RUNNING)
    conn.domains[dom.name()] = dom

    provider.halt({"host01.zbuilder.local": hostVars()})

    assert dom.state()[0] == FakeLibvirt.VIR_DOMAIN_SHUTOFF


def test_destroy_deletes_the_disks_the_domain_points_at(hypervisor):
    provider, conn, dns = hypervisor
    provider.build({"host01.zbuilder.local": hostVars(disks=[50])})

    provider.destroy({"host01.zbuilder.local": hostVars(disks=[50])})

    dom = conn.domains["host01.zbuilder.local"]
    assert dom.undefined == (
        FakeLibvirt.VIR_DOMAIN_UNDEFINE_MANAGED_SAVE
        | FakeLibvirt.VIR_DOMAIN_UNDEFINE_SNAPSHOTS_METADATA
        | FakeLibvirt.VIR_DOMAIN_UNDEFINE_NVRAM
    )
    assert all(v.deleted for name, v in conn.pool.volumes.items() if name.startswith("host01"))
    assert not conn.pool.volumes["debian-13-base.qcow2"].deleted
    assert dns["removed"] == {"host01.zbuilder.local": {}}


def test_snapshot_create_replaces_the_previous_one(hypervisor):
    provider, conn, dns = hypervisor
    provider.build({"host01.zbuilder.local": hostVars()})
    dom = conn.domains["host01.zbuilder.local"]

    provider.snapCreate({"host01.zbuilder.local": hostVars()})
    first = dom.snapshots[kvm.SNAPSHOT]
    provider.snapCreate({"host01.zbuilder.local": hostVars()})

    assert dom.snapshots[kvm.SNAPSHOT] is not first


def test_snapshot_restore_boots_the_host_back_up(hypervisor):
    provider, conn, dns = hypervisor
    provider.build({"host01.zbuilder.local": hostVars()})
    provider.snapCreate({"host01.zbuilder.local": hostVars()})
    dom = conn.domains["host01.zbuilder.local"]
    dom.shutdown()

    snapshot = dom.snapshots[kvm.SNAPSHOT]

    provider.snapRestore({"host01.zbuilder.local": hostVars()})

    assert dom.reverted is snapshot
    assert dom.state()[0] == FakeLibvirt.VIR_DOMAIN_RUNNING


def test_snapshots_refuse_a_raw_disk(hypervisor, capsys):
    """Internal snapshots need qcow2, say so instead of failing in libvirt"""
    provider, conn, dns = hypervisor
    conn.domains["host01.zbuilder.local"] = FakeDomain(
        "host01.zbuilder.local",
        xml=kvm._domainXML("host01", {}, [{"path": "/pool/root.raw", "target": "vda", "format": "raw"}]),
        state=FakeLibvirt.VIR_DOMAIN_RUNNING,
    )

    provider.snapCreate({"host01.zbuilder.local": hostVars()})

    assert "raw disk" in capsys.readouterr().out
