"""GCP DNS provider.

Like the gcp vm provider, the google client stack is an optional extra
(`zbuilder[gcp]`) imported lazily, so this module imports without it.
"""

import time
import click


from zbuilder.base import DNSProvider
from zbuilder.vm.gcp import auth, require

try:
    from google.cloud import dns
except ImportError:  # installed without the gcp extra
    dns = None


DNS_TTL = 60 * 10  # 10 mins


class dnsProvider(DNSProvider):
    def __init__(self, cfg):
        super().__init__(cfg)
        if cfg:
            require(dns, "google-cloud-dns")
            creds = auth(self.cfg)

            try:
                if "project" in cfg["dns"]:
                    self.dns = dns.Client(project=self.cfg["dns"]["project"], credentials=creds)
                else:
                    self.dns = dns.Client(credentials=creds)
            except Exception as e:
                click.echo("Login failed: [{}]".format(e))
                raise click.Abort()

    def _getZoneInfo(self, host, zone):
        zones = self.dns.list_zones()
        mzone = None
        for z in zones:
            if z.dns_name == zone + ".":
                mzone = z
                break

        return mzone

    def update(self, host, zone, ip):
        mzone = self._getZoneInfo(host, zone)
        try:
            changes = mzone.changes()
            changes.delete_record_set(mzone.resource_record_set("{}.{}.".format(host, zone), "A", DNS_TTL, [ip]))
            changes.create()
            while changes.status != "done":
                time.sleep(5)
                changes.reload()
            click.echo("  - Updating record [{}.{}] with ip [{}]".format(host, zone, ip))
        except Exception:
            click.echo("  - Creating record [{}.{}] with ip [{}]".format(host, zone, ip))

        changes = mzone.changes()
        changes.add_record_set(mzone.resource_record_set("{}.{}.".format(host, zone), "A", DNS_TTL, [ip]))
        changes.create()
        while changes.status != "done":
            time.sleep(5)
            changes.reload()
        time.sleep(5)

    def remove(self, host, zone):
        mzone = self._getZoneInfo(host, zone)
        records = mzone.list_resource_record_sets()
        found = False
        for r in records:
            if r.name == "{}.{}.".format(host, zone) and r.record_type in [
                "A",
                "CNAME",
            ]:
                found = True
                click.echo("  - Removing record [{}.{}]".format(host, zone))
                changes = mzone.changes()
                changes.delete_record_set(mzone.resource_record_set(r.name, r.record_type, r.ttl, r.rrdatas))
                changes.create()
                while changes.status != "done":
                    time.sleep(5)
                    changes.reload()
                break

        if not found:
            click.echo("  - No such record [{}.{}]".format(host, zone))
