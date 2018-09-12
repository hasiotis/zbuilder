import click
import digitalocean


class dnsProvider(object):

    def __init__(self, state, creds=None):
        self.state = state
        self.creds = creds


    def action(self, hosts):
        pass
