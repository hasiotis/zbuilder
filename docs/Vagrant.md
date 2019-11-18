## Initial zbuilder setup

Make sure you have installed the following on your system:

* Vagrant
* vagrant-hostmanager plugin
* VirtualBox

# Main configuration

Configure the source of your templates:
```
zbuilder config main templates repo=https://github.com/hasiotis/zbuilder-templates.git
zbuilder config main templates path=~/.config/zbuilder/templates
zbuilder config update --yes
```

# Provider configuration

Define *local* as a provider of type vagrant
```
zbuilder config provider local type=vagrant
zbuilder config view
```

# Create your environment

Now create and environment from a vagrant template:
```
mkdir ZBUILDER_VAGRANT_DEMO
cd ZBUILDER_VAGRANT_DEMO
zbuilder init --template vagrant
zbuilder build
```

To remove all VMs run:
```
zbuilder destroy
```
