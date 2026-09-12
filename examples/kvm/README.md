# zbuilder KVM example

Two Debian 13 guests on the local libvirt hypervisor, built from a cloud image
template, seeded with cloud-init, then handed to ansible.

| host           | address           | spec                        |
|----------------|-------------------|-----------------------------|
| `kvm1.kvm.loc` | `192.168.122.101` | 1 vcpu, 1GB, 10GB root      |
| `kvm2.kvm.loc` | `192.168.122.102` | 1 vcpu, 1GB, 10GB root + 5GB `/data` |

## Prerequisites

A working `qemu:///system` you can reach without sudo, the default storage pool
and the default network:

```
virsh --connect qemu:///system pool-list
virsh --connect qemu:///system net-list
```

Your user has to be in the `libvirt` group. zbuilder depends on
`libvirt-python`, which builds against `libvirt-dev`, so that package has to be
installed before zbuilder itself:

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

### The template volume

`VM_OPTIONS.template` names a **volume in the pool**, not a path. The root disk
of each guest is a qcow2 overlay backed by it, so it must stay put for as long
as the guests live. To (re)create it:

```
curl -Lo /tmp/debian-13-base.qcow2 \
  https://cloud.debian.org/images/cloud/trixie/latest/debian-13-genericcloud-amd64.qcow2

virsh --connect qemu:///system vol-create-as default debian-13-base.qcow2 3G --format qcow2
virsh --connect qemu:///system vol-upload  --pool default debian-13-base.qcow2 /tmp/debian-13-base.qcow2
virsh --connect qemu:///system vol-list default
```

Any cloud image with cloud-init works — point `template:` at a different volume
and adjust `provision.yml` if it isn't Debian-flavoured.

## Use it

```
cd examples/kvm

zbuilder summary                     # what the inventory says
zbuilder providers                   # is the hypervisor reachable
zbuilder build                       # create the domains, then run bootstrap.yml
zbuilder play provision.yml          # the ansible half

ssh sysadmin@192.168.122.101
```

Snapshots, and the rest of the lifecycle:

```
zbuilder snapshot create
zbuilder snapshot restore
zbuilder snapshot delete

zbuilder halt
zbuilder up
zbuilder destroy                     # domains and their volumes, not the template
```

Everything takes `--limit`, exactly as ansible does:

```
zbuilder build --limit kvm1.kvm.loc
zbuilder destroy --limit demo
```
