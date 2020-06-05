import click
import dns.query
import dns.tsigkeyring
import dns.update


class dnsProvider(object):
    def __init__(self, cfg):
        if cfg:
            self.cfg = cfg
            self.keyname = cfg['keyname']
            self.keysecret = cfg['keysecret']
            self.server = cfg['server']
            if not isinstance(cfg['server'], list):
                self.server = [cfg['server']]
            self.keyring = dns.tsigkeyring.from_text({self.keyname: self.keysecret})

    def _dns_query(self, update):
        for srv in self.server:
            response = dns.query.tcp(update, srv)
            if response.rcode():
                err = dns.rcode.to_text(response.rcode())
                click.echo("      Failed to update DNS record [{}] on server [{}]".format(err, srv))

    def update(self, host, zone, ip):
        if ip is None:
            click.echo("  - Skipping due to empty ip")
            return
        fqdn = "{}.{}".format(host, zone)
        click.echo("  - Creating/Updating record [{}] with ip [{}]".format(fqdn, ip))
        update = dns.update.Update(zone, keyring=self.keyring)
        update.replace(host, 300, 'a', str(ip))
        self._dns_query(update)

    def remove(self, host, zone):
        fqdn = "{}.{}".format(host, zone)
        click.echo("  - Removing record {}".format(fqdn))
        update = dns.update.Update(zone, keyring=self.keyring)
        update.delete(host)
        self._dns_query(update)

    def config(self):
        return "server: {}, keyname: {}".format(self.server, self.keyname)

    def status(self):
        return 'PASS'
