import sys
import click
import time
import socket
import delegator
import ruamel.yaml
import zbuilder.vm
import zbuilder.cfg

from retrying import retry
from ansible.errors import AnsibleError
from ansible.template import Templar
from ansible.cli.playbook import PlaybookCLI
from ansible.parsing.vault import VaultSecretsContext
from ansible.utils.context_objects import GlobalCLIArgs


def resetVaultContext():
    """Drop the process wide vault context

    Since ansible-core 2.19 the vault secrets live in a process wide context
    that refuses to be initialized twice. zbuilder runs more than one CLI per
    process (inventory parsing followed by a playbook run), so the context has
    to be cleared before every one of them.
    """
    VaultSecretsContext._current = None


def resetCliContext():
    """Drop the process wide cli arguments

    The parsed cli arguments live in a singleton, so only the first CLI of a
    process ever wins: every later parse() silently keeps the arguments of the
    first one. zbuilder builds one CLI to read the inventory and another one to
    run the playbook, so the singleton has to be dropped before every parse.
    """
    GlobalCLIArgs._Singleton__instance = None


def playbookArgs(pbook, limit):
    """Build the ansible-playbook argv, with -l only when there is a limit

    Passing "-l None" makes ansible look for hosts named None and end up with
    nothing to target.
    """
    args = ["ansible-playbook"]
    if limit is not None:
        args += ["-l", limit]
    args.append(pbook)

    return args


def nativeTypes(value):
    """Turn ansible tagged values into plain python ones

    Since ansible-core 2.19 templating returns tagged subclasses of str, int,
    dict, ... which carry the origin of every value. Code dispatching on the
    exact type, like the yaml dumper or the cloud sdks, does not know about
    them, so unwrap everything back to the builtin types.
    """
    if isinstance(value, dict):
        return {nativeTypes(k): nativeTypes(v) for k, v in value.items()}
    if isinstance(value, list):
        return [nativeTypes(v) for v in value]
    if isinstance(value, tuple):
        return tuple(nativeTypes(v) for v in value)
    if isinstance(value, set):
        return {nativeTypes(v) for v in value}
    if value is None or isinstance(value, bool):
        return value
    if isinstance(value, str):
        return str(value)
    if isinstance(value, int):
        return int(value)
    if isinstance(value, float):
        return float(value)

    return value


class ZBbuilderInventoryCLI(PlaybookCLI):
    def dumpVars(self):
        super(ZBbuilderInventoryCLI, self).parse()
        return self._play_prereqs()


def getHostsWithVars(limit, pbook="bootstrap.yml"):
    resetVaultContext()
    resetCliContext()
    inv = ZBbuilderInventoryCLI(playbookArgs(pbook, limit))
    loader, inventory, vm = inv.dumpVars()

    hostVars = {}
    for host in inventory.get_hosts():
        hvars = vm.get_vars(host=host, include_hostvars=True)
        templar = Templar(loader=loader, variables=hvars)
        hvars = nativeTypes(templar.template(hvars))

        if "ZBUILDER_PROVIDER" in hvars:
            hvars["ZBUILDER_PROVIDER"]["VM_OPTIONS"]["enabled"] = False
            hostVars[host.name] = hvars["ZBUILDER_PROVIDER"]
            if "ansible_host" in hvars:
                hostVars[host.name]["ansible_host"] = hvars["ansible_host"]
            if "ZBUILDER_PUBKEY" in hvars:
                hostVars[host.name]["ZBUILDER_PUBKEY"] = hvars["ZBUILDER_PUBKEY"]
            if "ZBUILDER_SYSUSER" in hvars:
                hostVars[host.name]["ZBUILDER_SYSUSER"] = hvars["ZBUILDER_SYSUSER"]
            if "ZBUILDER_ENV" in hvars:
                hostVars[host.name]["ZBUILDER_ENV"] = hvars["ZBUILDER_ENV"]

    inventory.subset(limit)
    for host in inventory.get_hosts():
        if host.name in hostVars:
            hostVars[host.name]["VM_OPTIONS"]["enabled"] = True

    return hostVars


def getHosts(state):
    cfg = zbuilder.cfg.load()
    hosts = getHostsWithVars(state.limit)

    vmProviders = {}
    if cfg is None:
        click.Abort("Config file seems to be empty")
    if "providers" not in cfg:
        click.Abort("There is no 'providers' sections on config file")

    for h, hvars in hosts.items():
        if "CLOUD" in hvars:
            curVMProvider = hvars["CLOUD"]
        else:
            next

        if curVMProvider not in vmProviders:
            provider_cfg = cfg["providers"][curVMProvider]
            provider_cfg["state"] = state
            vmProviders[curVMProvider] = {
                "cloud": zbuilder.vm.vmProvider(provider_cfg["type"], provider_cfg),
                "hosts": {},
            }

        hvars["VM_OPTIONS"]["aliases"] = ""
        if "ansible_host" in hvars:
            hvars["VM_OPTIONS"]["ansible_host"] = hvars["ansible_host"]
        if "ZBUILDER_PUBKEY" in hvars:
            hvars["VM_OPTIONS"]["ZBUILDER_PUBKEY"] = hvars["ZBUILDER_PUBKEY"]
            state.vars = {"ZBUILDER_PUBKEY": hvars["ZBUILDER_PUBKEY"]}
        if "ZBUILDER_SYSUSER" in hvars:
            hvars["VM_OPTIONS"]["ZBUILDER_SYSUSER"] = hvars["ZBUILDER_SYSUSER"]
        if "ZBUILDER_ENV" in hvars:
            hvars["VM_OPTIONS"]["ZBUILDER_ENV"] = hvars["ZBUILDER_ENV"]

        vmProviders[curVMProvider]["hosts"][h] = hvars["VM_OPTIONS"]

    return vmProviders


def getProviders(cfg, state):
    providers = []
    for p in cfg["providers"]:
        try:
            cp = cfg["providers"][p]
            cp["state"] = state
            if cp["type"] in [
                "aws",
                "azure",
                "do",
                "ganeti",
                "gcp",
                "proxmox",
                "vagrant",
            ]:
                curProvider = zbuilder.vm.vmProvider(cp["type"], cp)
            if cp["type"] in ["powerdns"]:
                curProvider = zbuilder.dns.dnsProvider(cp["type"], cp)
            if cp["type"] in ["phpipam"]:
                curProvider = zbuilder.ipam.ipamProvider(cp["type"], cp)
            providers.append([p, cp["type"], curProvider.status()])
        except Exception as e:
            providers.append([p, cp["type"], e])

    return providers


def runPlaybook(state, pbook):
    try:
        resetVaultContext()
        resetCliContext()
        playbookCLI = PlaybookCLI(playbookArgs(pbook, state.limit))
        playbookCLI.parse()
        playbookCLI.run()
    except AnsibleError as e:
        click.echo(e)


def load_yaml(fname):
    """Safely load a yaml file"""
    value = None
    try:
        yaml = ruamel.yaml.YAML()
        with open(fname, "r") as f:
            value = yaml.load(f)
    except ruamel.yaml.YAMLError as e:
        if hasattr(e, "problem_mark"):
            mark = e.problem_mark
            raise click.ClickException(
                "Yaml error (%s) at position: [line:%s column:%s]"
                % (fname, mark.line + 1, mark.column + 1)
            )
    except Exception as e:
        raise click.ClickException(e)

    return value


def humanize_time(secs):
    mins, secs = divmod(secs, 60)
    hours, mins = divmod(mins, 60)
    return "%02d:%02d" % (mins, secs)


def dump_yaml(cfg, where=None):
    yaml = ruamel.yaml.YAML()
    if where:
        yaml.dump(cfg, where)
    else:
        yaml.dump(cfg, sys.stdout)


@retry(stop_max_delay=10000)
def getIP(hostname):
    return socket.gethostbyname(hostname)


def waitSSH(ip):
    TIMEOUT = 300
    start_time = time.perf_counter()
    while True:
        try:
            with socket.create_connection((ip, 22), timeout=TIMEOUT):
                break
        except OSError:
            time.sleep(0.01)
            if time.perf_counter() - start_time >= TIMEOUT:
                return None
    return True


def fixKeys(state):
    vmProviders = getHosts(state)
    for _, vmProvider in vmProviders.items():
        for h, v in vmProvider["hosts"].items():
            if v["enabled"]:
                ip = None
                if "ansible_host" in v:
                    ip = v["ansible_host"]
                else:
                    try:
                        ip = getIP(h)
                    except Exception:
                        click.echo(
                            click.style(
                                "  - Host: {} can't be resolved".format(h), fg="red"
                            )
                        )
                        continue

                click.echo("  - Host: {}".format(h))
                runCmd("ssh-keygen -R {}".format(h), verbose=state.verbose)
                if ip is not None:
                    runCmd("ssh-keygen -R {}".format(ip), verbose=state.verbose)
                    waitSSH(ip)
                    runCmd(
                        "ssh -o StrictHostKeyChecking=no -o PasswordAuthentication=no {} exit".format(
                            h
                        ),
                        verbose=state.verbose,
                        ignoreError=True,
                    )
                    runCmd(
                        "ssh -o StrictHostKeyChecking=no -o PasswordAuthentication=no {} exit".format(
                            ip
                        ),
                        verbose=state.verbose,
                        ignoreError=True,
                    )


def runCmd(cmd, verbose=False, dry=False, ignoreError=False):
    if verbose:
        click.echo("    CMD: [{}]".format(cmd))
    if not dry:
        status = delegator.run(cmd)
        if verbose:
            click.echo(click.style(status.out, fg="green"))
        if status.return_code != 0 and not ignoreError:
            click.echo(click.style(status.err, fg="red"))

    return status.return_code
