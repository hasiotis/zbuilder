import click
import requests


class dnsProvider(object):
    def __init__(self, cfg):
        if cfg:
            self.cfg = cfg
            self.apikey = self.cfg['apikey']
            self.url = self.cfg['url'] + 'api/v1'

    def _get_record(self, fqdn):
        uri = "{}/servers/localhost/search-data".format(self.url)
        params = {'q': fqdn, 'object-type': 'record',  'max': 1}
        r = requests.get(uri, params=params, headers={'X-API-Key': self.apikey})
        if r.status_code == 404:
            return None
        else:
            return r.json()

    def update(self, host, zone, ip):
        fqdn = "{}.{}".format(host, zone)
        r = self._get_record(fqdn)

        uri = "{}/servers/localhost/zones/{}".format(self.url, zone)
        payload = {"rrsets": [{
            "name": fqdn + ".",
            "type": "A",
            "ttl": 300,
            "changetype": "REPLACE",
            "records": [{"content": ip, "disabled": False}]
        }]}

        if not r:
            click.echo("  - Creating record [{}] with ip [{}]".format(fqdn, ip))
        else:
            click.echo("  - Updating record [{}] with ip [{}]".format(fqdn, ip))
        r = requests.patch(uri, json=payload, headers={'X-API-Key': self.apikey})

    def remove(self, host, zone):
        fqdn = "{}.{}".format(host, zone)
        r = self._get_record(fqdn)

        uri = "{}/servers/localhost/zones/{}".format(self.url, zone)
        payload = {"rrsets": [{
            "name": fqdn + ".",
            "type": "A",
            "ttl": 300,
            "changetype": "DELETE",
        }]}

        if r:
            click.echo("  - Removing record {}".format(fqdn))
            r = requests.patch(uri, json=payload, headers={'X-API-Key': self.apikey})
        else:
            click.echo("  - No such record {}".format(fqdn))

    def config(self):
        return "url: {v[url]}".format(v=self.cfg)

    def status(self):
        return 'PASS'
