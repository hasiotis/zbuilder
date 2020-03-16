import click
import boto3


class dnsProvider(object):
    def __init__(self, cfg):
        if cfg:
            if 'aws_access_key_id' and 'aws_access_key_id' in cfg:
                self.route53 = boto3.client(
                    'route53',
                    aws_access_key_id=cfg['aws_access_key_id'],
                    aws_secret_access_key=cfg['aws_secret_access_key']
                )
            else:
                self.route53 = boto3.client('route53')

    def update(self, host, zone, ip):
        response = self.route53.list_hosted_zones_by_name(DNSName=zone)
        if response['HostedZones']:
            zoneID = response['HostedZones'][0]['Id']
            fqdn = "{}.{}".format(host, zone)
            click.echo("  - Update record [{}] with ip [{}]".format(fqdn, ip))

            oldIP = None
            record_set = self.route53.list_resource_record_sets(HostedZoneId=zoneID, StartRecordName=fqdn, StartRecordType='A', MaxItems='1')
            for rs in record_set['ResourceRecordSets']:
                oldIP = rs['ResourceRecords'][0]['Value']

            if oldIP != ip:
                try:
                    response = self.route53.change_resource_record_sets(
                        HostedZoneId=zoneID,
                        ChangeBatch={
                            'Comment': 'ZBuilder manages',
                            'Changes': [{
                                'Action': 'UPSERT',
                                'ResourceRecordSet': {
                                    'Name': fqdn,
                                    'Type': 'A',
                                    'TTL': 300,
                                    'ResourceRecords': [{'Value': ip}]
                                }
                             }]
                        }
                    )
                    if 'ChangeInfo' in response:
                        ChangeInfoID = response['ChangeInfo']['Id']
                        waiter = self.route53.get_waiter('resource_record_sets_changed')
                        waiter.wait(Id=ChangeInfoID)
                except Exception as e:
                    click.echo("    Error: [{}]".format(e))

    def remove(self, host, zone):
        response = self.route53.list_hosted_zones_by_name(DNSName=zone)
        if response['HostedZones']:
            zoneID = response['HostedZones'][0]['Id']
            fqdn = "{}.{}".format(host, zone)
            ip = None
            record_set = self.route53.list_resource_record_sets(HostedZoneId=zoneID, StartRecordName=fqdn, StartRecordType='A', MaxItems='1')
            for rs in record_set['ResourceRecordSets']:
                ip = rs['ResourceRecords'][0]['Value']

            if ip is not None:
                click.echo("  - Remove record [{}] with IP [{}]".format(fqdn, ip))
                try:
                    response = self.route53.change_resource_record_sets(
                        HostedZoneId=zoneID,
                        ChangeBatch={
                            'Comment': 'ZBuilder manages',
                            'Changes': [{
                                'Action': 'DELETE',
                                'ResourceRecordSet': {
                                    'Name': fqdn,
                                    'Type': 'A',
                                    'TTL': 300,
                                    'ResourceRecords': [{'Value': ip}]
                                }
                             }]
                        }
                    )
                except Exception as e:
                    click.echo("    Error: [{}]".format(e))
            else:
                click.echo("  - DNS record [{}] does not exist".format(fqdn))
