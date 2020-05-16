import os
import click

from zbuilder.dns import dnsUpdate, dnsRemove

from azure.common.credentials import ServicePrincipalCredentials
from azure.mgmt.resource import ResourceManagementClient
from azure.mgmt.compute import ComputeManagementClient
from azure.mgmt.network import NetworkManagementClient
from msrestazure.azure_exceptions import CloudError
from msrestazure.tools import parse_resource_id


class vmProvider(object):
    def __init__(self, cfg):
        if cfg:
            self.cfg = cfg
            self.credentials = ServicePrincipalCredentials(
                client_id=cfg['client_id'],
                secret=cfg['client_secret'],
                tenant=cfg['tenant_id']
            )
            self.rgroupClient = ResourceManagementClient(self.credentials, cfg['subscription_id'])
            self.netClient = NetworkManagementClient(self.credentials, cfg['subscription_id'])
            self.vmClient = ComputeManagementClient(self.credentials, cfg['subscription_id'])

    def create_nic(self, h, v):
        subnet = self.netClient.subnets.get(v['network']['group'], v['network']['vnet'], v['network']['subnet'])
        nicName = "nic_{}".format(h)
        nicParams = {
            'location': v['location'],
            'ip_configurations': [{
                'name': nicName,
                'subnet': {
                    'id': subnet.id
                }
            }]
        }

        if v['network'].get('external', False):
            pipName = "public_ip_{}".format(h)
            pipParams = {
                'location': v['location'],
                'public_ip_allocation_method': 'dynamic',
            }
            pip_poller = self.netClient.public_ip_addresses.create_or_update(
                v['resource_group'], pipName, pipParams
            )
            pip = pip_poller.result()
            nicParams['ip_configurations'][0]['public_ip_address'] = {'id': pip.id}

        nic = self.netClient.network_interfaces.create_or_update(v['resource_group'], nicName, nicParams)
        return nic.result()

    def create_vm(self, h, v, nic):
        sysuser = v['ZBUILDER_SYSUSER']
        pubkey_fname = os.path.expanduser(v['ZBUILDER_PUBKEY'])
        pubkey = open(pubkey_fname, "r").read().rstrip('\n')
        datadisks = []
        if 'data_disks' in v:
            for i, disk in enumerate(v['data_disks']):
                datadisks.append({
                    "lun": i,
                    "diskSizeGB": disk['diskSizeGB'],
                    "caching": disk['caching'],
                    "createOption": "Empty",
                    "managedDisk": {"storageAccountType": disk['storageAccountType']}
                })
        vmParams = {
            'location': v['location'],
            'os_profile': {
                'computer_name': h,
                'admin_username': sysuser,
                'linux_configuration': {
                    'disable_password_authentication': True,
                    'ssh': {
                        'public_keys': [{
                            "path": "/home/{}/.ssh/authorized_keys".format(sysuser),
                            "key_data": pubkey
                         }]
                    }
                }
            },
            'hardware_profile': {
                'vm_size': v['vm_size']
            },
            'storage_profile': {
                'image_reference': {
                    'publisher': v['publisher'],
                    'offer': v['offer'],
                    'sku': v['sku'],
                    'version': v['version']
                },
                "osDisk": {
                    "createOption": "fromImage",
                    "caching": "ReadWrite",
                    "managedDisk": {"storageAccountType": v['storageAccountType']}
                },
                "dataDisks": datadisks
            },
            'network_profile': {
                'network_interfaces': [{
                    'id': nic.id
                }]
            },
        }
        result = self.vmClient.virtual_machines.create_or_update(v['resource_group'], h, vmParams)
        return result.result()

    def build(self, hosts):
        ips = {}
        for h, v in hosts.items():
            if v['enabled']:
                vm = None
                try:
                    vm = self.vmClient.virtual_machines.get(v['resource_group'], h)
                    click.echo("  - Already up host: {} ".format(vm.name))
                except CloudError as e:
                    if str(e).startswith("Azure Error: ResourceNotFound"):
                        click.echo("  - Creating host: {} ".format(h))
                        nic = self.create_nic(h, v)
                        vm = self.create_vm(h, v, nic)
                        ips[vm.name] = None

                interface = vm.network_profile.network_interfaces[0]
                nicInfo = parse_resource_id(interface.id)
                ip_configurations = self.netClient.network_interfaces.get(nicInfo['resource_group'], nicInfo['resource_name']).ip_configurations

                if v.get('external_dns', False):
                    pipInfo = parse_resource_id(ip_configurations[0].public_ip_address.id)
                    pip = self.netClient.public_ip_addresses.get(pipInfo['resource_group'], pipInfo['resource_name'])
                    ips[vm.name] = pip.ip_address
                else:
                    ips[vm.name] = ip_configurations[0].private_ip_address

        dnsUpdate(ips)

    def up(self, hosts):
        for h, v in hosts.items():
            if v['enabled']:
                vm = None
                try:
                    vm = self.vmClient.virtual_machines.get(v['resource_group'], h, expand='instanceView')
                    vmStatus = vm.instance_view.statuses[1].display_status
                    if vmStatus == 'VM stopped':
                        click.echo("  - Booting host: {} ".format(h))
                        async_vm_start = self.vmClient.virtual_machines.start(v['resource_group'], h)
                        async_vm_start.wait()
                    else:
                        click.echo("  - Status of host: {} is [{}]".format(h, vmStatus))
                except CloudError as e:
                    if str(e).startswith("Azure Error: ResourceNotFound"):
                        click.echo("  - No such host: {} ".format(h))

    def halt(self, hosts):
        for h, v in hosts.items():
            if v['enabled']:
                vm = None
                try:
                    vm = self.vmClient.virtual_machines.get(v['resource_group'], h, expand='instanceView')
                    vmStatus = vm.instance_view.statuses[1].display_status
                    if vmStatus == 'VM running':
                        click.echo("  - Halting host: {} ".format(h))
                        async_vm_stop = self.vmClient.virtual_machines.power_off(v['resource_group'], h)
                        async_vm_stop.wait()
                    else:
                        click.echo("  - Status of host: {} is [{}]".format(h, vmStatus))
                except CloudError as e:
                    if str(e).startswith("Azure Error: ResourceNotFound"):
                        click.echo("  - No such host: {} ".format(h))

    def destroy(self, hosts):
        ips = {}
        for h, v in hosts.items():
            if hosts[h]['enabled']:
                vm = None
                try:
                    vm = self.vmClient.virtual_machines.get(v['resource_group'], h)

                    interface = vm.network_profile.network_interfaces[0]
                    nicInfo = parse_resource_id(interface.id)
                    ip_configurations = self.netClient.network_interfaces.get(nicInfo['resource_group'], nicInfo['resource_name']).ip_configurations
                    click.echo("  - Destroying host: {} ".format(vm.name))

                    async_vm_delete = self.vmClient.virtual_machines.delete(v['resource_group'], h)
                    async_vm_delete.wait()

                    click.echo("    Removing nic: {} ".format(nicInfo['resource_name']))
                    net_del_poller = self.netClient.network_interfaces.delete(nicInfo['resource_group'], nicInfo['resource_name'])
                    net_del_poller.wait()

                    pipInfo = parse_resource_id(ip_configurations[0].public_ip_address.id)
                    pip = self.netClient.public_ip_addresses.get(pipInfo['resource_group'], pipInfo['resource_name'])
                    if pip.id:
                        click.echo("    Removing public ip: {} ".format(pip.name))
                        ip_del_poller = self.netClient.public_ip_addresses.delete(pipInfo['resource_group'], pipInfo['resource_name'])
                        ip_del_poller.wait()

                    if v.get('external_dns', False):
                        ips[vm.name] = pip.ip_address
                    else:
                        ips[vm.name] = ip_configurations[0].private_ip_address

                except CloudError as e:
                    if str(e).startswith("Azure Error: ResourceNotFound"):
                        click.echo("  - Host does not exists : {}".format(h))

                try:
                    disks_list = self.vmClient.disks.list_by_resource_group(v['resource_group'])
                    disk_handle_list = []
                    async_disk_handle_list = []
                    for disk in disks_list:
                        if h in disk.name:
                            click.echo("    Removing disk: {} ".format(disk.name))
                            async_disk_delete = self.vmClient.disks.delete(v['resource_group'], disk.name)
                            async_disk_handle_list.append(async_disk_delete)
                    for async_disk_delete in disk_handle_list:
                        async_disk_delete.wait()
                except CloudError as e:
                    click.echo("    Error while removing disk: {}".format(e))

        dnsRemove(ips)

    def dnsupdate(self, hosts):
        ips = {}
        for h, v in hosts.items():
            if hosts[h]['enabled']:
                try:
                    vm = self.vmClient.virtual_machines.get(v['resource_group'], h)
                    interface = vm.network_profile.network_interfaces[0]
                    nicInfo = parse_resource_id(interface.id)
                    ip_configurations = self.netClient.network_interfaces.get(nicInfo['resource_group'], nicInfo['resource_name']).ip_configurations
                    if v.get('external_dns', False):
                        pipInfo = parse_resource_id(ip_configurations[0].public_ip_address.id)
                        pip = self.netClient.public_ip_addresses.get(pipInfo['resource_group'], pipInfo['resource_name'])
                        ips[vm.name] = pip.ip_address
                    else:
                        ips[vm.name] = ip_configurations[0].private_ip_address
                except CloudError as e:
                    if str(e).startswith("Azure Error: ResourceNotFound"):
                        pass

        dnsUpdate(ips)

    def dnsremove(self, hosts):
        ips = {}
        for h in hosts:
            if hosts[h]['enabled']:
                ips[h] = None

        dnsRemove(ips)

    def config(self):
        return "subscription: {v[subscription_id]}".format(v=self.cfg)

    def status(self):
        return "PASS"
