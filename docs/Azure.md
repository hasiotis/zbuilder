# Initial zbuilder setup

Make sure you have installed the following on your system:

* az (Azure cli)


## Main configuration

Configure the source of your templates:
```
zbuilder config main templates repo=https://github.com/hasiotis/zbuilder-templates.git
zbuilder config main templates path=~/.config/zbuilder/templates
zbuilder config update --yes
```

## Create azure resources needed

First you need to create a resource group, a vnet (with a subnet) and the dns zone:
```
az group create -l westeurope -n zbuilder

az network vnet create -g zbuilder -n zbuilder-vnet
az network vnet subnet create -g zbuilder --vnet-name zbuilder-vnet -n zbuilder-subnet --address-prefixes "10.0.0.0/24"

az network dns zone create -g zbuilder -n azure.hasiotis.dev
```

In order to authenticate we will create a service principal:
```
az ad sp create-for-rbac --name zbuilder-principal
```
From this command you will find out appId,password and tenant.

You will find the subscriptionId from:
```
az account list | jq '.[0].id'
```

## Provider configuration

So you can now define *azure* as provider of type azure:
```
zbuilder config provider azure type=azure
zbuilder config provider azure client_id=<appId>
zbuilder config provider azure client_secret=<password>
zbuilder config provider azure tenant_id=<tenant>
zbuilder config provider azure subscription_id=<subscriptionId>
```

Let zbuilder know that azure provider will also handle the *azure.hasiotis.dev* zone:
```
zbuilder config provider azure.dns zones=azure.hasiotis.dev
zbuilder config view
```
For this to work you need to have your dns zone managed by azure DNS.

## Create your environment

Now create and environment from a vagrant template:
```
mkdir ZBUILDER_AZURE_DEMO
cd ZBUILDER_AZURE_DEMO
zbuilder init --template azure
zbuilder build
```

## Cleanup the environment

To remove all VMs run:
```
zbuilder destroy
```
