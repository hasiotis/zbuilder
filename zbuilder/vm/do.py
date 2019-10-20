import time
import click
import digitalocean

SLEEP_TIME = 5


class vmProvider(object):

    def __init__(self, state, dns):
        self.state = state
        self.dns = dns
        self.token = self.state.vmConfig['token']
        self.manager = digitalocean.Manager(token=self.token)

    def getDroplets(self, hosts):
        retValue = {}
        droplets = self.manager.get_all_droplets()
        for h, v in hosts.items():
            if hosts[h]['enabled']:
                for droplet in droplets:
                    if droplet.name == h:
                        retValue[droplet.name] = droplet
                if h not in retValue:
                    for curkey in self.manager.get_all_sshkeys():
                        if curkey.name == v['sshkey']:
                            sshkey = curkey
                            continue
                    droplet = digitalocean.Droplet(
                        token=self.token,
                        name=h,
                        region=v['region'],
                        image=v['image'],
                        size_slug=v['size_slug'],
                        ssh_keys=[sshkey],
                        monitoring=True,
                        backups=False,
                    )
                    retValue[h] = droplet

        return retValue

    def waitStatus(self, hosts, status):
        allStatus = True
        while not allStatus:
            allStatus = True
            for k, d in self.getDroplets(hosts).items():
                if d.status != status:
                    allStatus = False
                    break
            click.echo(".")
            time.sleep(SLEEP_TIME)

    def build(self, hosts):
        ips = {}
        for k, d in self.getDroplets(hosts).items():
            if d.status is None:
                click.echo("  - Creating host: {} ".format(d.name))
                d.create()
                ips[d.name] = None
            elif d.status == 'off':
                click.echo("  - Booting host: {} ".format(d.name))
                d.power_on()
            elif d.status == 'active':
                click.echo("  - Already up host: {} ".format(d.name))
            else:
                click.echo("  - Status of host: {} is {}".format(d.name, d.status))

        self.waitStatus(hosts, 'active')

        for k, d in self.getDroplets(hosts).items():
            if d.name in ips:
                ips[d.name] = d.ip_address

        self.dns.update(ips)

    def up(self, hosts):
        for k, d in self.getDroplets(hosts).items():
            if d.status is None:
                click.echo("  - No such host: {} ".format(d.name))
            elif d.status == 'off':
                click.echo("  - Booting host: {} ".format(d.name))
                d.power_on()
            elif d.status == 'active':
                click.echo("  - Already up host: {} ".format(d.name))
            else:
                click.echo("  - Status of host: {} is {}".format(d.name, d.status))

    def halt(self, hosts):
        for k, d in self.getDroplets(hosts).items():
            if d.status == 'active':
                click.echo("  - Halting host: {} ".format(d.name))
                d.shutdown()
            else:
                click.echo("  - Status of host: {} is {}".format(d.name, d.status))

        self.waitStatus(hosts, 'off')

    def destroy(self, hosts):
        for k, d in self.getDroplets(hosts).items():
            if d.status is not None:
                click.echo("  - Destroying host: {} ".format(d.name))
                d.destroy()
            else:
                click.echo("  - Host does not exists : {}".format(d.name))

        self.waitStatus(hosts, 'off')
        ips = {}
        for h in hosts:
            if hosts[h]['enabled']:
                ips[h] = None
        self.dns.remove(ips)

    def dnsupdate(self, hosts):
        ips = {}
        for k, d in self.getDroplets(hosts).items():
            if d.ip_address:
                ips[d.name] = d.ip_address
        self.dns.update(ips)

    def dnsremove(self, hosts):
        ips = {}
        for h in hosts:
            if hosts[h]['enabled']:
                ips[h] = None
        self.dns.remove(ips)

    def snapCreate(self, hosts):
        snapshots = self.manager.get_droplet_snapshots()
        snaps = [s.name for s in snapshots]
        for k, d in self.getDroplets(hosts).items():
            if d.status is not None:
                snapshot_name = "zbuilder-{}".format(d.name)
                if snapshot_name not in snaps:
                    click.echo("  - Taking snapshot: {}".format(d.name))
                    d.take_snapshot(snapshot_name)
                else:
                    click.echo("  - Snapshot already exists: {}".format(d.name))

    def snapRestore(self, hosts):
        snapshots = self.manager.get_droplet_snapshots()
        snaps = {}
        for s in snapshots:
            snaps[s.name] = s

        click.echo("  Halting")
        self.halt(hosts)
        self.waitStatus(hosts, 'off')
        click.echo("  Restoring")
        for k, d in self.getDroplets(hosts).items():
            if d.status == 'off':
                snapshot_name = "zbuilder-{}".format(d.name)
                if snapshot_name in snaps.keys():
                    click.echo("  - Restoring from image: {} ".format(snapshot_name))
                    d.restore(snaps[snapshot_name].id)
                else:
                    click.echo("  - No such snapshot: {}".format(snapshot_name))
        click.echo("  Booting up")
        self.up(hosts)
        self.waitStatus(hosts, 'active')

    def snapDelete(self, hosts):
        snapshots = self.manager.get_droplet_snapshots()
        snaps = {}
        for s in snapshots:
            snaps[s.name] = s
        for h in hosts:
            if hosts[h]['enabled']:
                snapshot_name = "zbuilder-{}".format(h)
                if snapshot_name in snaps.keys():
                    click.echo("  - Deleting snapshot: {}".format(snapshot_name))
                    snaps[snapshot_name].destroy()
                else:
                    click.echo("  - No such snapshot: {}".format(snapshot_name))
