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
                    allStatus == False
                    continue
            click.echo(".")
            time.sleep(SLEEP_TIME)


    def up(self, hosts):
        for k, d in self.getDroplets(hosts).items():
            if d.status == None:
                click.echo("  - Creating host: {} ".format(d.name))
                d.create()
            elif d.status == 'off':
                click.echo("  - Booting host: {} ".format(d.name))
                d.power_on()
            elif d.status == 'active':
                click.echo("  - Already up host: {} ".format(d.name))
            else:
                click.echo("  - Status of host: {} is {}".format(d.name, d.status))

        self.waitStatus(hosts, 'active')

        ips = {}
        for k, d in self.getDroplets(hosts).items():
            ips[d.name] = d.ip_address

        self.dns.update(ips)


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
            if d.status != None:
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


    def snapCreate(self, hosts):
        for d in self.getDroplets(hosts):
            click.echo("  - Host: {}".format(h))
            droplet.take_snapshot("zbuilder")


    def snapRestore(self, hosts):
        click.echo("  Halting")
        click.echo("  Restoring")
        click.echo("  Booting up")


    def snapDelete(self, hosts):
        for d in self.getDroplets(hosts):
            click.echo("  - Host: {}".format(h))
            droplet.take_snapshot("zbuilder")
