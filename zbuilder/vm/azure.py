import os
import time
import click


from azure.common.credentials import ServicePrincipalCredentials
from azure.mgmt.resource import ResourceManagementClient
from azure.mgmt.compute import ComputeManagementClient
from azure.mgmt.network import NetworkManagementClient
from azure.mgmt.compute.models import DiskCreateOption
from msrestazure.azure_exceptions import CloudError
from msrestazure.tools import parse_resource_id


class vmProvider(object):

    def __init__(self, state, dns):
        self.state = state
        self.dns = dns
        self.credentials = ServicePrincipalCredentials(
            client_id = state.vmConfig['client_id'],
            secret = state.vmConfig['client_secret'],
            tenant = state.vmConfig['tenant_id']
        )
        self.rgroupClient = ResourceManagementClient(self.credentials, state.vmConfig['subscription_id'])
        self.netClient = NetworkManagementClient(self.credentials, state.vmConfig['subscription_id'])
        self.vmClient = ComputeManagementClient(self.credentials, state.vmConfig['subscription_id'])


    def create_nic(self, h, v):
        subnet = self.netClient.subnets.get(v['network']['group'], v['network']['vnet'], v['network']['subnet'])
        nicName = "nic_{}".format(h)
        ipConfigName = "ip_config_{}".format(h)
        nicParams = {
            'location': v['location'],
            'ip_configurations': [{
                'name': ipConfigName,
                'subnet': {
                    'id': subnet.id
                }
            }]
        }
        nic = self.netClient.network_interfaces.create_or_update(v['resource_group'], nicName, nicParams)
        return nic.result()


    def create_vm(self, h, v, nic):
        sysuser = self.state.vars['ZBUILDER_SYSUSER']
        pubkey_fname = os.path.expanduser(self.state.vars['ZBUILDER_PUBKEY'])
        pubkey = open(pubkey_fname, "r").read().rstrip('\n')
        datadisks = []
        if 'data_disks' in v:
            for i, disk in enumerate(v['data_disks']):
                datadisks.append({
                    "lun": i,
                    "diskSizeGB": disk['diskSizeGB'],
                    "caching": disk['caching'],
                    "createOption": "Empty",
                    "managedDisk": { "storageAccountType": disk['storageAccountType'] }
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
                    "managedDisk": { "storageAccountType": v['storageAccountType'] }
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
                thing = self.netClient.network_interfaces.get(nicInfo['resource_group'], nicInfo['resource_name']).ip_configurations
                ips[vm.name] = thing[0].private_ip_address

        self.dns.update(ips)


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
                    thing = self.netClient.network_interfaces.get(nicInfo['resource_group'], nicInfo['resource_name']).ip_configurations
                    ips[vm.name] = thing[0].private_ip_address
                    click.echo("  - Destroying host: {} ".format(vm.name))

                    async_vm_delete = self.vmClient.virtual_machines.delete(v['resource_group'], h)
                    async_vm_delete.wait()

                    click.echo("    Removing nic: {} ".format(nicInfo['resource_name']))
                    net_del_poller = self.netClient.network_interfaces.delete(nicInfo['resource_group'], nicInfo['resource_name'])
                    net_del_poller.wait()
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

        self.dns.remove(ips)


    def dnsupdate(self, hosts):
        ips = {}
        for h, v in hosts.items():
            if hosts[h]['enabled']:
                vm = self.vmClient.virtual_machines.get(v['resource_group'], h)

                interface = vm.network_profile.network_interfaces[0]
                nicInfo = parse_resource_id(interface.id)
                thing = self.netClient.network_interfaces.get(nicInfo['resource_group'], nicInfo['resource_name']).ip_configurations
                ips[vm.name] = thing[0].private_ip_address

        self.dns.update(ips)


    def dnsremove(self, hosts):
        ips = {}
        for h in hosts:
            if hosts[h]['enabled']:
                ips[h] = None
        self.dns.remove(ips)
