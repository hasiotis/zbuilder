import os
import re
import time
import click
import requests
import urllib.parse

from proxmoxer import ProxmoxAPI
from zbuilder.dns import dnsUpdate, dnsRemove
from zbuilder.ipam import ipamReserve, ipamRelease, ipamLocate

NOTES_FORMAT = """Created with zbuilder

time: {}
user: {}
"""


class vmProvider(object):
    def __init__(self, cfg):
        if cfg:
            self.cfg = cfg
            self.username = self.cfg['username']
            password = self.cfg['password']
            url = self.cfg['url']
            verify = self.cfg.get('verify', True)
            try:
                self.proxmox = ProxmoxAPI(url, user=self.username, password=password, verify_ssl=verify)
            except requests.exceptions.Timeout as e:
                raise Exception(e.args[0].reason.args[1])

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
        vms = {v['name']: v for v in self.proxmox.cluster.resources.get(type='vm') if 'name' in v}
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
        templates = [i for i in self.proxmox.cluster.resources.get(type='vm') if i.get('template', 0) == 1]

        for h, v in self._getVMs(hosts).items():
            if v['status']:
                click.echo("  - Status of host: {} is {}".format(h, v['status']))
                ips[h] = v['ip']
            else:
                click.echo("  - Creating host: {} ".format(h))
                node = self.proxmox.nodes(v['node'])
                nextid = self.proxmox.cluster.nextid.get()
                template = None
                for t in templates:
                    if v['template'] == t['name'] and v['node'] == t['node']:
                        template = t

                if not template:
                    click.echo("No such template: [{}] on node [{}]".format(v['template'], v['node']))
                    continue

                # Clone the VM
                full = int(v.get('full', 0) is True)
                taskid = node(template['id']).clone.post(newid=nextid, name=h, full=full)
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
                    ipconfig0=ipconfig,
                    nameserver=v['nameserver'],
                    searchdomain=v['searchdomain'],
                    sshkeys=urllib.parse.quote(sshkey, safe=''),
                    ciuser=v['ZBUILDER_SYSUSER'],
                    description=NOTES_FORMAT.format(time.strftime("%c", time.localtime()), self.username)
                )
                for i, disk in enumerate(v.get('disks', [])):
                    args = {f"virtio{i+1}": disk}
                    taskid = node.qemu(nextid).config.set(**args)

                # Start the VM
                taskid = node.qemu(nextid).status.start().post()
                result = self._waitTask(node, taskid)
                if result != 'OK':
                    click.echo("Can't start the VM".format())
                    continue

        dnsUpdate(ips)

    def up(self, hosts):
        vms = {i['name']: i for i in self.proxmox.cluster.resources.get(type='vm') if 'name' in i}
        for h, v in self._getVMs(hosts).items():
            if v['status']:
                click.echo("  - Starting host: {} ".format(h))
                node = self.proxmox.nodes(v['node'])
                vm = vms[h]
                if v['status'] == 'stopped':
                    taskid = node(vm['id']).status.start().post()
                    result = self._waitTask(node, taskid)
                    if result != 'OK':
                        click.echo('Failed: {}'.format(result))
                        continue
            else:
                click.echo("  - Host does not exists [{}]".format(h))

    def halt(self, hosts):
        vms = {i['name']: i for i in self.proxmox.cluster.resources.get(type='vm') if 'name' in i}
        for h, v in self._getVMs(hosts).items():
            if v['status']:
                click.echo("  - Halting host: {} ".format(h))
                node = self.proxmox.nodes(v['node'])
                vm = vms[h]
                if v['status'] == 'running':
                    taskid = node(vm['id']).status.shutdown().post()
                    result = self._waitTask(node, taskid)
                    if result != 'OK':
                        click.echo('Failed: {}'.format(result))
                        continue
            else:
                click.echo("  - Host does not exists [{}]".format(h))

    def destroy(self, hosts):
        updateHosts = {}
        vms = {i['name']: i for i in self.proxmox.cluster.resources.get(type='vm') if 'name' in i}

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

    def snapCreate(self, hosts):
        vms = {i['name']: i for i in self.proxmox.cluster.resources.get(type='vm') if 'name' in i}
        for h, v in self._getVMs(hosts).items():
            if v['status']:
                node = self.proxmox.nodes(v['node'])
                vm = vms[h]
                snapshots = node(vm['id']).snapshot.get()
                for curSnapshot in snapshots:
                    if curSnapshot['name'] == 'zbuilder':
                        click.echo("  - Deleting snapshot for vm: {} ".format(h))
                        taskid = node(vm['id']).snapshot("zbuilder").delete()
                        result = self._waitTask(node, taskid)
                        if result != 'OK':
                            click.echo('    Failed: {}'.format(result))
                click.echo("  - Creating snapshot for vm: {} ".format(h))
                taskid = node(vm['id']).snapshot.post(snapname="zbuilder", description="Managed by zbuilder")
                result = self._waitTask(node, taskid)
                if result != 'OK':
                    click.echo('Failed: {}'.format(result))
                    continue
            else:
                click.echo("  - Host does not exists [{}]".format(h))

    def snapRestore(self, hosts):
        vms = {i['name']: i for i in self.proxmox.cluster.resources.get(type='vm') if 'name' in i}
        for h, v in self._getVMs(hosts).items():
            if v['status']:
                node = self.proxmox.nodes(v['node'])
                vm = vms[h]
                snapshots = node(vm['id']).snapshot.get()
                for curSnapshot in snapshots:
                    if curSnapshot['name'] == 'zbuilder':
                        click.echo("  - Restoring snapshot for vm: {} ".format(h))
                        taskid = node(vm['id']).snapshot("zbuilder").rollback.post()
                        result = self._waitTask(node, taskid)
                        if result != 'OK':
                            click.echo('    Failed: {}'.format(result))
                        taskid = node(vm['id']).status.start().post()
                        result = self._waitTask(node, taskid)
                        if result != 'OK':
                            click.echo('Failed: {}'.format(result))
            else:
                click.echo("  - Host does not exists [{}]".format(h))

    def snapDelete(self, hosts):
        vms = {i['name']: i for i in self.proxmox.cluster.resources.get(type='vm') if 'name' in i}
        for h, v in self._getVMs(hosts).items():
            if v['status']:
                node = self.proxmox.nodes(v['node'])
                vm = vms[h]
                snapshots = node(vm['id']).snapshot.get()
                for curSnapshot in snapshots:
                    if curSnapshot['name'] == 'zbuilder':
                        click.echo("  - Deleting snapshot for vm: {} ".format(h))
                        taskid = node(vm['id']).snapshot("zbuilder").delete()
                        result = self._waitTask(node, taskid)
                        if result != 'OK':
                            click.echo('    Failed: {}'.format(result))
            else:
                click.echo("  - Host does not exists [{}]".format(h))

    def config(self):
        return "url: {v[url]}, username: {v[username]}".format(v=self.cfg)

    def status(self):
        return 'PASS'

    def params(self, params):
        return {k: params.get(k, None) for k in ['node', 'template', 'vcpu', 'memory', 'ipconfig', 'disks']}
