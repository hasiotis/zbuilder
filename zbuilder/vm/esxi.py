import time
import click
import arrow

from pyVmomi import vim
from pyVim.connect import SmartConnect, SmartConnectNoSSL
from zbuilder.dns import dnsRemove


class vmProvider(object):
    def __init__(self, cfg):
        if cfg:
            self.cfg = cfg
            if cfg['verify']:
                self.conn = SmartConnect(host=cfg['host'], user=cfg['username'], pwd=cfg['password'], port=cfg['port'])
            else:
                self.conn = SmartConnectNoSSL(host=cfg['host'], user=cfg['username'], pwd=cfg['password'], port=cfg['port'])

    def _get_obj(self, content, vimtype, name):
        obj = None
        container = content.viewManager.CreateContainerView(content.rootFolder, vimtype, True)
        for c in container.view:
            if name:
                if c.name == name:
                    obj = c
                    break
            else:
                obj = c
                break
        return obj

    def _wait_for_task(self, task, reportTime=False):
        task_done = False
        while not task_done:
            if task.info.state == 'success':
                if reportTime:
                    elapsed = arrow.get(task.info.completeTime) - arrow.get(task.info.startTime)
                    click.echo("    Task completed in [%s seconds]" % (elapsed.seconds))
                task_done = True
            if task.info.state == 'error':
                click.echo("    Task [%s] failed: [%s]" % (task, task.info.error.msg))
                task_done = True
            time.sleep(1)

        return task.info.state

    def build(self, hosts):
        content = self.conn.RetrieveContent()

        for h, v in hosts.items():
            vmFound = self._get_obj(content, [vim.VirtualMachine], h)
            if not vmFound:
                click.echo("  - Creating host: {} ".format(h))
                template = self._get_obj(content, [vim.VirtualMachine], v['template'])
                templateDisk = None
                for device in template.config.hardware.device:
                    if type(device) == vim.vm.device.VirtualDisk and device.unitNumber == 0:
                        templateDisk = device.backing.fileName

                root_datastore, root_size = v['root_disk'].split(':', 2)

                devices = []
                vmPathName = "[{}] {}/{}.vmx".format(root_datastore, h, h)
                vmx_file = vim.vm.FileInfo(logDirectory=None, snapshotDirectory=None, suspendDirectory=None, vmPathName=vmPathName)

                net = self._get_obj(content, [vim.Network], v['network'])

                nicspec = vim.vm.device.VirtualDeviceSpec()
                nicspec.operation = vim.vm.device.VirtualDeviceSpec.Operation.add
                nic_type = vim.vm.device.VirtualVmxnet3()
                nicspec.device = nic_type
                nicspec.device.deviceInfo = vim.Description()
                nicspec.device.backing = vim.vm.device.VirtualEthernetCard.NetworkBackingInfo()
                nicspec.device.backing.network = net
                nicspec.device.backing.deviceName = net.name
                nicspec.device.connectable = vim.vm.device.VirtualDevice.ConnectInfo()
                nicspec.device.connectable.startConnected = True
                nicspec.device.connectable.allowGuestControl = True
                devices.append(nicspec)

                scsi_ctr = vim.vm.device.VirtualDeviceSpec()
                scsi_ctr.operation = vim.vm.device.VirtualDeviceSpec.Operation.add
                scsi_ctr.device = vim.vm.device.ParaVirtualSCSIController()
                scsi_ctr.device.deviceInfo = vim.Description()
                scsi_ctr.device.slotInfo = vim.vm.device.VirtualDevice.PciBusSlotInfo()
                scsi_ctr.device.slotInfo.pciSlotNumber = 16
                scsi_ctr.device.controllerKey = 100
                scsi_ctr.device.unitNumber = 3
                scsi_ctr.device.busNumber = 0
                scsi_ctr.device.hotAddRemove = True
                scsi_ctr.device.sharedBus = 'noSharing'
                scsi_ctr.device.scsiCtlrUnitNumber = 7
                devices.append(scsi_ctr)

                unit_number = 0
                controller = scsi_ctr.device
                disk_spec = vim.vm.device.VirtualDeviceSpec()
                disk_spec.operation = vim.vm.device.VirtualDeviceSpec.Operation.add
                disk_spec.device = vim.vm.device.VirtualDisk()
                disk_spec.fileOperation = "create"
                disk_spec.device.backing = vim.vm.device.VirtualDisk.FlatVer2BackingInfo()
                disk_spec.device.backing.diskMode = 'persistent'
                disk_spec.device.backing.fileName = "[{}] {}/{}_disk0.vmdk".format(root_datastore, h, h)
                disk_spec.device.unitNumber = unit_number
                disk_spec.device.capacityInKB = int(root_size) * 1024 * 1024
                disk_spec.device.controllerKey = controller.key
                devices.append(disk_spec)

                config = vim.vm.ConfigSpec(name=h, memoryMB=v['memory'], numCPUs=v['vcpu'], files=vmx_file, guestId='ubuntu64Guest', version='vmx-15', deviceChange=devices)
                folder = self._get_obj(content, [vim.Folder], "")
                pool = self._get_obj(content, [vim.ResourcePool], "")

                try:
                    task = folder.CreateVM_Task(config=config, pool=pool)
                    self._wait_for_task(task)
                except Exception as e:
                    print(e)

                if templateDisk:
                    templateDiskRaw = templateDisk.replace('.vmdk', '-flat.vmdk')
                    destDiskRaw = "[{}] {}/{}_disk0-flat.vmdk".format(root_datastore, h, h)
                    try:
                        task = content.fileManager.CopyDatastoreFile_Task(sourceName=templateDiskRaw, destinationName=destDiskRaw, force=True)
                        self._wait_for_task(task, reportTime=True)
                    except Exception as e:
                        print(e)
            else:
                click.echo("  - Already running host: {} ".format(h))

    def up(self, hosts):
        pass

    def halt(self, hosts):
        pass

    def destroy(self, hosts):
        updateHosts = {}
        content = self.conn.RetrieveContent()
        for h, v in hosts.items():
            vmFound = self._get_obj(content, [vim.VirtualMachine], h)
            if vmFound:
                click.echo("  - Destroying host: {} ".format(h))
                if vmFound.runtime.powerState == "poweredOn":
                    try:
                        task = vmFound.PowerOffVM_Task()
                        self._wait_for_task(task)
                    except Exception as e:
                        click.echo("  Attempting to power off failed [%s]" % e)

                try:
                    task = vmFound.Destroy_Task()
                    self._wait_for_task(task)
                    click.echo("    Destroyed")
                except Exception as e:
                    click.echo("        Attempting to destroy failed [%s]" % e)
            else:
                click.echo("  - Host does not exists : {}".format(h))

        dnsRemove(updateHosts)

    def dnsupdate(self, hosts):
        pass

    def snapCreate(self, hosts):
        pass

    def snapRestore(self, hosts):
        pass

    def snapDelete(self, hosts):
        pass

    def params(self, params):
        pass
