import boto3
import click

from zbuilder.dns import dnsUpdate, dnsRemove


class vmProvider(object):
    def __init__(self, cfg):
        if cfg:
            self.cfg = cfg
            if 'aws_access_key_id' and 'aws_access_key_id' in cfg:
                self.ec2 = boto3.resource(
                    'ec2',
                    aws_access_key_id=cfg['aws_access_key_id'],
                    aws_secret_access_key=cfg['aws_secret_access_key']
                )
            else:
                self.ec2 = boto3.resource('ec2')

    def _getVMs(self, hosts):
        retValue = {}
        for h, v in hosts.items():
            if hosts[h]['enabled']:
                instances = list(self.ec2.instances.filter(Filters=[{'Name': 'tag:Name', 'Values': [h]}]))
                retValue[h] = {'status': None}
                for vm in instances:
                    if vm.state['Name'] not in ['terminated', 'shutting-down']:
                        retValue[h] = {'status': vm.state['Name'], 'vm': vm}
                retValue[h]['values'] = v

        return retValue

    def build(self, hosts):
        ips = {}
        for h, v in self._getVMs(hosts).items():
            if v['status'] is None:
                click.echo("  - Creating host: {} ".format(h))
                self.ec2.create_instances(
                    BlockDeviceMappings=[
                        {
                            'DeviceName': '/dev/sda1',
                            'Ebs': {
                                'DeleteOnTermination': True,
                                'VolumeSize': v['values'].get('disksize', 20),
                                'VolumeType': 'standard',
                            },
                        },
                    ],
                    TagSpecifications=[{'ResourceType': 'instance', 'Tags': [{'Key': 'Name', 'Value': h}]}],
                    ImageId=v['values']['ami'], MinCount=1, MaxCount=1,
                    InstanceType=v['values']['vmtype'],
                    KeyName=v['values']['key'],
                    SecurityGroupIds=v['values']['sg'],
                    SubnetId=v['values']['subnet'],
                    UserData="""#cloud-config
                    fqdn: {}
                    manage_etc_hosts: true
                    """.format(h)
                )
            else:
                click.echo("  - Status of host: {} is {}".format(h, v['status']))

        for h, v in self._getVMs(hosts).items():
            if v['status'] is not None:
                v['vm'].wait_until_running()
                v['vm'].reload()
                ips[h] = v['vm'].public_ip_address

        dnsUpdate(ips)

    def up(self, hosts):
        pass

    def halt(self, hosts):
        pass

    def destroy(self, hosts):
        updateHosts = {}
        for h, v in self._getVMs(hosts).items():
            if v['status'] is not None:
                click.echo("  - Destroying host: {} ".format(h))
                v['vm'].terminate()
                updateHosts[h] = {}
            else:
                click.echo("  - Host does not exists : {}".format(h))

        dnsRemove(updateHosts)

    def dnsupdate(self, hosts):
        ips = {}
        for h, v in self._getVMs(hosts).items():
            if hosts[h]['enabled']:
                ips[h] = v['vm'].public_ip_address
        dnsUpdate(ips)

    def dnsremove(self, hosts):
        ips = {}
        for h in hosts:
            if hosts[h]['enabled']:
                ips[h] = None
        dnsRemove(hosts)

    def snapCreate(self, hosts):
        pass

    def snapRestore(self, hosts):
        pass

    def snapDelete(self, hosts):
        pass

    def config(self):
        return "aws_access_key_id: {}".format(self.cfg['aws_access_key_id'])

    def status(self):
        return "PASS"

    def params(self, params):
        return {k: params[k] for k in ['ami', 'region', 'vmtype', 'subnet', 'sg']}
