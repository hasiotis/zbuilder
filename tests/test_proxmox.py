"""Proxmox provider tests.

proxmoxer is an optional extra, so the module has to import - and say what is
missing - on a machine that does not have it.
"""

import click
import pytest

from zbuilder.vm import proxmox


def test_a_missing_extra_is_reported_as_an_install_hint(monkeypatch):
    monkeypatch.setattr(proxmox, "ProxmoxAPI", None)

    assert "zbuilder[proxmox]" in proxmox.vmProvider({}).status()
    # ... and `zbuilder plugins` does not offer a provider that cannot run
    assert proxmox.vmProvider({}).enabled() is False


def test_a_missing_extra_is_reported_when_configured(monkeypatch):
    monkeypatch.setattr(proxmox, "ProxmoxAPI", None)

    with pytest.raises(click.ClickException) as excinfo:
        proxmox.vmProvider({"url": "https://pve:8006", "username": "root@pam", "password": "x"})

    assert "zbuilder[proxmox]" in str(excinfo.value)


def test_params_tolerates_a_host_that_omits_them():
    assert proxmox.vmProvider({}).params({"memory": 2048}) == {
        "node": None,
        "template": None,
        "vcpu": None,
        "memory": 2048,
        "ipconfig": None,
        "disks": None,
    }
