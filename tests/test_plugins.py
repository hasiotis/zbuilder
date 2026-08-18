import pytest
import click

import zbuilder.vm
import zbuilder.plugins as plugins

from pathlib import Path
from zbuilder.base import VMProvider, DNSProvider, IPAMProvider, UnsupportedAction


SRC = Path(__file__).parent.parent / "src" / "zbuilder"

GROUPS = [
    (plugins.VM, "vmProvider", VMProvider),
    (plugins.DNS, "dnsProvider", DNSProvider),
    (plugins.IPAM, "ipamProvider", IPAMProvider),
]


@pytest.mark.parametrize("group, klass, base", GROUPS)
def test_every_module_is_registered(group, klass, base):
    """Every provider module in the tree has an entry point in pyproject.toml"""
    family = group.rpartition(".")[2]
    modules = {p.stem for p in (SRC / family).glob("*.py") if p.stem != "__init__"}

    assert modules == set(plugins.names(group))


@pytest.mark.parametrize("group, klass, base", GROUPS)
def test_every_entry_point_loads(group, klass, base):
    """Entry point targets import and point at the expected provider class"""
    for name in plugins.names(group):
        provider = plugins.load(group, name)
        assert provider.__name__ == klass


@pytest.mark.parametrize("group, klass, base", GROUPS)
def test_every_provider_implements_its_contract(group, klass, base):
    """Providers subclass the base of their family and leave nothing abstract"""
    for name in plugins.names(group):
        provider = plugins.load(group, name)
        assert issubclass(provider, base)
        assert not provider.__abstractmethods__


def test_unknown_provider_is_reported():
    with pytest.raises(click.ClickException) as excinfo:
        plugins.load(plugins.VM, "nosuchcloud")

    assert "nosuchcloud" in str(excinfo.value)
    assert "vagrant" in str(excinfo.value)


def test_provider_knows_the_name_it_was_loaded_as():
    assert zbuilder.vm.vmProvider("vagrant").factory == "vagrant"


class minimalProvider(VMProvider):
    """A provider implementing the mandatory actions and nothing else"""

    def build(self, hosts):
        pass

    def up(self, hosts):
        pass

    def halt(self, hosts):
        pass

    def destroy(self, hosts):
        pass


def test_optional_actions_report_they_are_unsupported():
    provider = minimalProvider()
    provider.factory = "minimal"

    with pytest.raises(UnsupportedAction) as excinfo:
        provider.snapCreate({})

    assert "minimal" in str(excinfo.value)
    assert "snapCreate" in str(excinfo.value)


def test_mandatory_actions_can_not_be_skipped():
    class brokenProvider(VMProvider):
        pass

    with pytest.raises(TypeError):
        brokenProvider()
