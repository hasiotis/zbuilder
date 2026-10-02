import click

import zbuilder.cfg
import zbuilder.plugins


def getProvider(subnet, cfg):
    for v in cfg.values():
        if "ipam" in v and "subnets" in v["ipam"] and subnet in v["ipam"]["subnets"]:
            return ipamProvider(v["type"], v)
    return None


def ipamReserve(hostname, subnet):
    cfg = zbuilder.cfg.load()
    provider = getProvider(subnet, cfg["providers"])
    if provider:
        return provider.reserve(hostname, subnet)
    else:
        click.echo(f"No IPAM provider found for subnet [{subnet}]")


def ipamLocate(hostname, subnet):
    cfg = zbuilder.cfg.load()
    provider = getProvider(subnet, cfg["providers"])
    if provider:
        return provider.locate(hostname, subnet)
    else:
        click.echo(f"No IPAM provider found for subnet [{subnet}]")


def ipamRelease(hostname, ip, subnet):
    cfg = zbuilder.cfg.load()
    provider = getProvider(subnet, cfg["providers"])
    if provider:
        provider.release(hostname, ip, subnet)
    else:
        click.echo(f"No IPAM provider found for subnet [{subnet}]")


def ipamProvider(factory, cfg=None):
    """Instantiate the IPAM provider registered as `factory`"""
    provider = zbuilder.plugins.load(zbuilder.plugins.IPAM, factory)(cfg)
    provider.factory = factory
    return provider
