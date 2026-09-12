# Zbuilder: Building VMs and applying ansible playbooks

[![PyPi version](https://badge.fury.io/py/zbuilder.svg)](https://pypi.org/project/zbuilder/)
[![PyPi downloads](https://img.shields.io/pypi/dm/zbuilder.svg)](https://pypistats.org/packages/zbuilder)
[![Build status](https://github.com/hasiotis/zbuilder/workflows/master/badge.svg)](https://github.com/hasiotis/zbuilder/actions?query=workflow%3A%22master%22)
[![Documentation Status](https://readthedocs.org/projects/zbuilder/badge/?version=stable)](https://zbuilder.readthedocs.io/en/stable/?badge=stable)
[![License: GPL v3](https://img.shields.io/badge/License-GPLv3-blue.svg)](https://github.com/hasiotis/zbuilder/blob/master/LICENSE)

ZBuilder is a tool to help you build VMs ready to be transferred to ansible.
By using ansible as a library, it has access to all ansible variables. This
way it achieves high integration with ansible.

## Installation

zbuilder depends on the libvirt python bindings, which compile against the
libvirt headers, so install those first:
```
apt install libvirt-dev pkg-config gcc     # or: dnf install libvirt-devel
```

Then install with:
```
pipx install --force zbuilder
```

or

```
pip3 install --user --upgrade zbuilder
```

The `gcp` provider needs the google client libraries, which ship as an extra:
```
pipx install --force 'zbuilder[gcp]'
```

The `proxmox` provider needs `proxmoxer`, which ships as an extra:
```
pipx install --force 'zbuilder[proxmox]'
```

## Providers

| Family | Providers |
|---|---|
| VM   | `aws`, `gcp`, `kvm`, `proxmox` |
| DNS  | `ansible`, `aws`, `bind`, `gcp`, `powerdns` |
| IPAM | `phpipam` |

See the [documentation](https://zbuilder.readthedocs.io/en/stable/) for the
settings each one accepts, or run `zbuilder providers`.

## Development
During development you can:
```
uv sync
. .venv/bin/activate

uv run pytest                # run the tests
prek run --all-files         # lint and format
```

## Links

[Documentation](https://zbuilder.readthedocs.io/en/stable/?badge=stable)
| [Releases](https://pypi.org/project/zbuilder/)
| [Code](https://github.com/hasiotis/zbuilder)
