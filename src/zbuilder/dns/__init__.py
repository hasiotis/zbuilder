import time
import click
import dns.resolver

import zbuilder.cfg
import zbuilder.plugins


def waitDNS(hostname, ip):
    synced = False
    click.echo("  - Waiting for host [{}] DNS to sync".format(hostname))
    while not synced:
        try:
            answers = dns.resolver.query(hostname, "A")
            ttl = answers.rrset.ttl
            rip = answers[0].address
            if rip == ip:
                click.echo("  - Host [{}] is synced with ip [{}]".format(hostname, rip))
                synced = True
            else:
                click.echo(
                    "  - Host [{}] is not synced with ip [{} != {}], sleeping for [{}]".format(
                        hostname, ip, rip, ttl + 1
                    )
                )
                time.sleep(ttl + 1)
        except dns.resolver.NXDOMAIN:
            click.echo("    Sleeping 20s due to NXDOMAIN")
            time.sleep(20)
        except Exception as e:
            click.echo(e)
            exit()


def getProvider(zone, cfg):
    for p, v in cfg.items():
        if "dns" in v and "zones" in v["dns"] and zone == v["dns"]["zones"]:
            return dnsProvider(cfg[p]["type"], cfg[p])
    return None


def dnsUpdate(ips):
    cfg = zbuilder.cfg.load()
    waitList = {}
    provider = None
    for hostname, ip in ips.items():
        zone = hostname.partition(".")[2]
        host = hostname.partition(".")[0]
        provider = getProvider(zone, cfg["providers"])
        if provider:
            provider.update(host, zone, ip)
            waitList[hostname] = ip
        else:
            click.echo("No DNS provider found for zone [{}]".format(zone))

    if provider and provider.factory != "ansible":
        for hostname, ip in waitList.items():
            waitDNS(hostname, ip)


def dnsRemove(hosts):
    cfg = zbuilder.cfg.load()
    for hostname in hosts:
        zone = hostname.partition(".")[2]
        host = hostname.partition(".")[0]
        provider = getProvider(zone, cfg["providers"])
        if provider:
            provider.remove(host, zone)
        else:
            click.echo("No DNS provider found for zone [{}]".format(zone))


def dnsProvider(factory, cfg=None):
    """Instantiate the DNS provider registered as `factory`"""
    provider = zbuilder.plugins.load(zbuilder.plugins.DNS, factory)(cfg)
    provider.factory = factory
    return provider
