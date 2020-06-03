PHPipam Provider
================

Provider configuration
----------------------

Define *ipcatalog* as a provider of type phpipam::

  zbuilder config provider ipcatalog type=phpipam
  zbuilder config provider ipcatalog server=ip.yourhost.fqdn
  zbuilder config provider ipcatalog username=Admin
  zbuilder config provider ipcatalog password=YOURPASSWORD
  zbuilder config provider ipcatalog ssl=true
  zbuilder config provider ipcatalog verify=true

  zbuilder config provider ipcatalog.ipam subnets=192.168.0.0/24
  zbuilder config view
