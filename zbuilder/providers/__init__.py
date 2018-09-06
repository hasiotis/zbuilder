import click
import importlib

class vmProvider(object):

    def __init__(self, factory, verbose):
        self.factory = factory
        self.verbose = verbose
        vmProviderClass = getattr(importlib.import_module("zbuilder.providers.%s" % factory), "vmProvider")
        self.provider = vmProviderClass(verbose)

    def init(self):
        try:
            self.provider.init()
        except AttributeError as error:
            click.echo("Provider [%s] does not implement this action" % (self.factory))


    def up(self, hosts):
        try:
            self.provider.up(hosts)
        except AttributeError as error:
            click.echo("Provider [%s] does not implement this action" % (self.factory))


    def halt(self, hosts):
        try:
            self.provider.halt(hosts)
        except AttributeError as error:
            click.echo("Provider [%s] does not implement this action" % (self.factory))


    def destroy(self, hosts):
        try:
            self.provider.destroy(hosts)
        except AttributeError as error:
            click.echo("Provider [%s] does not implement this action" % (self.factory))

    def snapCreate(self, hosts):
        try:
            self.provider.snapCreate(hosts)
        except AttributeError as error:
            click.echo("Provider [%s] does not implement this action" % (self.factory))

    def snapRestore(self, hosts):
        try:
            self.provider.snapRestore(hosts)
        except AttributeError as error:
            click.echo("Provider [%s] does not implement this action" % (self.factory))


    def snapDelete(self, hosts):
        try:
            self.provider.snapDelete(hosts)
        except AttributeError as error:
            click.echo("Provider [%s] does not implement this action" % (self.factory))
