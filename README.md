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

Install with:
```
pipx install --force zbuilder
```

or

```
pip3 install --user --upgrade zbuilder
```

The `kvm` provider needs the libvirt python bindings, which compile against
`libvirt-dev`. Install that package first, then ask for the extra:
```
pipx install --force 'zbuilder[kvm]'
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
