# Setting up a local KVM host for zbuilder

Here is how to prepare a local KVM, to use with zbuilder.

## 1. libvirt

```
apt install qemu-system-x86 libvirt-daemon-system libvirt-clients
sudo usermod -aG libvirt $USER          # log out and back in
```

Check that `qemu:///system` is reachable without sudo and that the default
pool and network exist and are active:

```
virsh pool-list
virsh net-list
```

## 2. The template volumes

`VM_OPTIONS.template` is a **volume in the pool**, not a path. Every guest's
root disk is a qcow2 overlay backed by it, so leave it in place for as long as
the guests exist.

```
curl -Lo /tmp/debian-13-base.qcow2 https://cloud.debian.org/images/cloud/trixie/latest/debian-13-genericcloud-amd64.qcow2
virsh vol-create-as default debian-13-base.qcow2 3G --format qcow2
virsh vol-upload --pool default debian-13-base.qcow2 /tmp/debian-13-base.qcow2

curl -Lo /tmp/ubuntu-26.04-base.qcow2 https://cloud-images.ubuntu.com/resolute/current/resolute-server-cloudimg-amd64.img
virsh vol-create-as default ubuntu-26.04-base.qcow2 3G --format qcow2
virsh vol-upload --pool default ubuntu-26.04-base.qcow2 /tmp/ubuntu-26.04-base.qcow2

virsh vol-list default
```

## 3. DNS

No separate DNS server is needed. The dnsmasq that
libvirt already runs for the `default` network is the DNS server for `kvm.lan`,
and the host's resolver sends `kvm.lan` lookups to it:

```
ansible / ssh on the host
   │  debian01.kvm.lan?
   ▼
systemd-resolved ── ~kvm.lan ──► dnsmasq on virbr0 (192.168.122.1)
   │ everything else                  │ names come from the DHCP leases
   ▼                                  ▼
your normal upstream DNS          debian01 → 192.168.122.x
```

cloud-init sets each guest's hostname to the short name (`debian01`), the guest
sends it in its DHCP request, and dnsmasq answers for `<hostname>.kvm.lan` from
then on. A rebuilt guest gets a new MAC and a new lease, and its name follows
the new address.

### 3.1 Give the libvirt network a domain

```
virsh net-edit default
```

Add the `<domain>` element next to `<bridge>`:

```xml
<network>
  <name>default</name>
  <forward mode='nat'/>
  <bridge name='virbr0' stp='on' delay='0'/>
  <domain name='kvm.lan' localOnly='yes'/>
  <ip address='192.168.122.1' netmask='255.255.255.0'>
    <dhcp>
      <range start='192.168.122.2' end='192.168.122.254'/>
    </dhcp>
  </ip>
</network>
```

`localOnly='yes'` makes dnsmasq authoritative for `kvm.lan`. An unknown name gets
NXDOMAIN right away rather than being forwarded upstream.

The change only applies when the network restarts. Guests already attached
lose their link while it happens, so do this before building anything:

```
virsh net-destroy default
virsh net-start default
```

### 3.2 Route `kvm.lan` to it on the host (systemd-resolved)

```
resolvectl dns virbr0 192.168.122.1
resolvectl domain virbr0 '~kvm.lan'
```

The `~` makes `kvm.lan` a routing-only domain: only `*.kvm.lan` queries go to
virbr0, nothing gets appended to short names, and every other query still goes
to your normal DNS.

These settings belong to the link and are lost every time virbr0 is recreated
(reboot, `net-destroy`/`net-start`). To reapply them automatically, use a
libvirt network hook at `/etc/libvirt/hooks/network`:

```sh
#!/bin/sh
# libvirt calls this as: network <name> <operation> <sub-op> -
# Route kvm.lan lookups on the host to the default network's dnsmasq
if [ "$1" = "default" ] && [ "$2" = "started" ]; then
    resolvectl dns virbr0 192.168.122.1
    resolvectl domain virbr0 '~kvm.lan'
fi
exit 0
```

```
sudo chmod +x /etc/libvirt/hooks/network
sudo systemctl restart libvirtd        # or virtnetworkd, on modular-daemon setups
```

libvirt looks for hook scripts only when the daemon starts, so restart it
once after creating the hook.

If the host runs NetworkManager with its own dnsmasq rather than
systemd-resolved, put this in `/etc/NetworkManager/dnsmasq.d/kvm.lan.conf` and
reload NetworkManager instead:

```
server=/kvm.lan/192.168.122.1
```

### 3.3 Verify

```
resolvectl status virbr0               # DNS Servers: 192.168.122.1, DNS Domain: ~kvm.lan
```

Once guests are running:

```
virsh net-dhcp-leases default                   # hostnames should be listed
dig +short @192.168.122.1 debian01.kvm.lan      # dnsmasq directly
resolvectl query debian01.kvm.lan               # through the host resolver
```

If `dig` returns an answer but `resolvectl query` doesn't, the routing in 3.2
isn't in place. If neither returns an answer, look at the leases: a guest
without a hostname there didn't send one, so cloud-init probably hasn't run.
