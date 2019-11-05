import time
import click
import importlib
import dns.resolver

from zbuilder.wrappers import trywrap


def waitDNS(hostname, ip):
    synced = False
    while not synced:
        try:
            answers = dns.resolver.query(hostname, 'A')
            ttl = answers.rrset.ttl
            rip = answers[0].address
            if rip == ip:
                click.echo("  - Host [{}] is synced with ip [{}]".format(hostname, rip))
                synced = True
            else:
                click.echo("  - Host [{}] is not synced with ip [{} != {}], sleeping for [{}]".format(hostname, ip, rip, ttl+1))
                time.sleep(ttl + 1)
        except dns.resolver.NXDOMAIN:
            time.sleep(20)
        except Exception as e:
            click.echo(e)


class dnsProvider(object):

    def __init__(self, factory, state):
        if factory is None:
            return None
        self.factory = factory
        dnsProviderClass = getattr(importlib.import_module("zbuilder.dns.%s" % factory), "dnsProvider")
        self.provider = dnsProviderClass(state)

    @trywrap
    def update(self, ips):
        self.provider.update(ips)
        for hostname, ip in ips.items():
            waitDNS(hostname, ip)

    @trywrap
    def remove(self, hosts):
        self.provider.remove(hosts)
