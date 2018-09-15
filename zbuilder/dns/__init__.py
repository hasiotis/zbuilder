import os
import click
import importlib
import distutils.dir_util

class dnsProvider(object):

    def __init__(self, factory, state):
        if factory is None:
            return None
        self.factory = factory
        dnsProviderClass = getattr(importlib.import_module("zbuilder.dns.%s" % factory), "dnsProvider")
        self.provider = dnsProviderClass(state)


    def update(self, ips):
        try:
            self.provider.update(ips)
        except AttributeError as error:
            click.echo("Provider [%s] does not implement this action" % (self.factory))
        except Exception as e:
            click.echo("Provider [%s] failed with [%s]" % (self.factory, e))


    def remove(self, hosts):
        try:
            self.provider.remove(hosts)
        except AttributeError as error:
            click.echo("Provider [%s] does not implement this action" % (self.factory))
        except Exception as e:
            click.echo("Provider [%s] failed with [%s]" % (self.factory, e))

