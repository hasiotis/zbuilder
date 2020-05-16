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
from ansible.release import __version__ as ansible_version


class ZBbuilderInventoryCLI(PlaybookCLI):
    def dumpVars(self):
        super(ZBbuilderInventoryCLI, self).parse()
        if ansible_version.startswith('2.7'):
            from ansible.cli import CLI
            parser = CLI.base_parser(vault_opts=True, inventory_opts=True)
            options, args = parser.parse_args(["-i", "hosts"])
            return self._play_prereqs(options)
        if ansible_version.startswith('2.9'):
            return self._play_prereqs()


def getHostsWithVars(limit, pbook='bootstrap.yml'):
    inv = ZBbuilderInventoryCLI(["ansible-playbook", "-l", limit,  pbook])
    loader, inventory, vm = inv.dumpVars()

    hostVars = {}
    for host in inventory.get_hosts():
        hvars = vm.get_vars(host=host, include_hostvars=True)
        templar = Templar(loader=loader, variables=hvars)
        hvars = templar.template(hvars)

        if 'ZBUILDER_PROVIDER' in hvars:
            hvars['ZBUILDER_PROVIDER']['VM_OPTIONS']['enabled'] = False
            hostVars[host.name] = hvars['ZBUILDER_PROVIDER']
            if 'ansible_host' in hvars:
                hostVars[host.name]['ansible_host'] = hvars['ansible_host']
            if 'ZBUILDER_PUBKEY' in hvars:
                hostVars[host.name]['ZBUILDER_PUBKEY'] = hvars['ZBUILDER_PUBKEY']
            if 'ZBUILDER_SYSUSER' in hvars:
                hostVars[host.name]['ZBUILDER_SYSUSER'] = hvars['ZBUILDER_SYSUSER']
            if 'ZBUILDER_ENV' in hvars:
                hostVars[host.name]['ZBUILDER_ENV'] = hvars['ZBUILDER_ENV']

    inventory.subset(limit)
    for host in inventory.get_hosts():
        if host.name in hostVars:
            hostVars[host.name]['VM_OPTIONS']['enabled'] = True

    return hostVars


def getHosts(state):
    cfg = zbuilder.cfg.load()
    hosts = getHostsWithVars(state.limit)

    vmProviders = {}
    if cfg is None:
        click.Abort("Config file seems to be empty")
    if 'providers' not in cfg:
        click.Abort("There is no 'providers' sections on config file")

    for h, hvars in hosts.items():
        if 'CLOUD' in hvars:
            curVMProvider = hvars['CLOUD']
        else:
            next

        if curVMProvider not in vmProviders:
            provider_cfg = cfg['providers'][curVMProvider]
            provider_cfg['state'] = state
            vmProviders[curVMProvider] = {
                'cloud': zbuilder.vm.vmProvider(provider_cfg['type'], provider_cfg),
                'hosts': {}
            }

        hvars['VM_OPTIONS']['aliases'] = ''
        if 'ansible_host' in hvars:
            hvars['VM_OPTIONS']['ansible_host'] = hvars['ansible_host']
        if 'ZBUILDER_PUBKEY' in hvars:
            hvars['VM_OPTIONS']['ZBUILDER_PUBKEY'] = hvars['ZBUILDER_PUBKEY']
            state.vars = {'ZBUILDER_PUBKEY': hvars['ZBUILDER_PUBKEY']}
        if 'ZBUILDER_SYSUSER' in hvars:
            hvars['VM_OPTIONS']['ZBUILDER_SYSUSER'] = hvars['ZBUILDER_SYSUSER']
        if 'ZBUILDER_ENV' in hvars:
            hvars['VM_OPTIONS']['ZBUILDER_ENV'] = hvars['ZBUILDER_ENV']

        vmProviders[curVMProvider]['hosts'][h] = hvars['VM_OPTIONS']

    return vmProviders


def getProviders(cfg, state):
    providers = []
    for p in cfg['providers']:
        try:
            cp = cfg['providers'][p]
            cp['state'] = state
            if cp['type'] in ['aws', 'azure', 'do', 'ganeti', 'gcp', 'proxmox', 'vagrant']:
                curProvider = zbuilder.vm.vmProvider(cp['type'], cp)
            if cp['type'] in ['powerdns']:
                curProvider = zbuilder.dns.dnsProvider(cp['type'], cp)
            if cp['type'] in ['phpipam']:
                curProvider = zbuilder.ipam.ipamProvider(cp['type'], cp)
            providers.append([p, cp['type'], curProvider.status()])
        except Exception as e:
            providers.append([p, cp['type'], e])

    return providers


def runPlaybook(state, pbook):
    try:
        playbookCLI = PlaybookCLI(["ansible-playbook", "-l", state.limit,  pbook])
        playbookCLI.parse()
        playbookCLI.run()
    except AnsibleError as e:
        click.echo(e)


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


def humanize_time(secs):
    mins, secs = divmod(secs, 60)
    hours, mins = divmod(mins, 60)
    return '%02d:%02d' % (mins, secs)


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
        for h, v in vmProvider['hosts'].items():
            if v['enabled']:
                ip = None
                if 'ansible_host' in v:
                    ip = v['ansible_host']
                else:
                    try:
                        ip = getIP(h)
                    except Exception:
                        click.echo(click.style("  - Host: {} can't be resolved".format(h), fg='red'))
                        continue

                click.echo("  - Host: {}".format(h))
                runCmd("ssh-keygen -R {}".format(h), verbose=state.verbose)
                if ip is not None:
                    runCmd("ssh-keygen -R {}".format(ip), verbose=state.verbose)
                    waitSSH(ip)
                    runCmd(
                        "ssh -o StrictHostKeyChecking=no -o PasswordAuthentication=no {} exit".format(h),
                        verbose=state.verbose, ignoreError=True
                    )
                    runCmd(
                        "ssh -o StrictHostKeyChecking=no -o PasswordAuthentication=no {} exit".format(ip),
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
            click.echo(click.style(status.err, fg='red'))

    return status.return_code
