import os
import click
import importlib
import distutils.dir_util

class dnsProvider(object):

    def __init__(self, factory, state):
        if factory is None:
            return None
        cloud = state.cfg['type']
        self.factory = cloud
        dnsProviderClass = getattr(importlib.import_module("zbuilder.dns.%s" % cloud), "dnsProvider")
        self.provider = dnsProviderClass(state)


    def action(self, hosts):
        try:
            self.provider.snapDelete(hosts)
        except AttributeError as error:
            click.echo("Provider [%s] does not implement this action" % (self.factory))
