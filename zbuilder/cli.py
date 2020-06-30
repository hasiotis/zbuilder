# -*- coding: utf-8 -*-
import os
import time
import click
import tabulate
import dpath.util
import distutils.dir_util

import zbuilder.vm
import zbuilder.cfg

from zbuilder.helpers import getHosts, getProviders, runPlaybook, fixKeys, runCmd, humanize_time
from zbuilder.options import pass_state, common_options

from click._bashcomplete import get_completion_script


@click.group()
@click.version_option()
def cli():
    """ZBuilder is a tool to create VMs ready to be transfered to ansible."""


@cli.command()
@click.option('--template', default='devel', help='Environment template')
@common_options
@pass_state
def init(state, template):
    """Init an environment"""
    if os.path.exists('group_vars') or os.path.exists('hosts'):
        raise click.ClickException("This directory already contains relevant files")

    cfg = zbuilder.cfg.load(touch=True)
    tmpl_path = dpath.util.get(cfg, '/main/templates/path')
    TEMPLATE_PATH = os.path.join(os.path.expanduser(tmpl_path), template)
    if os.path.exists(TEMPLATE_PATH):
        click.echo("Initializing {} based zbuilder environment".format(template))
        distutils.dir_util.copy_tree(TEMPLATE_PATH, os.getcwd())
    else:
        click.echo("Template path dose not exist: [{}]".format(TEMPLATE_PATH))
        exit(1)


@cli.command()
@common_options
@pass_state
def build(state):
    """Build the VMs"""
    start_time = time.time()
    click.echo("Building VMs")
    vmProviders = getHosts(state)
    for _, vmProvider in vmProviders.items():
        vmProvider['cloud'].build(vmProvider['hosts'])
    click.echo("Fixing ssh keys VMs")
    fixKeys(state)
    if os.path.exists('bootstrap.yml'):
        click.echo("Running bootstrap.yml")
        runPlaybook(state, "bootstrap.yml")
    end_time = time.time()
    click.echo("Time elapsed: {}".format(humanize_time(end_time - start_time)))


@cli.command()
@common_options
@pass_state
def up(state):
    """Boot the VMs"""
    click.echo("Booting VMs")
    vmProviders = getHosts(state)
    for _, vmProvider in vmProviders.items():
        vmProvider['cloud'].up(vmProvider['hosts'])


@cli.command()
@common_options
@pass_state
def halt(state):
    """Halt the VMs"""
    click.echo("Halting VMs")
    vmProviders = getHosts(state)
    for _, vmProvider in vmProviders.items():
        vmProvider['cloud'].halt(vmProvider['hosts'])


@cli.command()
@common_options
@pass_state
def destroy(state):
    """Destroy the VMs"""
    click.echo("Destroying VMs")
    vmProviders = getHosts(state)
    for _, vmProvider in vmProviders.items():
        zbuilder_env = None
        for h in vmProvider['hosts']:
            if 'ZBUILDER_ENV' in vmProvider['hosts'][h]:
                if 'prod' in vmProvider['hosts'][h]['ZBUILDER_ENV'].lower():
                    zbuilder_env = vmProvider['hosts'][h]['ZBUILDER_ENV']
                    break
                if 'prd' in vmProvider['hosts'][h]['ZBUILDER_ENV'].lower():
                    zbuilder_env = vmProvider['hosts'][h]['ZBUILDER_ENV']
                    break
        if zbuilder_env:
            if click.confirm("  The ZBUILDER_ENV is set to [{}] Do you want to continue?".format(zbuilder_env)):
                vmProvider['cloud'].destroy(vmProvider['hosts'])
            else:
                click.echo("    Aborting!")
        else:
            vmProvider['cloud'].destroy(vmProvider['hosts'])


@cli.command()
@common_options
@pass_state
def fixkeys(state):
    """Fix ssh keys"""
    click.echo("Fixing ssh keys VMs")
    fixKeys(state)


@cli.group()
def dns():
    """DNS management"""
    pass


@dns.command(name="update")
@common_options
@pass_state
def dns_update(state):
    """Update DNS records"""
    click.echo("Updating DNS records")
    vmProviders = getHosts(state)
    for _, vmProvider in vmProviders.items():
        vmProvider['cloud'].dnsupdate(vmProvider['hosts'])


@dns.command()
@common_options
@pass_state
def remove(state):
    """Remove DNS records"""
    click.echo("Removing DNS records")
    vmProviders = getHosts(state)
    for _, vmProvider in vmProviders.items():
        vmProvider['cloud'].dnsremove(vmProvider['hosts'])


@cli.group()
def snapshot():
    """Manage VM snapshots"""
    pass


@snapshot.command()
@common_options
@pass_state
def create(state):
    """Create VM snapshots"""
    click.echo("Creating VMs snapshots")
    vmProviders = getHosts(state)
    for _, vmProvider in vmProviders.items():
        vmProvider['cloud'].snapCreate(vmProvider['hosts'])


@snapshot.command()
@common_options
@pass_state
def restore(state):
    """Restore VM snapshots"""
    click.echo("Restoring VMs snapshots")
    vmProviders = getHosts(state)
    for _, vmProvider in vmProviders.items():
        vmProvider['cloud'].snapRestore(vmProvider['hosts'])


@snapshot.command()
@common_options
@pass_state
def delete(state):
    """Delete VM snapshots"""
    click.echo("Deleting VMs snapshots")
    vmProviders = getHosts(state)
    for _, vmProvider in vmProviders.items():
        vmProvider['cloud'].snapDelete(vmProvider['hosts'])


@cli.command()
@click.argument('playbook')
@common_options
@pass_state
def play(state, playbook):
    """Play an ansible playbook"""
    runPlaybook(state, playbook)


@cli.command()
@pass_state
def summary(state):
    """Display environment summary"""
    vmProviders = getHosts(state)
    data = []
    for _, vmProvider in vmProviders.items():
        for h, v in vmProvider['hosts'].items():
            data.append([vmProvider['cloud'].factory, h, vmProvider['cloud'].params(v)])
    click.echo(tabulate.tabulate(data, headers=["Provider", "Host", 'Parameters'], tablefmt="psql"))


@cli.command()
@pass_state
def providers(state):
    """Display providers info"""
    click.echo('Checking providers state...')
    cfg = zbuilder.cfg.load(touch=True)
    data = getProviders(cfg, state)
    headers = ['Name', 'Type', 'Check']
    click.echo(tabulate.tabulate(data, headers=headers))


@cli.group()
def config():
    """Zbuilder configuration"""
    pass


@config.command()
def view():
    """View configuration"""
    cfg = zbuilder.cfg.load()
    zbuilder.cfg.view(cfg)


@config.command()
def edit():
    """Edit configuration"""
    fname = os.path.expanduser(zbuilder.cfg.CONFIG_PATH)
    click.edit(filename=fname)


@config.command()
@click.argument('args', nargs=2)
@pass_state
def main(state, args):
    """Configure main parameters"""
    cfg = zbuilder.cfg.load(touch=True)

    base_path = args[0].replace('.', '/')
    sub_path, value = args[1].split('=')
    if ',' in value:
        value = value.split(',')
    cfg_path = "main/{}/{}".format(base_path, sub_path)

    click.echo("Setting config /{} to {}".format(cfg_path, value))
    dpath.util.new(cfg, cfg_path, value)
    zbuilder.cfg.save(cfg)


@config.command()
@click.argument('args', nargs=2)
@pass_state
def provider(state, args):
    """Configure a provider"""
    cfg = zbuilder.cfg.load(touch=True)

    base_path = args[0].replace('.', '/')
    sub_path, value = args[1].split('=', 1)
    if ',' in value:
        value = value.split(',')
    if value in ['True', 'true']:
        value = True
    if value in ['False', 'false']:
        value = False
    cfg_path = "providers/{}/{}".format(base_path, sub_path)

    click.echo("Setting config /{} to {}".format(cfg_path, value))
    dpath.util.new(cfg, cfg_path, value)
    zbuilder.cfg.save(cfg)


@config.command()
@click.option('--yes', is_flag=True)
@pass_state
def update(state, yes):
    """Update configuration components"""
    if not yes:
        click.confirm('Do you want to update?', abort=True)

    cfg = zbuilder.cfg.load(touch=True)
    try:
        tmpl_repo = dpath.util.get(cfg, '/main/templates/repo')
        tmpl_path = dpath.util.get(cfg, '/main/templates/path')
        if tmpl_repo and tmpl_path:
            click.echo(" * Updating templates")
            runCmd("git -C {path} pull || git clone {repo} {path}".format(repo=tmpl_repo, path=tmpl_path))
    except KeyError:
        pass


@cli.command()
@click.argument('shell', default='bash')
def completion(shell):
    """Autocomplete for bash"""
    click.echo(get_completion_script('zbuilder', '_ZBUILDER_COMPLETE', shell))
