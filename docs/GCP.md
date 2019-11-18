## Initial zbuilder setup

Make sure you have installed the following on your system:

* gcloud (Google Cloud SDK)


# Main configuration

Configure the source of your templates:
```
zbuilder config main templates repo=https://github.com/hasiotis/zbuilder-templates.git
zbuilder config main templates path=~/.config/zbuilder/templates
zbuilder config update --yes
```

# Create google resources needed

First you need to create a gcp project in order to create your service account and auth key:
```
gcloud projects create zbuilder-demo --name="ZBUILDER demo"
```

Create the service account and the auth key:
```
gcloud iam service-accounts create zbuilder-account --project zbuilder-demo --display-name ZBuilder
gcloud iam service-accounts keys create ~/.config/zbuilder/zbuilder-key.json --iam-account=zbuilder-account@zbuilder-demo.iam.gserviceaccount.com

gcloud projects add-iam-policy-binding zbuilder-demo --member serviceAccount:zbuilder-account@zbuilder-demo.iam.gserviceaccount.com --role roles/compute.admin
gcloud projects add-iam-policy-binding zbuilder-demo --member serviceAccount:zbuilder-account@zbuilder-demo.iam.gserviceaccount.com --role roles/dns.admin
```

Create a dns zone to be managed by zbuilder:
```
gcloud dns managed-zones create gcp-hasiotis-dev --project zbuilder-demo --dns-name gcp.hasiotis.dev. --description "ZBuilder managed gcp zone"
```

# Provider configuration

Define *google* as a provider of type gcp:
```
zbuilder config provider google type=gcp
zbuilder config provider google service-key=zbuilder-key.json
```

Let zbuilder know that google provider will also handle the *gcp.hasiotis.dev* zone:
```
zbuilder config provider google.dns zones=gcp.hasiotis.dev
zbuilder config provider google.dns project=zbuilder-demo
zbuilder config view
```
For this to work you need to have your dns zone managed by google cloud DNS.


# Create your environment

Now create and environment from a vagrant template:
```
mkdir ZBUILDER_GCP_DEMO
cd ZBUILDER_GCP_DEMO
zbuilder init --template gcp
zbuilder build
```

To remove all VMs run:
```
zbuilder destroy
```
