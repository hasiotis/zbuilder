import boto3
import click
from botocore.exceptions import BotoCoreError, ClientError

from zbuilder.base import DNSProvider


class dnsProvider(DNSProvider):
    def __init__(self, cfg):
        super().__init__(cfg)
        if cfg:
            if "aws_access_key_id" in cfg and "aws_secret_access_key" in cfg:
                self.route53 = boto3.client(
                    "route53",
                    aws_access_key_id=cfg["aws_access_key_id"],
                    aws_secret_access_key=cfg["aws_secret_access_key"],
                )
            else:
                self.route53 = boto3.client("route53")

    def update(self, host, zone, ip):
        response = self.route53.list_hosted_zones_by_name(DNSName=zone)
        if response["HostedZones"]:
            zoneID = response["HostedZones"][0]["Id"]
            fqdn = f"{host}.{zone}"
            click.echo(f"  - Update record [{fqdn}] with ip [{ip}]")

            oldIP = None
            record_set = self.route53.list_resource_record_sets(
                HostedZoneId=zoneID,
                StartRecordName=fqdn,
                StartRecordType="A",
                MaxItems="1",
            )
            for rs in record_set["ResourceRecordSets"]:
                oldIP = rs["ResourceRecords"][0]["Value"]

            if oldIP != ip:
                try:
                    response = self.route53.change_resource_record_sets(
                        HostedZoneId=zoneID,
                        ChangeBatch={
                            "Comment": "ZBuilder manages",
                            "Changes": [
                                {
                                    "Action": "UPSERT",
                                    "ResourceRecordSet": {
                                        "Name": fqdn,
                                        "Type": "A",
                                        "TTL": 300,
                                        "ResourceRecords": [{"Value": ip}],
                                    },
                                }
                            ],
                        },
                    )
                    if "ChangeInfo" in response:
                        ChangeInfoID = response["ChangeInfo"]["Id"]
                        waiter = self.route53.get_waiter("resource_record_sets_changed")
                        waiter.wait(Id=ChangeInfoID)
                except (BotoCoreError, ClientError) as e:
                    click.echo(f"    Error: [{e}]")

    def remove(self, host, zone):
        response = self.route53.list_hosted_zones_by_name(DNSName=zone)
        if response["HostedZones"]:
            zoneID = response["HostedZones"][0]["Id"]
            fqdn = f"{host}.{zone}"
            ip = None
            record_set = self.route53.list_resource_record_sets(
                HostedZoneId=zoneID,
                StartRecordName=fqdn,
                StartRecordType="A",
                MaxItems="1",
            )
            for rs in record_set["ResourceRecordSets"]:
                ip = rs["ResourceRecords"][0]["Value"]

            if ip is not None:
                click.echo(f"  - Remove record [{fqdn}] with IP [{ip}]")
                try:
                    response = self.route53.change_resource_record_sets(
                        HostedZoneId=zoneID,
                        ChangeBatch={
                            "Comment": "ZBuilder manages",
                            "Changes": [
                                {
                                    "Action": "DELETE",
                                    "ResourceRecordSet": {
                                        "Name": fqdn,
                                        "Type": "A",
                                        "TTL": 300,
                                        "ResourceRecords": [{"Value": ip}],
                                    },
                                }
                            ],
                        },
                    )
                except (BotoCoreError, ClientError) as e:
                    click.echo(f"    Error: [{e}]")
            else:
                click.echo(f"  - DNS record [{fqdn}] does not exist")
