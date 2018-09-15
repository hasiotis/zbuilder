import os
import click
import jinja2
import shutil

from zbuilder.helpers import runCmd


class dnsProvider(object):

    def __init__(self, state):
        self.state = state


    def update(self, ips):
        pass


    def remove(self, hosts):
        pass
