# Initial zbuilder setup

Make sure you have installed the following on your system:

* doctl

## Create digital ocean resources needed

```
doctl compute domain create do.hasiotis.dev
```

## Main configuration

Configure the source of your templates:
```
zbuilder config main templates repo=https://github.com/hasiotis/zbuilder-templates.git
zbuilder config main templates path=~/.config/zbuilder/templates
zbuilder config update --yes
```

## Provider configuration

Define *digital-ocean* as a provider of type do
```
zbuilder config provider digital-ocean type=do
zbuilder config provider digital-ocean apikey=SUPERDUPERSECRET
zbuilder config view
```

Let zbuilder know that digital ocean provider will also handle the *do.hasiotis.dev* zone:
```
zbuilder config provider digital-ocean.dns zones=do.hasiotis.dev
zbuilder config view
```
For this to work you need to have your dns zone managed by digital ocean DNS.

## Create your environment

Now create and environment from a vagrant template:
```
mkdir ZBUILDER_DO_DEMO
cd ZBUILDER_DO_DEMO
zbuilder init --template do
zbuilder build
```

## Cleanup the environment

To remove all VMs run:
```
zbuilder destroy
```
