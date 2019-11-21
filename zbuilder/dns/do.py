import click
import digitalocean


class dnsProvider(object):
    def __init__(self, cfg):
        if cfg:
            self.cfg = cfg
            self.apikey = self.cfg['apikey']
            self.manager = digitalocean.Manager(token=self.apikey)

    def getRecord(self, host, zone, ip=None):
        retValue = None

        doDomain = self.manager.get_domain(zone)
        for record in doDomain.get_records():
            if host == record.name:
                retValue = record
                continue

        if ip and not retValue:
            retValue = digitalocean.Record(token=self.apikey, domain_name=zone, name=host, type='A', data=ip)

        return retValue

    def update(self, host, zone, ip):
        fqdn = "{}.{}".format(host, zone)
        record = self.getRecord(host, zone, ip)
        if not record.id:
            click.echo("  - Creating record [{}] with ip [{}]".format(fqdn, record.data))
            record.create()
        else:
            click.echo("  - Updating record [{}] with ip [{}]".format(fqdn, record.data))
            record.save()

    def remove(self, host, zone):
        fqdn = "{}.{}".format(host, zone)
        record = self.getRecord(host, zone)
        if record:
            click.echo("  - Removing record {}".format(fqdn))
            record.destroy()
        else:
            click.echo("  - No such record {}".format(fqdn))
