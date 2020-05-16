import os
import click
import pickle
import googleapiclient.discovery

from zbuilder.dns import dnsUpdate, dnsRemove
from google.oauth2 import service_account
from google_auth_oauthlib.flow import InstalledAppFlow
from google.auth.transport.requests import Request

CONFIG_PATH = "~/.config/zbuilder/"


def auth(cfg):
    SCOPES = ['https://www.googleapis.com/auth/compute', 'https://www.googleapis.com/auth/ndev.clouddns.readwrite']

    creds = None
    # First we check for client-secret and creds-file
    if 'client-secret' in cfg and 'creds-file' in cfg:
        secretFilename = os.path.expanduser("{}/{}".format(CONFIG_PATH, cfg['client-secret']))
        tokenFilename = os.path.expanduser("{}/{}".format(CONFIG_PATH, cfg.get('creds-file', '')))
        if os.path.exists(secretFilename) and os.path.exists(tokenFilename):
            with open(tokenFilename, 'rb') as token:
                creds = pickle.load(token)
        if not creds or not creds.valid:
            if creds and creds.expired and creds.refresh_token:
                creds.refresh(Request())
            else:
                flow = InstalledAppFlow.from_client_secrets_file(secretFilename, SCOPES)
                creds = flow.run_local_server(port=0)
            with open(tokenFilename, 'wb') as token:
                pickle.dump(creds, token)

    # In case of missing client-secret or creds-file fallback to service-key
    if creds is None and 'service-key' in cfg:
        secretFilename = os.path.expanduser("{}/{}".format(CONFIG_PATH, cfg['service-key']))
        if os.path.exists(secretFilename) and os.path.exists(secretFilename):
            creds = service_account.Credentials.from_service_account_file(secretFilename, scopes=SCOPES)

    # Fail if no auth keys are available
    if creds is None:
        click.echo("Unable to authenticate due to missing secrets")
        raise click.Abort()

    return creds


class vmProvider(object):
    def __init__(self, cfg):
        if cfg:
            self.cfg = cfg
            creds = auth(self.cfg)

            try:
                self.compute = googleapiclient.discovery.build('compute', 'v1', credentials=creds)
            except Exception as e:
                click.echo("Login failed: [{}]".format(e))
                raise click.Abort()

    def _waitDone(self, ops, msg=None):
        for h, op in ops.items():
            while True:
                request = self.compute.zoneOperations().get(project=op['project'], zone=op['zone'], operation=op['name'])
                response = request.execute()
                if response['status'] == 'DONE':
                    if msg:
                        click.echo(msg.format(h))
                    break

    def _getVMs(self, hosts):
        retValue = {}
        for h, v in hosts.items():
            if hosts[h]['enabled']:
                shortname = h.partition('.')[0]
                try:
                    result = self.compute.instances().list(
                        project=v['project'],
                        zone=v['zone'],
                        filter="name=\"{}\"".format(shortname)
                    ).execute()
                except Exception as e:
                    click.echo("Error [{}]".format(e))
                    exit()
                items = result.get('items', [])
                if items:
                    retValue[h] = items[0]
                    retValue[h]['values'] = v
                else:
                    retValue[h] = {'status': None}
                    retValue[h]['values'] = v

                    image_response = self.compute.images().getFromFamily(project=v['image']['project'], family=v['image']['family']).execute()
                    source_disk_image = image_response['selfLink']

                    fname = os.path.expanduser(v['ZBUILDER_PUBKEY'])
                    sshkey = ''
                    if os.path.isfile(fname):
                        with open(fname, "r") as f:
                            sshkey = f.read().rstrip('\n')

                    network = "global/networks/{v[network]}".format(v=v)
                    if '/' in v['network']:
                        network = v['network']

                    subnetwork = "regions/{v[region]}/subnetworks/{v[subnet]}".format(v=v)
                    if '/' in v['subnet']:
                        subnetwork = v['subnet']

                    accessConfigs = []
                    if v.get('net_external', False):
                        accessConfigs = [{'type': 'ONE_TO_ONE_NAT', 'name': 'External NAT'}]

                    retValue[h]['insert'] = self.compute.instances().insert(
                        project=v['project'],
                        zone=v['zone'],
                        body={
                            'name': shortname,
                            'machineType': "zones/{v[zone]}/machineTypes/{v[size]}".format(v=v),
                            'disks': [
                                {
                                    'boot': True,
                                    'autoDelete': True,
                                    'initializeParams': {
                                        'sourceImage': source_disk_image,
                                    }
                                }
                            ],
                            'networkInterfaces': [{
                                'network': network,
                                'subnetwork': subnetwork,
                                'accessConfigs': accessConfigs
                            }],
                            "metadata": {
                                "items": [
                                    {
                                        "key": "ssh-keys",
                                        "value": "gcpadmin:" + sshkey
                                    }
                                ]
                            },
                        }
                    )

        return retValue

    def build(self, hosts):
        ops = {}
        ips = {}
        for h, v in self._getVMs(hosts).items():
            if v['status'] is None:
                click.echo("  - Creating host: {} ".format(h))
                r = v['insert'].execute()
                ops[h] = {'name': r['name'], 'project': hosts[h]['project'], 'zone': hosts[h]['zone']}
                ips[h] = None
            elif v['status'] == 'TERMINATED':
                click.echo("  - Booting host: {} ".format(h))
                self.compute.instances().start(project=hosts[h]['project'], zone=hosts[h]['zone'], instance=v['name']).execute()
            elif v['status'] == "RUNNING":
                click.echo("  - Already up host: {} ".format(h))
            else:
                click.echo("  - Status of host: {} is {}".format(h, v['status']))

        self._waitDone(ops, "  - Host {} created")
        for h, v in self._getVMs(hosts).items():
            if v['values'].get('dns_external', False):
                ips[h] = v['networkInterfaces'][0]['accessConfigs'][0]['natIP']
            else:
                ips[h] = v['networkInterfaces'][0]['networkIP']

        dnsUpdate(ips)

    def up(self, hosts):
        for h, v in self._getVMs(hosts).items():
            if v['status'] is None:
                click.echo("  - No such host: {} ".format(h))
            elif v['status'] == 'TERMINATED':
                click.echo("  - Booting host: {} ".format(h))
                self.compute.instances().start(project=hosts[h]['project'], zone=hosts[h]['zone'], instance=v['name']).execute()
            elif v['status'] == "RUNNING":
                click.echo("  - Already up host: {} ".format(h))
            else:
                click.echo("  - Status of host: {} is {}".format(h, v['status']))

    def halt(self, hosts):
        for h, v in self._getVMs(hosts).items():
            if v['status'] is None:
                click.echo("  - No such host: {} ".format(h))
            if v['status'] == "RUNNING":
                click.echo("  - Halting host: {} ".format(h))
                self.compute.instances().stop(project=hosts[h]['project'], zone=hosts[h]['zone'], instance=v['name']).execute()
            else:
                click.echo("  - Status of host: {} is {}".format(h, v['status']))

    def destroy(self, hosts):
        updateHosts = {}
        ops = {}
        for h, v in self._getVMs(hosts).items():
            if v['status'] is not None:
                click.echo("  - Destroying host: {} ".format(h))
                r = self.compute.instances().delete(project=hosts[h]['project'], zone=hosts[h]['zone'], instance=v['name']).execute()
                ops[h] = {'name': r['name'], 'project': hosts[h]['project'], 'zone': hosts[h]['zone']}
                updateHosts[h] = {}
            else:
                click.echo("  - Host does not exists : {}".format(h))

        self._waitDone(ops, "  - Host {} destroyed")
        dnsRemove(updateHosts)

    def dnsupdate(self, hosts):
        ips = {}
        for h, v in self._getVMs(hosts).items():
            if v['values'].get('dns_external', False):
                ips[h] = v['networkInterfaces'][0]['accessConfigs'][0]['natIP']
            else:
                ips[h] = v['networkInterfaces'][0]['networkIP']

        dnsUpdate(ips)

    def dnsremove(self, hosts):
        ips = {}
        for h in hosts:
            if hosts[h]['enabled']:
                ips[h] = None

        dnsRemove(hosts)

    def snapCreate(self, hosts):
        pass

    def snapRestore(self, hosts):
        pass

    def snapDelete(self, hosts):
        pass

    def config(self):
        if 'service-key' in self.cfg:
            return "service-key: {}{}".format(CONFIG_PATH, self.cfg['service-key'])
        else:
            return "client-secret: {}{}".format(CONFIG_PATH, self.cfg['client-secret'])

    def status(self):
        return "PASS"

    def params(self, params):
        return {k: params[k] for k in ['size', 'image']}
