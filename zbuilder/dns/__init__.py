import os
import click
import importlib
import distutils.dir_util

from zbuilder.wrappers import trywrap


class dnsProvider(object):

    def __init__(self, factory, state):
        if factory is None:
            return None
        self.factory = factory
        dnsProviderClass = getattr(importlib.import_module("zbuilder.dns.%s" % factory), "dnsProvider")
        self.provider = dnsProviderClass(state)


    @trywrap
    def update(self, ips):
        self.provider.update(ips)


    @trywrap
    def remove(self, hosts):
        self.provider.remove(hosts)

