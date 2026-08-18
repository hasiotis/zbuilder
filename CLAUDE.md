# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Commands

Dependency management is uv

```bash
uv sync                      # create/refresh .venv from uv.lock
. .venv/bin/activate

uv run pytest                # all tests
uv run pytest tests/test_inventory.py::test_group_vars_precedence   # single test
uv run pytest -v --md-report --md-report-flavor gfm                 # what CI runs

prek run --all-files         # lint/format (ruff-check + ruff-format via prek.toml)
uv build                     # build the wheel
```

CI (`.github/workflows/pr.yml`, `master.yml`) runs exactly `uv sync` → prek → pytest. Line length is 120 (`[tool.ruff]`).

## What this is

`zbuilder` is a CLI that provisions VMs across cloud providers and then hands them to ansible. Its distinguishing trait: **ansible is used as a library, not shelled out to**. Host definitions live in a normal ansible inventory, so zbuilder sees every group_var/host_var and all templating.

## Architecture

### The inventory → provider pipeline

Every VM-touching command in `cli.py` follows the same shape:

```python
vmProviders = getHosts(state)
for _, vmProvider in vmProviders.items():
    vmProvider["cloud"].<action>(vmProvider["hosts"])
```

`helpers.getHosts()` is where the two worlds meet:

1. `getHostsWithVars()` instantiates `ZBbuilderInventoryCLI` (a `PlaybookCLI` subclass) against `bootstrap.yml`, templates every host's vars through `Templar`, and keeps only hosts that define a `ZBUILDER_PROVIDER` dict. Hosts without it (e.g. `localhost`) are not zbuilder hosts.
2. Hosts matching `--limit` get `VM_OPTIONS.enabled = True`; **all other hosts are still returned, just disabled**. Providers must therefore check `hosts[h]["enabled"]` in every loop — the limit is not applied by filtering the dict.
3. `ZBUILDER_PROVIDER.CLOUD` names an entry in the user config's `providers:` section; its `type` selects the plugin module. `state` is injected into the provider config, which is how providers reach `state.verbose` and `state.vars["ZBUILDER_PUBKEY"]`.

### Inventory contract

```yaml
ZBUILDER_PROVIDER:
  CLOUD: <provider name from user config>
  DNS: <provider name>
  VM_OPTIONS: {memory: ..., vcpus: ..., disks: ..., box: ...}
```

Top-level `ZBUILDER_PUBKEY`, `ZBUILDER_SYSUSER`, `ZBUILDER_ENV` and `ansible_host` are copied into `VM_OPTIONS` by `getHosts()`. `ZBUILDER_ENV` containing `prod`/`prd` makes `destroy` prompt for confirmation.

### ansible-core process-wide state (fragile, easy to regress)

zbuilder runs more than one ansible CLI per process (inventory parse, then playbook run). ansible keeps singletons that refuse or silently ignore a second initialization, so `helpers.resetAnsibleContext()` must be called before **every** CLI construction — it clears the vault context, the `GlobalCLIArgs` singleton, and the collection finder. Without it, the second run silently inherits the first run's `--limit`. `tests/test_playbook.py` exists specifically to guard this.

Related: since ansible-core 2.19, templating returns tagged subclasses of `str`/`int`/`dict`. `helpers.nativeTypes()` unwraps them, because the yaml dumper and cloud SDKs dispatch on exact type. Anything crossing out of the templating layer must go through it (`test_vars_are_plain_python_types` guards this).

Also: `playbookArgs()` omits `-l` when limit is `None` — passing `-l None` makes ansible target a host literally named `None`.

### Provider plugins

Three parallel plugin families, each with an identical dynamic-import loader:

| Package | Loader | Module must export | Base class | Implementations |
|---|---|---|---|---|
| `zbuilder/vm/` | `vmProvider(factory, cfg)` | `vmProvider` class | `base.VMProvider` | vagrant, gcp, aws, do, azure, proxmox, ganeti |
| `zbuilder/dns/` | `dnsProvider(factory, cfg)` | `dnsProvider` class | `base.DNSProvider` | bind, powerdns, gcp, aws, azure, do, vagrant, ansible |
| `zbuilder/ipam/` | `ipamProvider(factory, cfg)` | `ipamProvider` class | `base.IPAMProvider` | phpipam |

The loader resolves `factory` through `plugins.load()`, instantiates the class with the provider config and stamps `factory` on it — nothing wraps or delegates, callers hold the provider itself.

`base.py` is the contract. Each family's base class derives from `Provider(ABC)`: `@abstractmethod` marks the actions a provider **must** implement (vm: `build`/`up`/`halt`/`destroy`, dns: `update`/`remove`, ipam: `reserve`/`locate`/`release`), and the concrete methods are the defaults for the optional ones (`dnsupdate`, `dnsremove`, `snapCreate`, `snapRestore`, `snapDelete`, `params`, `config`, `status`), which raise `base.UnsupportedAction` — a `ClickException` naming the provider and the action. Consequences: a provider still implements only the actions it supports, but skipping a mandatory one is a `TypeError` at instantiation rather than an `AttributeError` mid-build, and **exceptions inside providers now propagate** (the old `@trywrap` printed a traceback and swallowed them). `test_every_provider_implements_its_contract` guards the subclassing.

Providers with their own `__init__` must call `super().__init__(cfg)` — that is what sets `self.cfg`.

`plugins.py` discovers providers via `importlib.metadata` entry points, one group per family (`zbuilder.vm`, `zbuilder.dns`, `zbuilder.ipam`), declared in `pyproject.toml`. Loading stays lazy — only the selected provider's module is imported, so a missing cloud SDK breaks that provider alone. `plugins.names(group)` is the single source of truth for "which providers exist"; `cli.plugins` and `helpers.getProviders` both read it, so **adding a provider means dropping a module in the package and adding one line to `[project.entry-points."zbuilder.<family>"]`** — then `uv sync` to refresh the installed metadata, or discovery won't see it. An out-of-tree distribution registering the same groups is picked up the same way. A name registered in two families (`gcp`, `aws`, `do`, `azure`, `vagrant` are both vm and dns) resolves to vm in `getProviders`. `tests/test_plugins.py` asserts the entry points and the modules on disk stay in sync.

VM providers call `zbuilder.dns.dnsUpdate/dnsRemove` and `zbuilder.ipam.ipamReserve/Locate/Release` directly; those look up the right DNS/IPAM provider by matching the host's zone against `providers.*.dns.zones` and the subnet against `providers.*.ipam.subnets` in the user config.

The vagrant provider is the odd one: it renders a large embedded Jinja `Vagrantfile` template (overridable by a `Vagrantfile.tmpl` in the cwd) and drives the `vagrant` binary via `runCmd`, rather than talking to an API.

### User configuration

`~/.config/zbuilder/zbuilder.yaml` (`cfg.CONFIG_PATH`), with `main:` and `providers:` sections, written by `zbuilder config main|provider` using dpath paths (`zbuilder config provider pve username=root@pam`). Provider credential files (GCP secrets/tokens) also live in that directory. `zbuilder init` copies a template from the git repo configured at `main.templates.path`.

## Tests

`tests/fixtures/inventory/` is a real ansible inventory. Tests `monkeypatch.chdir` into it and override `C.DEFAULT_HOST_LIST`. They cover inventory parsing, var precedence/templating, and limit semantics — not the cloud providers, which have no test coverage.

## Notes

- `.envrc` (gitignored) holds live PyPI and ReadTheDocs tokens — do not print or commit it.
