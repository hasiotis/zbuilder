import time
import click

from google.cloud import dns

DNS_TTL = 60 * 10 # 10 mins


class dnsProvider(object):

    def __init__(self, state):
        self.state = state
        self.dns = dns.Client(project="zbuilder-devel")

    def _getZoneInfo(self, hostname):
        zone = hostname.partition('.')[2]
        host = hostname.partition('.')[0]
        zones = self.dns.list_zones()
        mzone = None
        for z in zones:
            if z.dns_name == zone + '.':
                mzone = z
                break

        return(zone, host, mzone)


    def update(self, ips):
        for hostname, ip in ips.items():
            (zone, host, mzone) = self._getZoneInfo(hostname)

            try:
                changes = mzone.changes()
                changes.delete_record_set(mzone.resource_record_set(hostname + '.', 'A', DNS_TTL, [ip]))
                changes.create()
                while changes.status != 'done':
                    time.sleep(5)
                    changes.reload()
                click.echo("  - Updating record [{}] with ip [{}]".format(hostname, ip))
            except Exception as e:
                click.echo("  - Creating record [{}] with ip [{}]".format(hostname, ip))

            changes = mzone.changes()
            changes.add_record_set(mzone.resource_record_set(hostname + '.', 'A', DNS_TTL, [ip]))
            changes.create()
            while changes.status != 'done':
                time.sleep(5)
                changes.reload()
            time.sleep(5)

    def remove(self, hosts):
        for h in hosts:
            (zone, host, mzone) = self._getZoneInfo(h)
            records = mzone.list_resource_record_sets()
            found = False
            for r in records:
                if r.name == h + '.' and r.record_type in ['A', 'CNAME']:
                    found = True
                    click.echo("  - Removing record [{}]".format(h))
                    changes = mzone.changes()
                    changes.delete_record_set(mzone.resource_record_set(r.name, r.record_type, r.ttl, r.rrdatas))
                    changes.create()
                    while changes.status != 'done':
                        time.sleep(5)
                        changes.reload()
                    break

            if not found:
                click.echo("  - No such record [{}]".format(h))
