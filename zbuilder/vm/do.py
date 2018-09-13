import click
import digitalocean


class vmProvider(object):

    def __init__(self, state, dns, creds=None):
        self.state = state
        self.dns = dns


    def up(self, hosts):
        pubkey = self.state.vars["ZBUILDER_PUBKEY"]
        for h in hosts:
            if hosts[h]['enabled']:
                click.echo("  - Host: {}".format(h))
                click.echo(hosts[h])
        from zbuilder.helpers import dump_yaml
        dump_yaml(self.state.cfg)
        exit(0)
        manager = digitalocean.Manager(token="secretspecialuniquesnowflake")
        my_droplets = manager.get_all_droplets()
        pass


    def halt(self, hosts):
        pass


    def destroy(self, hosts):
        pass


    def snapCreate(self, hosts):
        pass


    def snapRestore(self, hosts):
        click.echo("  Halting")
        click.echo("  Restoring")
        click.echo("  Booting up")


    def snapDelete(self, hosts):
        pass
