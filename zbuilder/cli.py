# -*- coding: utf-8 -*-
import sys
import click

import zbuilder.config
import zbuilder.providers

from zbuilder.helpers import getHosts, runPlaybook, fixKeys
from zbuilder.options import pass_state, common_options

@click.group()
@click.version_option()
def cli():
    """ZBuilder is a tool to create VMs ready to be transfered to ansible."""


@cli.command()
@click.option('--provider', default='vagrant', help='VM provider')
@click.option('--dns', default='vagrant', help='DNS provider')
@common_options
@pass_state
def init(state, provider, dns):
    """Init an environment"""
    vmProvider = zbuilder.providers.vmProvider(provider, state.verbose)
    vmProvider.init()


@cli.command()
@common_options
@pass_state
def up(state):
    """Build the VMs"""
    click.echo("Building VMs")
    vmProviders = getHosts(state)
    for _, vmProvider in vmProviders.items():
        vmProvider['cloud'].up(vmProvider['hosts'])
    click.echo("Fixing ssh keys VMs")
    fixKeys(state)
    click.echo("Running bootstrap.yml")
    runPlaybook(state, "bootstrap.yml")


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
    pass

@config.command()
def view():
    """View configuration"""
    cfg = zbuilder.config.load("~/.zbuilder.yaml")
    zbuilder.config.view(cfg)
