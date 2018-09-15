import sys
import click
import socket
import delegator
import ruamel.yaml
import zbuilder.vm
import zbuilder.cfg

from ansible.cli import CLI
from ansible.template import Templar
from ansible.cli.playbook import PlaybookCLI


def getVars():
    parser = CLI.base_parser(vault_opts=True, inventory_opts=True)
    options, args = parser.parse_args(["-i", "hosts"])
    loader, inventory, vm = CLI._play_prereqs(options)
    hosts = inventory.get_hosts(pattern='localhost')
    tVars = vm.get_vars(host=hosts[0])
    retValue = {}
    for v in tVars:
        if v == 'VM_OPTIONS':
            next
        if v.startswith('ZBUILDER_'):
            retValue[v] = tVars[v]
    return retValue


def getHostsWithVars(subset):
    parser = CLI.base_parser(vault_opts=True, inventory_opts=True)
    options, args = parser.parse_args(["-i", "hosts", "-l", subset.limit])
    loader, inventory, vm = CLI._play_prereqs(options)

    hostVars = {}
    for host in inventory.get_hosts():
        hvars = vm.get_vars(host=host, include_hostvars=True)
        templar = Templar(loader=loader, variables=hvars)
        hvars = templar.template(hvars)
        if 'ZBUILDER_PROVIDER' in hvars:
            hvars['ZBUILDER_PROVIDER']['VM_OPTIONS']['enabled'] = False
            hostVars[str(host)] = hvars['ZBUILDER_PROVIDER']

    inventory.subset(options.subset)
    for host in inventory.get_hosts():
        if str(host) in hostVars:
            hostVars[str(host)]['VM_OPTIONS']['enabled'] = True

    return hostVars


def getHosts(state):
    state.vars = getVars()
    cfg  = zbuilder.cfg.load("~/.zbuilder.yaml")
    hosts = getHostsWithVars(state)

    vmProviders = {}
    (curVMProvider, curDNSrovider) = (None, None)
    for h, hvars in hosts.items():
        if 'CLOUD' in hvars:
            curVMProvider = hvars['CLOUD']
        state.vmConfig = cfg['providers'][curVMProvider]
        state.dnsConfig = None
        if 'DNS' in hvars:
            curDNSrovider = hvars['DNS']
        state.dnsConfig = cfg['providers'][curDNSrovider]
        if curVMProvider not in vmProviders:
            vmProviders[curVMProvider] = {}
            vmProviders[curVMProvider]['cloud'] = zbuilder.vm.vmProvider(state.vmConfig['type'], state)
            vmProviders[curVMProvider]['hosts'] = {}
        hvars['VM_OPTIONS']['aliases'] = ''
        vmProviders[curVMProvider]['hosts'][h] = hvars['VM_OPTIONS']

    return vmProviders


def runPlaybook(state, pbook):
    playbookCLI = PlaybookCLI(["ansible-playbook", "-l", state.limit,  pbook])
    playbookCLI.parse()
    playbookCLI.run()


def load_yaml(fname):
    """Safely load a yaml file"""
    value = None
    try:
        yaml = ruamel.yaml.YAML()
        with open(fname, 'r') as f:
            value = yaml.load(f)
    except ruamel.yaml.YAMLError as e:
        if hasattr(e, 'problem_mark'):
            mark = e.problem_mark
            raise click.ClickException(
                "Yaml error (%s) at position: [line:%s column:%s]" %
                (fname, mark.line + 1, mark.column + 1)
            )
    except Exception as e:
        raise click.ClickException(e)

    return value


def dump_yaml(cfg):
    yaml = ruamel.yaml.YAML()
    yaml.dump(cfg, sys.stdout)


def fixKeys(state):
    vmProviders = getHosts(state)
    for _, vmProvider in vmProviders.items():
        for host in vmProvider['hosts']:
            h = str(host)
            click.echo("  - Host: {}".format(h))
            ip = socket.gethostbyname(h)
            runCmd("ssh-keygen -R {}".format(ip), verbose=state.verbose)
            runCmd("ssh-keygen -R {}".format(h), verbose=state.verbose)
            runCmd(
                "ssh -o StrictHostKeyChecking=no -o PasswordAuthentication=no {} exit".format(h),
                verbose=state.verbose, ignoreError=True
            )

def runCmd(cmd, verbose=False, dry=False, ignoreError=False):
    if verbose:
        click.echo("    CMD: [{}]".format(cmd))
    if not dry:
        status = delegator.run(cmd)
        if verbose:
            click.echo(click.style(status.out, fg='green'))
        if status.return_code != 0 and not ignoreError:
            errMsg = "    Failed [{}]".format(status.err)
            click.echo(click.style(errMsg, fg='red'))

    return status.return_code
