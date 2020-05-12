Proxmox Provider
===============

Main configuration
------------------

Configure the source of your templates::

  zbuilder config main templates repo=https://github.com/hasiotis/zbuilder-templates.git
  zbuilder config main templates path=~/.config/zbuilder/templates
  zbuilder config update --yes

Provider configuration
----------------------

Define *pve* as a provider of type proxmox::

  zbuilder config provider pve type=proxmox
  zbuilder config provider pve username=root@pam
  zbuilder config provider pve password=YOURPASSWORD
  zbuilder config provider pve url=yourhost.fqdn
  zbuilder config provider pve ssl=true
  zbuilder config provider pve verify=true
  zbuilder config view


Since proxmox is not a DNS provider we will use ansible for the DNS (poor man's DNS)::

  zbuilder config provider ansible type=ansible
  zbuilder config provider ansible.dns zones=proxmox.hasiotis.dev
  zbuilder config view


Create your environment
-----------------------

Now create and environment from a proxmox template::

  mkdir ZBUILDER_PROXMOX_DEMO
  cd ZBUILDER_PROXMOX_DEMO
  zbuilder init --template proxmox
  zbuilder build

Cleanup the environment
-----------------------

To remove all VMs run::

  zbuilder destroy
