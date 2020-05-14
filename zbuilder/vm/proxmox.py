import os
import re
import time
import click
import urllib.parse

from proxmoxer import ProxmoxAPI
from zbuilder.dns import dnsUpdate, dnsRemove
from zbuilder.ipam import ipamReserve, ipamRelease, ipamLocate


class vmProvider(object):
    def __init__(self, cfg):
        if cfg:
            self.cfg = cfg
            self.username = self.cfg['username']
            password = self.cfg['password']
            url = self.cfg['url']
            verify = self.cfg.get('verify', True)

            self.proxmox = ProxmoxAPI(url, user=self.username, password=password, verify_ssl=verify)

    def _waitTask(self, node, tid):
        results = None
        while True:
            results = node.tasks(tid).status.get()
            if results['status'] == 'stopped':
                break
            time.sleep(1)

        return results['exitstatus']

    def _getVMs(self, hosts):
        retValue = {}
        vms = {v['name']: v for v in self.proxmox.cluster.resources.get(type='vm')}
        for h, v in hosts.items():
            if hosts[h]['enabled']:
                ipconfig = v.get('ipconfig', '')
                if ipconfig.startswith('ipam='):
                    m = re.match(r"ipam=(?P<subnet>.*)", ipconfig)
                    subnet = m.groupdict()['subnet']
                    mask = subnet.split('/')[1]
                    ip, gw = ipamLocate(h, subnet)
                    v['subnet'] = subnet
                else:
                    m = re.match(r"ip=(?P<ip>.*)/(?P<mask>\d+),gw=(?P<gw>.*)", ipconfig)
                    mask = m.groupdict()['mask']
                    ip = m.groupdict()['ip']
                    gw = m.groupdict()['gw']

                v['mask'] = mask
                v['ip'] = ip
                v['gw'] = gw
                if h in vms.keys():
                    retValue[h] = v
                    retValue[h].update(vms[h])
                else:
                    retValue[h] = v
                    retValue[h].update({'status': None})

        return retValue

    def build(self, hosts):
        ips = {}
        vms = {i['name']: i for i in self.proxmox.cluster.resources.get(type='vm')}

        for h, v in self._getVMs(hosts).items():
            if v['status']:
                click.echo("  - Status of host: {} is {}".format(h, v['status']))
                ips[h] = v['ip']
            else:
                click.echo("  - Creating host: {} ".format(h))
                node = self.proxmox.nodes(v['node'])
                nextid = self.proxmox.cluster.nextid.get()
                if v['template'] in vms:
                    template = vms[v['template']]
                    if template['template'] != 1:
                        click.echo("This is not a template: [{}]".format(v['template']))
                        continue
                else:
                    click.echo("No such template: [{}]".format(v['template']))
                    continue

                # Clone the VM
                taskid = node(template['id']).clone.post(newid=nextid, name=h)
                result = self._waitTask(node, taskid)
                if result != 'OK':
                    click.echo("Clone failed".format())
                    continue

                # Customize the VM
                fname = os.path.expanduser(v['ZBUILDER_PUBKEY'])
                sshkey = ''
                if os.path.isfile(fname):
                    with open(fname, "r") as f:
                        sshkey = f.read().rstrip('\n')

                ipconfig = v['ipconfig']
                if v['ipconfig'].startswith('ipam='):
                    ip, gw = ipamReserve(h, v['subnet'])
                    ipconfig = "ip={}/{},gw={}".format(ip, v['mask'], gw)
                    ips[h] = ip
                else:
                    ips[h] = v['ip']

                taskid = node.qemu(nextid).config.set(
                    cores=v['vcpu'],
                    memory=v['memory'],
                    scsihw=v.get('scsihw', 'virtio-scsi-pci'),
                    net0=v.get('net0', 'virtio,bridge=vmbr0'),
                    virtio1='local-lvm:1,size=4G',
                    ipconfig0=ipconfig,
                    nameserver=v['nameserver'],
                    searchdomain=v['searchdomain'],
                    sshkeys=urllib.parse.quote(sshkey, safe=''),
                    ciuser=v['ZBUILDER_SYSUSER']
                )

                # Start the VM
                taskid = node.qemu(nextid).status.start().post()
                result = self._waitTask(node, taskid)
                if result != 'OK':
                    click.echo("Can't start the VM".format())
                    continue

        dnsUpdate(ips)

    def up(self, hosts):
        pass

    def halt(self, hosts):
        pass

    def destroy(self, hosts):
        updateHosts = {}
        vms = {i['name']: i for i in self.proxmox.cluster.resources.get(type='vm')}

        for h, v in self._getVMs(hosts).items():
            if v['status']:
                click.echo("  - Destroying host: {} ".format(h))
                updateHosts[h] = {}
                node = self.proxmox.nodes(v['node'])
                vm = vms[h]

                if v['status'] == 'running':
                    taskid = node(vm['id']).status.stop().post()
                    result = self._waitTask(node, taskid)
                    if result != 'OK':
                        click.echo('Failed: {}'.format(result))
                        continue

                taskid = node.delete(vm['id'])
                result = self._waitTask(node, taskid)
                if result != 'OK':
                    click.echo('Failed: {}'.format(result))
                    continue

                if v['ipconfig'].startswith('ipam='):
                    ipamRelease(h, v['ip'], v['subnet'])
            else:
                click.echo("  - Host does not exists [{}]".format(h))

        dnsRemove(updateHosts)

    def dnsupdate(self, hosts):
        ips = {}
        for h, v in self._getVMs(hosts).items():
            if 'ip' in v and hosts[h]['enabled']:
                ips[h] = v['ip']
        dnsUpdate(ips)

    def dnsremove(self, hosts):
        ips = {}
        for h, v in self._getVMs(hosts).items():
            if hosts[h]['enabled']:
                ips[h] = None
        dnsRemove(ips)

    def params(self, params):
        return {k: params[k] for k in ['node', 'template', 'vcpu', 'memory', 'ipconfig']}
