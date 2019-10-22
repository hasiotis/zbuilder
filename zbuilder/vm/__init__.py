import os
import click
import importlib
import zbuilder
import zbuilder.dns
import distutils.dir_util

from zbuilder import getAssetsDir
from zbuilder.wrappers import trywrap


class vmProvider(object):

    def __init__(self, factory, state):
        cloud = state.vmConfig['type']
        self.factory = cloud
        vmProviderClass = getattr(importlib.import_module("zbuilder.vm.%s" % cloud), "vmProvider")

        curDNS = None
        if state.dnsConfig:
            dns = state.dnsConfig['type']
            curDNS = zbuilder.dns.dnsProvider(dns, state)

        self.provider = vmProviderClass(state, curDNS)

    def init(self):
        ASSETS_DIR = getAssetsDir()

        if os.path.exists('group_vars') or os.path.exists('hosts'):
            raise click.ClickException("This directory already contains relevant files")

        click.echo("Initializing {} based zbuilder environment".format(self.factory))
        distutils.dir_util.copy_tree(ASSETS_DIR, os.getcwd())

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
