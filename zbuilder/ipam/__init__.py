import click
import importlib

import zbuilder.cfg
from zbuilder.wrappers import trywrap


def getProvider(subnet, cfg):
    for p, v in cfg.items():
        if 'ipam' in v and 'subnets' in v['ipam'] and subnet in v['ipam']['subnets']:
            return ipamProvider(cfg[p]['type'], cfg[p])
    return None


def ipamReserve(hostname, subnet):
    cfg = zbuilder.cfg.load()
    provider = getProvider(subnet, cfg['providers'])
    if provider:
        return provider.reserve(hostname, subnet)
    else:
        click.echo("No IPAM provider found for subnet [{}]".format(subnet))


def ipamLocate(hostname, subnet):
    cfg = zbuilder.cfg.load()
    provider = getProvider(subnet, cfg['providers'])
    if provider:
        return provider.locate(hostname, subnet)
    else:
        click.echo("No IPAM provider found for subnet [{}]".format(subnet))


def ipamRelease(hostname, ip, subnet):
    cfg = zbuilder.cfg.load()
    provider = getProvider(subnet, cfg['providers'])
    if provider:
        provider.release(hostname, ip, subnet)
    else:
        click.echo("No IPAM provider found for subnet [{}]".format(subnet))


class ipamProvider(object):
    def __init__(self, factory, cfg=None):
        self.factory = factory
        self.cfg = cfg
        ipamProviderClass = getattr(importlib.import_module("zbuilder.ipam.%s" % factory), "ipamProvider")
        self.provider = ipamProviderClass(cfg)

    @trywrap
    def release(self, host, ip, subnet):
        self.provider.release(host, ip, subnet)

    @trywrap
    def locate(self, host, subnet):
        return self.provider.locate(host, subnet)

    @trywrap
    def reserve(self, host, subnet):
        return self.provider.reserve(host, subnet)

    @trywrap
    def config(self):
        return self.provider.config()

    @trywrap
    def status(self):
        return self.provider.status()
