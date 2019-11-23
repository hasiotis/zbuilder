import click

from azure.common.credentials import ServicePrincipalCredentials
from azure.mgmt.dns import DnsManagementClient
from msrestazure.tools import parse_resource_id


class dnsProvider(object):
    def __init__(self, cfg):
        if cfg:
            self.credentials = ServicePrincipalCredentials(
                client_id=cfg['client_id'],
                secret=cfg['client_secret'],
                tenant=cfg['tenant_id']
            )
        self.dnsClient = DnsManagementClient(self.credentials, cfg['subscription_id'])

    def _getZoneInfo(self, host, zone):
        rgroup = None

        zones = self.dnsClient.zones.list()
        for z in zones:
            zoneInfo = parse_resource_id(z.id)
            if z.name == zone:
                rgroup = zoneInfo['resource_group']
                break

        return rgroup

    def update(self, host, zone, ip):
        fqdn = "{}.{}".format(host, zone)
        rgroup = self._getZoneInfo(host, zone)
        if not rgroup:
            click.echo("  - Error: Zone not found [{}]".format(zone))
        else:
            click.echo("  - Updating record [{}] with ip [{}]".format(fqdn, ip))
            self.dnsClient.record_sets.create_or_update(
                rgroup, zone, host, 'A', {"ttl": 300, "arecords": [{"ipv4_address": ip}]}
            )

    def remove(self, host, zone):
        fqdn = "{}.{}".format(host, zone)
        rgroup = self._getZoneInfo(host, zone)
        if not rgroup:
            click.echo("  - Error: Zone not found [{}]".format(zone))
        else:
            click.echo("  - Removing record [{}]".format(fqdn))
            self.dnsClient.record_sets.delete(rgroup, zone, host, 'A')
