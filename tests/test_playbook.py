import pytest

from pathlib import Path

from ansible import constants as C
from zbuilder.helpers import getHostsWithVars, runPlaybook


FIXTURES = Path(__file__).parent / "fixtures" / "inventory"
NOOP = str(FIXTURES / "noop.yml")
BOOTSTRAP = str(FIXTURES / "bootstrap.yml")

UBUNTU_HOSTS = ["ubuntu01.zbuilder.local", "ubuntu02.zbuilder.local"]
CENTOS_HOSTS = ["centos01.zbuilder.local"]


class State(object):
    def __init__(self, limit=None):
        self.limit = limit
        self.verbose = 0


@pytest.fixture
def play(monkeypatch, capfd):
    """Run a playbook against the fixture inventory, return the played hosts"""
    monkeypatch.chdir(FIXTURES)
    monkeypatch.setattr(C, "DEFAULT_HOST_LIST", [str(FIXTURES / "hosts")])

    def run(limit=None, pbook=NOOP):
        runPlaybook(State(limit), pbook)
        out = capfd.readouterr().out
        return sorted(line.split()[0] for line in out.splitlines() if ": ok=" in line)

    return run


def test_playbook_without_limit_targets_every_host(play):
    assert play() == sorted(UBUNTU_HOSTS + CENTOS_HOSTS)


def test_playbook_limit_targets_only_that_group(play):
    assert play("ubuntu") == sorted(UBUNTU_HOSTS)


def test_playbook_after_inventory_parse_targets_every_host(play):
    """The cli arguments are a process wide singleton, so the inventory parse
    zbuilder runs first must not decide what the playbook run targets"""
    getHostsWithVars("ubuntu", pbook=BOOTSTRAP)

    assert play() == sorted(UBUNTU_HOSTS + CENTOS_HOSTS)


def test_playbook_after_inventory_parse_uses_its_own_limit(play):
    getHostsWithVars("ubuntu", pbook=BOOTSTRAP)

    assert play("centos") == sorted(CENTOS_HOSTS)
