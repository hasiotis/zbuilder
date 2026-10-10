# zbuilder remote KVM example

Four guests on a remote libvirt hypervisor reached over ssh, two Debian 13 and
two Ubuntu 26.04, built from cloud image templates and seeded with cloud-init.
Unlike [`kvm-local`](../kvm-local/), the guests sit on a bridge of the LAN with
static addresses: zbuilder reserves each address in phpIPAM, writes it into the
guest's cloud-init network config, publishes the name in PowerDNS, and then
hands the guests to ansible.

| group    | hosts                                  | spec                                   |
|----------|----------------------------------------|----------------------------------------|
| `debian` | `debian01.kvm.loc`, `debian02.kvm.loc` | 2 vcpu, 2GB, 20GB root (+5GB on `*02`) |
| `ubuntu` | `ubuntu01.kvm.loc`, `ubuntu02.kvm.loc` | 2 vcpu, 2GB, 20GB root (+5GB on `*02`) |

All of them get an address from `192.168.33.0/24`, use `192.168.33.2` as their
nameserver and `kvm.loc` as their search domain.

## Prerequisites

zbuilder depends on `libvirt-python`, which builds against `libvirt-dev`, so
that package has to be installed on the machine running zbuilder before
zbuilder itself:

```
apt install libvirt-dev pkg-config gcc     # or: dnf install libvirt-devel
```

On the hypervisor:

- libvirt, with your ssh user able to reach `qemu:///system` (e.g. in the
  `libvirt` group). `virsh -c qemu+ssh://<user>@<hypervisor>/system list` from
  the zbuilder machine has to work without a password prompt, so use key auth.
- A bridge on the LAN, here `br0`, that the guests are plugged into.
- The template volumes `debian-13-base.qcow2` and `ubuntu-26.04-base.qcow2` in
  the `default` pool. The steps are the same as in
  [setup-local-kvm.md](../kvm-local/setup-local-kvm.md#2-the-template-volumes),
  run on the hypervisor.

On the network:

- A phpIPAM server with an API app called `zbuilder`, and the subnet
  `192.168.33.0/24` defined in it **with its gateway set** — the gateway the
  guests are configured with is read from there.
- A PowerDNS server authoritative for `kvm.loc`, with the API enabled.
- `192.168.33.2` resolving `kvm.loc`, for the guests, and the zbuilder machine
  resolving it as well, since ansible reaches the guests by name.

### The providers

`hosts` refers only to `CLOUD: kvm-remote`. The IPAM and DNS providers are
found from the user config instead: `ipam=192.168.33.0/24` is matched against
every provider's `ipam.subnets`, and the zone of each host name (`kvm.loc`)
against every provider's `dns.zones`. All three go in
`~/.config/zbuilder/zbuilder.yaml`:

```
zbuilder config provider kvm-remote type=kvm
zbuilder config provider kvm-remote uri=qemu+ssh://<user>@<hypervisor>/system
zbuilder config provider kvm-remote pool=default
zbuilder config provider kvm-remote network=bridge=br0

zbuilder config provider home-ipam type=phpipam
zbuilder config provider home-ipam server=<ipam host>
zbuilder config provider home-ipam username=<user>
zbuilder config provider home-ipam password=<password>
zbuilder config provider home-ipam ipam/subnets=192.168.33.0/24

zbuilder config provider home-pdns type=powerdns
zbuilder config provider home-pdns url=http://<pdns host>:8081/
zbuilder config provider home-pdns apikey=<api key>
zbuilder config provider home-pdns dns/zones=kvm.loc

zbuilder config view
```

which ends up as:

```yaml
providers:
  kvm-remote:
    type: kvm
    uri: qemu+ssh://<user>@<hypervisor>/system
    pool: default
    network: bridge=br0

  home-ipam:
    type: phpipam
    server: <ipam host>
    username: <user>
    password: <password>
    ipam:
      subnets: 192.168.33.0/24

  home-pdns:
    type: powerdns
    url: http://<pdns host>:8081/
    apikey: <api key>
    dns:
      zones: kvm.loc
```

The PowerDNS `url` needs its trailing `/`.

## Use it

```
cd examples/kvm-remote

zbuilder summary                     # what the inventory says
zbuilder providers                   # are the hypervisor, phpIPAM and PowerDNS reachable
zbuilder build                       # reserve, create the domains, publish DNS, run bootstrap.yml
zbuilder play provision.yml          # the ansible half

ssh sysadmin@debian01.kvm.loc
```

Snapshots, and the rest of the lifecycle:

```
zbuilder snapshot create
zbuilder snapshot restore
zbuilder snapshot delete

zbuilder halt
zbuilder up
zbuilder destroy                     # domains, volumes, DNS records and IPAM reservations
```

Everything takes `--limit`, exactly as ansible does:

```
zbuilder build --limit debian01.kvm.loc
zbuilder destroy --limit ubuntu
```

If DNS gets out of step with the guests, `zbuilder dns update` / `zbuilder dns
remove` republish or drop the records without touching the domains.
