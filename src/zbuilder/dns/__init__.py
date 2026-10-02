import time

import click
import dns.exception
import dns.resolver

import zbuilder.cfg
import zbuilder.plugins


def waitDNS(hostname, ip):
    synced = False
    click.echo(f"  - Waiting for host [{hostname}] DNS to sync")
    while not synced:
        try:
            answers = dns.resolver.query(hostname, "A")
            ttl = answers.rrset.ttl
            rip = answers[0].address
            if rip == ip:
                click.echo(f"  - Host [{hostname}] is synced with ip [{rip}]")
                synced = True
            else:
                click.echo(f"  - Host [{hostname}] is not synced with ip [{ip} != {rip}], sleeping for [{ttl + 1}]")
                time.sleep(ttl + 1)
        except dns.resolver.NXDOMAIN:
            click.echo("    Sleeping 20s due to NXDOMAIN")
            time.sleep(20)
        except dns.exception.DNSException as e:
            raise click.ClickException(str(e)) from e


def getProvider(zone, cfg):
    for v in cfg.values():
        if "dns" in v and "zones" in v["dns"] and zone == v["dns"]["zones"]:
            return dnsProvider(v["type"], v)
    return None


def dnsUpdate(ips):
    cfg = zbuilder.cfg.load()
    waitList = {}
    for hostname, ip in ips.items():
        zone = hostname.partition(".")[2]
        host = hostname.partition(".")[0]
        provider = getProvider(zone, cfg["providers"])
        if provider:
            provider.update(host, zone, ip)
            waitList[hostname] = ip
        else:
            click.echo(f"No DNS provider found for zone [{zone}]")

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
            click.echo(f"No DNS provider found for zone [{zone}]")


def dnsProvider(factory, cfg=None):
    """Instantiate the DNS provider registered as `factory`"""
    provider = zbuilder.plugins.load(zbuilder.plugins.DNS, factory)(cfg)
    provider.factory = factory
    return provider
