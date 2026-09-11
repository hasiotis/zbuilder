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

Your user has to be in the `libvirt` group. zbuilder itself needs the optional
extra, since `libvirt-python` builds against `libvirt-dev`:

```
uv sync --extra kvm      # in the zbuilder checkout
```

### The provider

`CLOUD: kvmlocal` in `hosts` refers to a provider you have to declare once, in
`~/.config/zbuilder/zbuilder.yaml`:

```
zbuilder config provider kvmlocal type=kvm
zbuilder config provider kvmlocal uri=qemu:///system
zbuilder config provider kvmlocal pool=default
zbuilder config provider kvmlocal network=default
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

## How it hangs together

`hosts` is a plain ansible inventory, which is the whole point of zbuilder —
group_vars, host_vars and templating all apply. A host is a zbuilder host
because it defines `ZBUILDER_PROVIDER`; `localhost` does not, so it is ignored.

* `CLOUD: kvmlocal` selects the `providers.kvmlocal` entry in
  `~/.config/zbuilder/zbuilder.yaml`, whose `type: kvm` picks the plugin.
* `ipconfig: ip=.../24,gw=...` becomes a netplan v2 `network-config` in the
  NoCloud seed. Drop the key entirely and the guest falls back to DHCP, with
  zbuilder reading the address back off the libvirt lease — but then nothing
  guarantees which address it gets, hence the static ones plus a matching
  `ansible_host` here.
* `ZBUILDER_PUBKEY` and `ZBUILDER_SYSUSER` (top level, inherited by both hosts)
  become the `user-data` that creates the login account.
* `disks: [5]` on `kvm2` adds one 5GB volume as `/dev/vdb`. `provision.yml`
  formats and mounts it.
* The seed iso is uploaded into the pool as a volume over a libvirt stream, so
  nothing is written to the local filesystem. Pointing `uri` at a
  `qemu+ssh://...` host would work the same way.

`zbuilder build` runs `bootstrap.yml` on its own once the domains are up.
`provision.yml` is separate, so it can be re-run on its own.

## Notes

* No DNS provider covers `kvm.loc`, so `build` prints
  `No DNS provider found for zone [kvm.loc]` and moves on. That is expected —
  ansible reaches the hosts through `ansible_host`.
* `zbuilder snapshot create` uses internal qcow2 snapshots, which is why the
  extra disks are qcow2 rather than raw.
* Dropping a `domain.xml.tmpl` in this directory overrides the built-in libvirt
  domain template.
