import click
import requests

from zbuilder.base import DNSProvider


class dnsProvider(DNSProvider):
    def __init__(self, cfg):
        super().__init__(cfg)
        if cfg:
            self.apikey = self.cfg["apikey"]
            self.url = self.cfg["url"] + "api/v1"

    def _get_record(self, fqdn):
        uri = f"{self.url}/servers/localhost/search-data"
        params = {"q": fqdn, "object-type": "record", "max": 1}
        r = requests.get(uri, params=params, headers={"X-API-Key": self.apikey})
        if r.status_code == 404:
            return None
        else:
            return r.json()

    def update(self, host, zone, ip):
        fqdn = f"{host}.{zone}"
        r = self._get_record(fqdn)

        uri = f"{self.url}/servers/localhost/zones/{zone}"
        payload = {
            "rrsets": [
                {
                    "name": fqdn + ".",
                    "type": "A",
                    "ttl": 300,
                    "changetype": "REPLACE",
                    "records": [{"content": ip, "disabled": False}],
                }
            ]
        }

        if not r:
            click.echo(f"  - Creating record [{fqdn}] with ip [{ip}]")
        else:
            click.echo(f"  - Updating record [{fqdn}] with ip [{ip}]")

        r = requests.patch(uri, json=payload, headers={"X-API-Key": self.apikey})

    def remove(self, host, zone):
        fqdn = f"{host}.{zone}"
        r = self._get_record(fqdn)

        uri = f"{self.url}/servers/localhost/zones/{zone}"
        payload = {
            "rrsets": [
                {
                    "name": fqdn + ".",
                    "type": "A",
                    "ttl": 300,
                    "changetype": "DELETE",
                }
            ]
        }

        if r:
            click.echo(f"  - Removing record {fqdn}")
            r = requests.patch(uri, json=payload, headers={"X-API-Key": self.apikey})
        else:
            click.echo(f"  - No such record {fqdn}")

    def config(self):
        return f"url: {self.cfg['url']}"

    def status(self):
        return "PASS"
