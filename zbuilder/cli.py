# -*- coding: utf-8 -*-
import os
import sys
import click

import zbuilder.vm
import zbuilder.cfg

import distutils.dir_util

from click._bashcomplete import get_completion_script

from zbuilder.helpers import getHosts, runPlaybook, fixKeys
from zbuilder.options import pass_state, common_options

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

    TEMPLATE_PATH = os.path.expanduser("~/.config/zbuilder/assets/{}".format(template))
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
    click.echo("Building VMs")
    vmProviders = getHosts(state)
    for _, vmProvider in vmProviders.items():
        vmProvider['cloud'].build(vmProvider['hosts'])
    click.echo("Fixing ssh keys VMs")
    fixKeys(state)
    click.echo("Running bootstrap.yml")
    runPlaybook(state, "bootstrap.yml")


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


@dns.command()
@common_options
@pass_state
def update(state):
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
def status():
    """Display environment status"""
    pass


@cli.command()
def summary():
    """Display environment summary"""
    pass


@cli.group()
def config():
    """Zbuilder configuration"""
    cfg  = zbuilder.cfg.load()
    for provider in providers:
        state.vmConfig = cfg['providers'][provider]
        state.dnsConfig = None
        vmProvider = zbuilder.vm.vmProvider(provider, state)
        vmProvider.config()

@config.command()
def view():
    """View configuration"""
    cfg = zbuilder.cfg.load()
    zbuilder.cfg.view(cfg)


@cli.command()
@click.argument('shell', default='bash')
def completion(shell):
    """Autocomplete for bash"""
    click.echo(get_completion_script('zbuilder', '_ZBUILDER_COMPLETE'))
