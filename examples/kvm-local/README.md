# zbuilder KVM example

Four guests on the local libvirt hypervisor, two Debian 13 and two Ubuntu 26.04,
built from cloud image templates, seeded with cloud-init, then handed to ansible.
They are on DHCP and ansible reaches them by name under `kvm.lan`.

| group    | hosts                                  | spec                                  |
|----------|----------------------------------------|---------------------------------------|
| `debian` | `debian01.kvm.lan`, `debian02.kvm.lan` | 2 vcpu, 2GB, 20GB root (+5GB on `*02`) |
| `ubuntu` | `ubuntu01.kvm.lan`, `ubuntu02.kvm.lan` | 2 vcpu, 2GB, 20GB root (+5GB on `*02`) |

## Prerequisites

The host needs libvirt, the template volumes and DNS for `kvm.lan`. All three
are covered in [setup-local-kvm.md](setup-local-kvm.md).

zbuilder depends on `libvirt-python`, which builds against `libvirt-dev`, so
that package has to be installed before zbuilder itself:

```
apt install libvirt-dev pkg-config gcc     # or: dnf install libvirt-devel
```

### The provider

`CLOUD: kvm-local` in `hosts` refers to a provider you have to declare once, in
`~/.config/zbuilder/zbuilder.yaml`:

```
zbuilder config provider kvm-local type=kvm
zbuilder config provider kvm-local uri=qemu:///system
zbuilder config provider kvm-local pool=default
zbuilder config provider kvm-local network=default
zbuilder config view
```

## Use it

```
cd examples/kvm-local

zbuilder summary                     # what the inventory says
zbuilder providers                   # is the hypervisor reachable
zbuilder build                       # create the domains, then run bootstrap.yml
zbuilder play provision.yml          # the ansible half

ssh sysadmin@debian01.kvm.lan
```

Snapshots, and the rest of the lifecycle:

```
zbuilder snapshot create
zbuilder snapshot restore
zbuilder snapshot delete

zbuilder halt
zbuilder up
zbuilder destroy                     # domains and their volumes, not the templates
```

Everything takes `--limit`, exactly as ansible does:

```
zbuilder build --limit debian01.kvm.lan
zbuilder destroy --limit ubuntu
```
