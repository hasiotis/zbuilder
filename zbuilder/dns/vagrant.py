import os
import click
import jinja2
import shutil

from zbuilder.helpers import runCmd


class dnsProvider(object):

    def __init__(self, state, creds=None):
        self.state = state
        self.creds = creds


    def action(self, hosts):
        self._cmd(hosts, 'vagrant snapshot delete {host} zbuilder')
