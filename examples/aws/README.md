# zbuilder AWS example

Two Debian 13 EC2 instances, named in route53 as they come up, then handed to
ansible.

| host               | spec                             |
|--------------------|----------------------------------|
| `aws1.example.com` | `t3.micro`, 20GB root            |
| `aws2.example.com` | `t3.micro`, 30GB root            |

Replace `example.com` throughout with a zone you actually own — the hostnames
are the DNS records, there is no `ansible_host` to fall back to.

## Prerequisites

Credentials boto3 can find, and a region, since the provider builds its
`boto3.resource("ec2")` without one:

```
export AWS_PROFILE=your-profile
export AWS_DEFAULT_REGION=eu-west-1      # must match VM_OPTIONS.region in hosts
aws sts get-caller-identity
```

`VM_OPTIONS.region` is only read by `zbuilder summary`; what actually decides
where the instances land is the region boto3 resolves from the environment or
the profile. Keeping the two in sync is on you.

You also need, in that region:

* An **EC2 key pair** — `VM_OPTIONS.key` is its name, and it is the only key
  that gets into the instance. Unlike the kvm example, `ZBUILDER_PUBKEY` and
  `ZBUILDER_SYSUSER` are ignored by this provider; the login user is whatever
  the AMI ships (`admin` on Debian).
* A **subnet** that auto-assigns public IPv4. The provider reads
  `public_ip_address` off the instance and publishes that, and never asks for
  an address explicitly, so a subnet without `MapPublicIpOnLaunch` leaves you
  with no record and no route in.
* A **security group** allowing 22 from wherever you run zbuilder.
* A **route53 hosted zone** for the domain the hosts are named in.

Then fill the four placeholders in `hosts` (`ami`, `key`, `subnet`, `sg`):

```
aws ec2 describe-images --owners 136693071363 \
  --filters 'Name=name,Values=debian-13-amd64-*' \
  --query 'sort_by(Images,&CreationDate)[-1].ImageId' --output text

aws ec2 describe-key-pairs      --query 'KeyPairs[].KeyName' --output text
aws ec2 describe-subnets        --query 'Subnets[].[SubnetId,CidrBlock,MapPublicIpOnLaunch]' --output text
aws ec2 describe-security-groups --query 'SecurityGroups[].[GroupId,GroupName]' --output text
```

### The provider

`CLOUD: aws-demo` and `DNS: aws-demo` in `hosts` refer to a provider you
declare once, in `~/.config/zbuilder/zbuilder.yaml`:

```
zbuilder config provider aws-demo type=aws
zbuilder config provider aws-demo dns.zones=example.com
zbuilder config view
```

That is enough if boto3 finds credentials by itself. To pin them to this
provider instead:

```
zbuilder config provider aws-demo aws_access_key_id=AKIA...
zbuilder config provider aws-demo aws_secret_access_key=...
```

`dns.zones` is what actually selects the DNS provider: zbuilder splits each
hostname, matches the zone against every provider's `dns.zones`, and uses the
first that fits.

## Use it

```
cd examples/aws

zbuilder summary                     # what the inventory says
zbuilder providers                   # are the credentials good
zbuilder build                       # create the instances, publish DNS, run bootstrap.yml
zbuilder play provision.yml          # the ansible half

ssh admin@aws1.example.com
```

```
zbuilder dns update                  # republish the records, e.g. after a stop/start
zbuilder destroy                     # terminate, and withdraw the records
```

Everything takes `--limit`, exactly as ansible does:

```
zbuilder build --limit aws1.example.com
zbuilder destroy --limit demo
```
