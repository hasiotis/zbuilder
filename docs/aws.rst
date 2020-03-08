Google Cloud Provider
=====================

Initial zbuilder setup
----------------------

Make sure you have installed the following on your system:

* aws cli

Main configuration
------------------

Configure the source of your templates::

  zbuilder config main templates repo=https://github.com/hasiotis/zbuilder-templates.git
  zbuilder config main templates path=~/.config/zbuilder/templates
  zbuilder config update --yes

Provider configuration
----------------------

Define *amazon* as a provider of type aws::

  zbuilder config provider amazon type=aws

Let zbuilder know that aws provider will also handle the *aws.hasiotis.dev* zone::

  zbuilder config provider amazon.dns zones=aws.hasiotis.dev
  zbuilder config view

For this to work you need to have your dns zone managed by aws route53

Create your environment
-----------------------

Now create and environment from a vagrant template::

  mkdir ZBUILDER_AWS_DEMO
  cd ZBUILDER_AWS_DEMO
  zbuilder init --template aws
  zbuilder build

Cleanup the environment
-----------------------

To remove all VMs run::

  zbuilder destroy
