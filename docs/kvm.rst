KVM Provider
============

The kvm provider talks to libvirt. Everything it does - creating disks,
uploading the cloud-init seed, defining and starting domains - goes over a
single libvirt connection, so a hypervisor reached over ``qemu+ssh://`` behaves
exactly like a local ``qemu:///system``. Nothing is ever written to the machine
running zbuilder.

Prerequisites
-------------

The libvirt bindings are a hard dependency of zbuilder, and they compile
against the libvirt headers, so those have to be in place before the install.
On the machine running zbuilder::

  apt install libvirt-dev pkg-config gcc     # or: dnf install libvirt-devel
  pip install zbuilder

On the hypervisor you need libvirt itself, a storage pool, and a network::

  virsh pool-list
  virsh net-list

For a remote hypervisor, plain ssh key access to a user in the ``libvirt``
group is all that is needed - no agent, no extra daemon.

Base images
-----------

Hosts are cloned from a template volume in the pool, which is a normal cloud
image with cloud-init in it. Import one once::

  wget https://cloud.debian.org/images/cloud/trixie/latest/debian-13-genericcloud-amd64.qcow2
  virsh vol-create-as default debian-13-base.qcow2 4G --format qcow2
  virsh vol-upload --pool default debian-13-base.qcow2 debian-13-genericcloud-amd64.qcow2

By default a host gets a thin clone backed by that volume, which costs nothing
to create. Set ``full: true`` on a host to get a full copy instead.

Main configuration
------------------

Configure the source of your templates::

  zbuilder config main templates repo=https://github.com/hasiotis/zbuilder-templates.git
  zbuilder config main templates path=~/.config/zbuilder/templates
  zbuilder config update --yes

Provider configuration
----------------------

Define *kvmhost* as a provider of type kvm::

  zbuilder config provider kvmhost type=kvm
  zbuilder config provider kvmhost uri=qemu+ssh://root@hyper01.hasiotis.dev/system
  zbuilder config provider kvmhost pool=default
  zbuilder config provider kvmhost network=default
  zbuilder config view

===========  ==========================================================
Setting      Meaning
===========  ==========================================================
``uri``      libvirt connection uri, defaults to ``qemu:///system``
``pool``     storage pool holding the templates and the disks
``network``  libvirt network, or ``bridge=<name>`` for a bridged nic
``timeout``  seconds to wait for a shutdown or a dhcp lease, default 120
===========  ==========================================================

Check the connection with::

  zbuilder providers

Since kvm is not a DNS provider we will use ansible for the DNS (poor man's
DNS)::

  zbuilder config provider ansible type=ansible
  zbuilder config provider ansible.dns zones=kvm.hasiotis.dev
  zbuilder config view

Host definition
---------------

The inventory vocabulary is the same as the proxmox one, so a host can move
between the two providers::

  ZBUILDER_PROVIDER:
    CLOUD: kvmhost
    DNS: ansible
    VM_OPTIONS:
      template: debian-13-base.qcow2
      memory: 2048
      vcpu: 2
      size: 20
      disks: [50]
      ipconfig: "ip=10.0.0.10/24,gw=10.0.0.1"
      nameserver: 10.0.0.1
      searchdomain: kvm.hasiotis.dev

===============  ======================================================
VM option        Meaning
===============  ======================================================
``template``     volume in the pool used as the base image
``memory``       MiB of RAM
``vcpu``         number of cpus (``vcpus`` is accepted too)
``size``         GiB of the root disk, defaults to the template's size
``disks``        extra disks, in GiB, as a size or a list of sizes
``full``         ``true`` for a full clone instead of a thin one
``pool``         override the provider's storage pool
``network``      override the provider's network
``ipconfig``     ``ip=<addr>/<mask>,gw=<gw>``, ``ipam=<subnet>``, or unset
``nameserver``   resolvers, space separated
``searchdomain`` search domains, space separated
``machine``      qemu machine type, defaults to ``q35``
``cpu``          cpu mode, defaults to ``host-passthrough``
``interface``    glob the guest matches its nic with, defaults to ``e*``
===============  ======================================================

A host without an ``ipconfig`` is left on DHCP, and its address is read back
from the libvirt lease or from the qemu guest agent. With ``ipam=<subnet>`` the
address comes from the IPAM provider serving that subnet, see :doc:`phpipam`.

``ZBUILDER_SYSUSER`` and ``ZBUILDER_PUBKEY`` become the user and the authorized
key of the guest, through a cloud-init NoCloud seed uploaded into the pool
alongside the disks.

Create your environment
-----------------------

Now create an environment from a kvm template::

  mkdir ZBUILDER_KVM_DEMO
  cd ZBUILDER_KVM_DEMO
  zbuilder init --template kvm
  zbuilder build

Snapshots are internal qcow2 snapshots named ``zbuilder``::

  zbuilder snapshot create
  zbuilder snapshot restore
  zbuilder snapshot delete

Custom domains
--------------

The domain XML comes from an embedded template. Drop a ``domain.xml.tmpl`` in
the environment directory to override it - it is rendered with jinja and gets
``name``, ``memory``, ``vcpu``, ``arch``, ``machine``, ``cpu``, ``disks``,
``seed``, ``interface`` and ``description``.

Cleanup the environment
-----------------------

To remove all VMs run::

  zbuilder destroy

Destroy deletes the disks the domain actually points at, so nothing is left
behind in the pool.
