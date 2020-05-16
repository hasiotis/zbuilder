import os
import click
import importlib

from zbuilder.wrappers import trywrap


class vmProvider(object):
    def __init__(self, factory, cfg=None):
        self.factory = factory
        self.cfg = cfg
        vmProviderClass = getattr(importlib.import_module("zbuilder.vm.%s" % factory), "vmProvider")
        self.provider = vmProviderClass(cfg)

    def init(self):
        if os.path.exists('group_vars') or os.path.exists('hosts'):
            raise click.ClickException("This directory already contains relevant files")

        click.echo("Initializing {} based zbuilder environment".format(self.factory))

    @trywrap
    def build(self, hosts):
        self.provider.build(hosts)

    @trywrap
    def up(self, hosts):
        self.provider.up(hosts)

    @trywrap
    def halt(self, hosts):
        self.provider.halt(hosts)

    @trywrap
    def destroy(self, hosts):
        self.provider.destroy(hosts)

    @trywrap
    def dnsupdate(self, hosts):
        self.provider.dnsupdate(hosts)

    @trywrap
    def dnsremove(self, hosts):
        self.provider.dnsremove(hosts)

    @trywrap
    def snapCreate(self, hosts):
        self.provider.snapCreate(hosts)

    @trywrap
    def snapRestore(self, hosts):
        self.provider.snapRestore(hosts)

    @trywrap
    def snapDelete(self, hosts):
        self.provider.snapDelete(hosts)

    @trywrap
    def params(self, v):
        return self.provider.params(v)

    @trywrap
    def config(self):
        return self.provider.config()

    @trywrap
    def status(self):
        return self.provider.status()
