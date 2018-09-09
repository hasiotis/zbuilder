import os
import click
import jinja2
import shutil
import distutils.dir_util

from zbuilder.helpers import runCmd


class vmProvider(object):

    def __init__(self, verbose):
        self.verbose = verbose

    def init(self):
        this_dir, this_filename = os.path.split(__file__)
        ASSETS_INIT_DIR = os.path.join(this_dir, '..', 'assets', 'vagrant', 'init')

        if os.path.exists('group_vars') or os.path.exists('hosts'):
            raise click.ClickException("This directory already contains relevant files")

        click.echo("Initializing vagrant based zbuilder environment")
        distutils.dir_util.copy_tree(ASSETS_INIT_DIR, os.getcwd())


    def _cmd(self, hosts, cmd):
        self.setVagrantfile(pubkey='~/.ssh/id_rsa.pub', hosts=hosts)
        for h in hosts:
            if hosts[h]['enabled']:
                click.echo("  - Host: {}".format(h))
                status = runCmd(cmd.format(host=h), verbose=self.verbose)


    def up(self, hosts):
        self._cmd(hosts, 'vagrant up {host}')


    def halt(self, hosts):
        self._cmd(hosts, 'vagrant halt {host}')


    def destroy(self, hosts):
        self._cmd(hosts, 'vagrant destroy --force {host}')


    def snapCreate(self, hosts):
        self._cmd(hosts, 'vagrant snapshot save {host} zbuilder --force')


    def snapRestore(self, hosts):
        self._cmd(hosts, 'vagrant halt {host}')
        self._cmd(hosts, 'vboxmanage snapshot {host} restore zbuilder')
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
