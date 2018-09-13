import os
import click
import importlib
import zbuilder.dns
import distutils.dir_util

class vmProvider(object):

    def __init__(self, factory, state, dns):
        cloud = state.cfg['type']
        self.factory = cloud
        vmProviderClass = getattr(importlib.import_module("zbuilder.vm.%s" % cloud), "vmProvider")
        curDNS = None
        if dns:
            curDNS = zbuilder.dns.dnsProvider(dns, state)
        self.provider = vmProviderClass(state, curDNS)

    def init(self):
        this_dir, this_filename = os.path.split(__file__)
        ASSETS_INIT_DIR = os.path.join(this_dir, '..', 'assets', self.factory, 'init')

        if os.path.exists('group_vars') or os.path.exists('hosts'):
            raise click.ClickException("This directory already contains relevant files")

        click.echo("Initializing {} based zbuilder environment".format(self.factory))
        distutils.dir_util.copy_tree(ASSETS_INIT_DIR, os.getcwd())


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
