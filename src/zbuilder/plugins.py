"""Provider plugin discovery.

Providers are registered as entry points, one group per plugin family. That
keeps the list of known providers in `pyproject.toml` instead of hardcoded in
the code, and lets a third party package ship a provider without touching
zbuilder at all: install a distribution exposing `zbuilder.vm` entry points and
its providers become selectable in the inventory.

Loading is lazy on purpose. Only the module of the provider actually in use is
imported, so a missing cloud SDK breaks that provider alone.
"""

import click

from functools import cache
from importlib.metadata import entry_points

VM = "zbuilder.vm"
DNS = "zbuilder.dns"
IPAM = "zbuilder.ipam"


@cache
def names(group):
    """Names of every provider registered under an entry point group"""
    return sorted({ep.name for ep in entry_points(group=group)})


def load(group, factory):
    """Return the provider class registered as `factory` in `group`"""
    for ep in entry_points(group=group, name=factory):
        return ep.load()

    raise click.ClickException(
        "Unknown {} provider [{}]. Available: {}".format(
            group.rpartition(".")[2], factory, ", ".join(names(group)) or "none"
        )
    )
