## Initial zbuilder setup

Make sure you have installed the following on your system:

* Vagrant
* vagrant-hostmanager plugin
* VirtualBox

Define *local* as a provider of type vagrant
``` shell
zbuilder config provider --type vagrant local
```

Configure the source of your templates:
``` shell
zbuilder config main templates=https://github.com/hasiotis/zbuilder-templates.git
```
