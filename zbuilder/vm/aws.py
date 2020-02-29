import boto3
import click

from zbuilder.dns import dnsUpdate, dnsRemove


class vmProvider(object):
    def __init__(self, cfg):
        if cfg:
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
                if len(instances) == 0:
                    retValue[h] = {'status': None}
                else:
                    vm = instances[0]
                    retValue[h] = {'status': vm.state['Name'], 'vm': vm}
                retValue[h]['values'] = v

        return retValue

    def build(self, hosts):
        ips = {}
        for h, v in self._getVMs(hosts).items():
            if v['status'] is None:
                click.echo("  - Creating host: {} ".format(h))
                self.ec2.create_instances(
                    TagSpecifications=[{'ResourceType': 'instance', 'Tags': [{'Key': 'Name', 'Value': h}]}],
                    ImageId=v['values']['ami'], MinCount=1, MaxCount=1
                )
            else:
                click.echo("  - Status of host: {} is {}".format(h, v['status']))

        for h, v in self._getVMs(hosts).items():
            v['vm'].wait_until_running()
            ips[h] = v['vm'].private_ip_address

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
        pass

    def dnsremove(self, hosts):
        pass

    def snapCreate(self, hosts):
        pass

    def snapRestore(self, hosts):
        pass

    def snapDelete(self, hosts):
        pass

    def params(self, params):
        return {k: params[k] for k in ['size', 'image']}
