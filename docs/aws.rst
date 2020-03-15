Google Cloud Provider
=====================

Initial zbuilder setup
----------------------

Make sure you have installed the following on your system:

* aws cli

Create aws resources needed (optional)
--------------------------------------

Find out our default VPC id::

  VPCID=`aws ec2 describe-vpcs | jq -r '.Vpcs[] | select(.IsDefault == true) | .VpcId'`

Make sure there is public ssh access to it::

  aws ec2 create-security-group --group-name SSHAccess --description "Security group for SSH access" --vpc-id $VPCID
  SGID=`aws ec2 describe-security-groups | jq -r '.SecurityGroups[] | select(.GroupName == "SSHAccess") | .GroupId'`
  aws ec2 authorize-security-group-ingress --group-id $SGID --protocol tcp --port 22 --cidr 0.0.0.0/0

Upload our ssh key into AWS::

  aws ec2 import-key-pair --key-name "sysadmin@zbuilder.com" --public-key-material fileb://~/.ssh/id_rsa.pub

Use these ids (security groups, subnet) for configuring *group_vars/all*::

  aws ec2 describe-subnets | jq -r ".Subnets[0] | select(.VpcId == \"$VPCID\") | .SubnetId"
  aws ec2 describe-security-groups | jq -r '.SecurityGroups[] | select(.GroupName == "default" or .GroupName == "SSHAccess") | .GroupId'

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
  (update security groups and subnet)
  zbuilder build

Cleanup the environment
-----------------------

To remove all VMs run::

  zbuilder destroy
