import click
import digitalocean


class dnsProvider(object):

    def __init__(self, state):
        self.state = state
        self.token = self.state.dnsConfig['token']
        self.manager = digitalocean.Manager(token=self.token)


    def getRecords(self, ips):
        retValue = {}
        for fqdn, ip in ips.items():
            (shortname, _, domain) = fqdn.partition('.')
            doDomain = self.manager.get_domain(domain)
            for record in doDomain.get_records():
                if shortname == record.name:
                    retValue[fqdn] = record
                    continue
            if fqdn not in retValue:
                record = digitalocean.Record(
                    token = self.token,
                    domain_name = domain,
                    name = shortname,
                    type = 'A',
                    data = ip
                )
                retValue[fqdn] = record

        return retValue

    def update(self, ips):
        for fqdn, record  in self.getRecords(ips).items():
            if not record.id:
                click.echo("  - Creating record {}".format(fqdn))
                record.create()
            else:
                click.echo("  - Updating record {}".format(fqdn))
                record.save()


    def remove(self, hosts):
        for fqdn, record  in self.getRecords(hosts).items():
            if record.id:
                click.echo("  - Removing record {}".format(fqdn))
                record.destroy()
            else:
                click.echo("  - No such record {}".format(fqdn))
