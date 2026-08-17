import pytest

from pathlib import Path

from ansible import constants as C
from zbuilder.helpers import getHostsWithVars


FIXTURES = Path(__file__).parent / "fixtures" / "inventory"

UBUNTU_HOSTS = ["ubuntu01.zbuilder.local", "ubuntu02.zbuilder.local"]
CENTOS_HOSTS = ["centos01.zbuilder.local"]


@pytest.fixture
def inventory(monkeypatch):
    """Run getHostsWithVars against the fixture inventory"""
    monkeypatch.chdir(FIXTURES)
    monkeypatch.setattr(C, "DEFAULT_HOST_LIST", [str(FIXTURES / "hosts")])

    def parse(limit="all"):
        # ansible allows a single vault context per process, drop it so that
        # every call starts from a clean state
        return getHostsWithVars(limit, pbook=str(FIXTURES / "bootstrap.yml"))

    return parse


def test_all_zbuilder_hosts_are_parsed(inventory):
    hosts = inventory()
    assert sorted(hosts) == sorted(UBUNTU_HOSTS + CENTOS_HOSTS)


def test_hosts_without_provider_are_ignored(inventory):
    """localhost carries no ZBUILDER_PROVIDER, so it is not a zbuilder host"""
    assert "localhost" not in inventory()


def test_group_vars_are_templated(inventory):
    hosts = inventory()

    ubuntu = hosts["ubuntu01.zbuilder.local"]
    assert ubuntu["DNS"] == "local"
    assert ubuntu["CLOUD"] == "local"
    assert ubuntu["VM_OPTIONS"]["memory"] == 512
    assert ubuntu["VM_OPTIONS"]["vcpus"] == 1
    assert ubuntu["VM_OPTIONS"]["disks"] == 10
    assert ubuntu["VM_OPTIONS"]["box"] == "bento/ubuntu-22.04"


def test_group_vars_precedence(inventory):
    """The centos group overrides GLOBAL_MEMORY defined in group_vars/all"""
    hosts = inventory()

    assert hosts["centos01.zbuilder.local"]["VM_OPTIONS"]["memory"] == 1024
    assert hosts["ubuntu01.zbuilder.local"]["VM_OPTIONS"]["memory"] == 512


def test_global_vars_are_exported(inventory):
    hosts = inventory()

    for hvars in hosts.values():
        assert hvars["ZBUILDER_SYSUSER"] == "sysadmin"
        assert hvars["ZBUILDER_ENV"] == "DEV"
        assert hvars["ZBUILDER_PUBKEY"] == "~/.ssh/id_rsa.pub"


def test_host_vars_are_exported(inventory):
    hosts = inventory()

    assert hosts["ubuntu02.zbuilder.local"]["ansible_host"] == "10.0.0.2"
    assert "ansible_host" not in hosts["ubuntu01.zbuilder.local"]


def test_limit_all_enables_every_host(inventory):
    hosts = inventory("all")

    assert all(h["VM_OPTIONS"]["enabled"] for h in hosts.values())


def test_limit_group_enables_only_that_group(inventory):
    hosts = inventory("ubuntu")

    assert sorted(hosts) == sorted(UBUNTU_HOSTS + CENTOS_HOSTS)
    for host in UBUNTU_HOSTS:
        assert hosts[host]["VM_OPTIONS"]["enabled"] is True
    for host in CENTOS_HOSTS:
        assert hosts[host]["VM_OPTIONS"]["enabled"] is False


def test_limit_single_host_enables_only_that_host(inventory):
    hosts = inventory("centos01.zbuilder.local")

    assert hosts["centos01.zbuilder.local"]["VM_OPTIONS"]["enabled"] is True
    for host in UBUNTU_HOSTS:
        assert hosts[host]["VM_OPTIONS"]["enabled"] is False


def test_vars_are_plain_python_types(inventory):
    """ansible-core >= 2.19 templates into tagged subclasses, which neither the
    yaml dumper nor the cloud sdks understand, so they must not leak out"""

    def check(value):
        assert type(value) in (dict, list, str, int, float, bool, type(None))
        if isinstance(value, dict):
            for k, v in value.items():
                check(k)
                check(v)
        elif isinstance(value, list):
            for v in value:
                check(v)

    check(inventory())
