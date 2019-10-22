import click

from azure.common.credentials import ServicePrincipalCredentials
from azure.mgmt.dns import DnsManagementClient
from msrestazure.tools import parse_resource_id


class dnsProvider(object):

    def __init__(self, state):
        self.state = state
        self.credentials = ServicePrincipalCredentials(
            client_id=state.dnsConfig['client_id'],
            secret=state.dnsConfig['client_secret'],
            tenant=state.dnsConfig['tenant_id']
        )
        self.dnsClient = DnsManagementClient(self.credentials, state.dnsConfig['subscription_id'])

    def _getZoneInfo(self, hostname):
        zone = hostname.partition('.')[2]
        host = hostname.partition('.')[0]
        zones = self.dnsClient.zones.list()
        rgroup = None
        for z in zones:
            zoneInfo = parse_resource_id(z.id)
            if z.name == zone:
                rgroup = zoneInfo['resource_group']
                break
        return(zone, host, rgroup)

    def update(self, ips):
        for hostname, ip in ips.items():
            (zone, host, rgroup) = self._getZoneInfo(hostname)
            if not rgroup:
                click.echo("  - Error: Zone not found [{}]".format(zone))
                next
            click.echo("  - Updating record [{}] with ip [{}]".format(hostname, ip))
            self.dnsClient.record_sets.create_or_update(
                rgroup, zone, host, 'A',
                {"ttl": 300, "arecords": [{"ipv4_address": ip}]}
            )

    def remove(self, hosts):
        for hostname in hosts:
            (zone, host, rgroup) = self._getZoneInfo(hostname)
            if not rgroup:
                click.echo("  - Error: Zone not found [{}]".format(zone))
                next
            click.echo("  - Removing record [{}]".format(hostname))
            self.dnsClient.record_sets.delete(rgroup, zone, host, 'A')
