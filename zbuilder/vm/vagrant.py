import os
import click
import jinja2

from zbuilder import getAssetsDir
from zbuilder.helpers import runCmd


class vmProvider(object):
    def __init__(self, cfg):
        self.cfg = cfg

    def _cmd(self, hosts, cmd):
        self.setVagrantfile(pubkey=self.cfg['state'].vars["ZBUILDER_PUBKEY"], hosts=hosts)
        for h in hosts:
            if hosts[h]['enabled']:
                click.echo("  - Host: {}".format(h))
                runCmd(cmd.format(host=h), verbose=self.cfg['state'].verbose)

    def build(self, hosts):
        self._cmd(hosts, 'vagrant up {host}')

    def up(self, hosts):
        self._cmd(hosts, 'vagrant up {host}')

    def halt(self, hosts):
        self._cmd(hosts, 'vagrant halt {host}')

    def destroy(self, hosts):
        self._cmd(hosts, 'vagrant destroy --force {host}')

    def dnsupdate(self, hosts):
        self._cmd(hosts, 'vagrant hostmanager {host}')

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

    def params(self, params):
        if 'disks' in params.keys():
            return {k: params[k] for k in ['box', 'vcpus', 'memory', 'disks']}
        else:
            return {k: params[k] for k in ['box', 'vcpus', 'memory']}

    def setVagrantfile(self, pubkey, hosts):
        ASSETS_DIR = os.path.join(getAssetsDir(), 'vagrant')

        templateLoader = jinja2.FileSystemLoader(searchpath=ASSETS_DIR)
        templateEnv = jinja2.Environment(loader=templateLoader, trim_blocks=True)
        template = templateEnv.get_template('Vagrant.j2')
        privkey = pubkey
        if privkey.endswith('.pub'):
            privkey = privkey[:-4]

        outputText = template.render(privkey=privkey, pubkey=pubkey, hosts=hosts)

        f = open('Vagrantfile', 'w')
        f.write(outputText)
        f.close()
