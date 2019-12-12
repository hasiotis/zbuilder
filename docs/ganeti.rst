Ganeti Provider
===============

Main configuration
------------------

Configure the source of your templates::

  zbuilder config main templates repo=https://github.com/hasiotis/zbuilder-templates.git
  zbuilder config main templates path=~/.config/zbuilder/templates
  zbuilder config update --yes

Provider configuration
----------------------

Define *ganeti* as a provider of type ganeti::

  zbuilder config provider ganeti type=ganeti
  zbuilder config provider ganeti user=YOURUSER
  zbuilder config provider ganeti apikey=SUPERDUPERSECRET
  zbuilder config provider ganeti url=https://yourhost.fqdn:5080
  zbuilder config provider ganeti verify=false
  zbuilder config view


Since ganeti is not a DNS provider we will use ansible for the DNS (poor man's DNS)::

  zbuilder config provider ansible type=ansible
  zbuilder config provider ansible.dns zones=ganeti.hasiotis.dev
  zbuilder config view


Create your environment
-----------------------

Now create and environment from a vagrant template::

  mkdir ZBUILDER_GANETI_DEMO
  cd ZBUILDER_GANETI_DEMO
  zbuilder init --template ganeti
  zbuilder build

Cleanup the environment
-----------------------

To remove all VMs run::

  zbuilder destroy
