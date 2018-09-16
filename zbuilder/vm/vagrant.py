import os
import click
import jinja2
import shutil

from zbuilder.helpers import runCmd


class vmProvider(object):

    def __init__(self, state, dns):
        self.state = state
        self.dns = dns


    def _cmd(self, hosts, cmd):
        self.setVagrantfile(pubkey=self.state.vars["ZBUILDER_PUBKEY"], hosts=hosts)
        for h in hosts:
            if hosts[h]['enabled']:
                click.echo("  - Host: {}".format(h))
                status = runCmd(cmd.format(host=h), verbose=self.state.verbose)


    def build(self, hosts):
        self._cmd(hosts, 'vagrant up {host}')


    def up(self, hosts):
        self._cmd(hosts, 'vagrant up {host}')


    def halt(self, hosts):
        self._cmd(hosts, 'vagrant halt {host}')


    def destroy(self, hosts):
        self._cmd(hosts, 'vagrant destroy --force {host}')


    def snapCreate(self, hosts):
        self._cmd(hosts, 'vagrant snapshot save {host} zbuilder --force')


    def snapRestore(self, hosts):
        click.echo("  Halting")
        self._cmd(hosts, 'vagrant halt {host}')
        click.echo("  Restoring")
        self._cmd(hosts, 'vboxmanage snapshot {host} restore zbuilder')
        click.echo("  Booting up")
        self._cmd(hosts, 'vboxmanage startvm {host} --type headless')


    def snapDelete(self, hosts):
        self._cmd(hosts, 'vagrant snapshot delete {host} zbuilder')


    def setVagrantfile(self, pubkey, hosts):
        this_dir, this_filename = os.path.split(__file__)
        ASSETS_DIR = os.path.join(this_dir, '..', 'assets', 'vagrant')

        templateLoader = jinja2.FileSystemLoader(searchpath=ASSETS_DIR)
        templateEnv = jinja2.Environment(loader=templateLoader, trim_blocks=True)
        template = templateEnv.get_template('Vagrant.j2')
        outputText = template.render(pubkey=pubkey, hosts=hosts)

        f = open('Vagrantfile', 'w')
        f.write(outputText)
        f.close()
