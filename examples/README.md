# Examples

Self-contained, runnable zbuilder setups. Each directory is an ansible
inventory plus the playbooks around it — `cd` into one and run zbuilder from
there.

| example | what it builds |
|---|---|
| [`kvm/`](kvm/) | Two Debian 13 guests on a local libvirt hypervisor, cloud-init seeded |
| [`aws/`](aws/) | Two Debian 13 EC2 instances, published in route53 as they come up |
| [`proxmox/`](proxmox/) | Two Debian 13 guests cloned from a cloud-init template on a PVE node |
| [`gcp/`](gcp/) | Two Debian 13 Compute Engine instances, published in Cloud DNS |
