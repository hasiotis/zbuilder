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
            self.keyring = dns.tsigkeyring.from_text({self.keyname: self.keysecret})

    def update(self, host, zone, ip):
        fqdn = "{}.{}".format(host, zone)
        click.echo("  - Creating/Updating record [{}] with ip [{}]".format(fqdn, ip))
        update = dns.update.Update(zone, keyring=self.keyring)
        update.replace(host, 300, 'a', str(ip))
        response = dns.query.tcp(update, self.server)
        if response.rcode():
            err = dns.rcode.to_text(response.rcode())
            click.echo("      Failed to add DNS record: [%s]" % (err))

    def remove(self, host, zone):
        fqdn = "{}.{}".format(host, zone)
        click.echo("  - Removing record {}".format(fqdn))
        update = dns.update.Update(zone, keyring=self.keyring)
        update.delete(host)
        response = dns.query.tcp(update, self.server)
        if response.rcode():
            err = dns.rcode.to_text(response.rcode())
            click.echo("      Failed to remove DNS record: [%s]" % (err))

    def config(self):
        return "server: {}, keyname: {}".format(self.server, self.keyname)

    def status(self):
        return 'PASS'
