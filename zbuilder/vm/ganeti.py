import time
import click
import urllib3
import requests
import ipaddress

from zbuilder.dns import dnsUpdate, dnsRemove

SLEEP_TIME = 5
urllib3.disable_warnings()


class vmProvider(object):
    def __init__(self, cfg):
        if cfg:
            self.cfg = cfg
            self.user = self.cfg['user']
            self.apikey = self.cfg['apikey']
            self.url = self.cfg['url']
            self.verify = self.cfg.get('verify', True)

    def _getJob(self, jobid):
        retValue = None
        url = "{}/2/jobs/{}".format(self.url, jobid)
        status = 'running'
        while status != 'success':
            time.sleep(2)
            r = requests.get(url, auth=(self.user, self.apikey), verify=self.verify)
            retValue = r.json()
            status = retValue['status']
            if r.status_code != requests.codes.ok:
                click.echo('Failed: [{v[message]} :: {v[explain]}]'.format(v=retValue))
                retValue = None
            elif status == 'running':
                time.sleep(SLEEP_TIME)

        return retValue

    def _getInfoVM(self, name):
        url = "{}/2/instances/{}/info".format(self.url, name)
        r = requests.get(url, auth=(self.user, self.apikey), verify=self.verify)
        if r.status_code != requests.codes.ok:
            j = r.json()
            click.echo('Failed: [{v[message]} :: {v[explain]}]'.format(v=j))
            return None

        jobid = r.text.rstrip('\n')
        j = self._getJob(jobid)

        for nic in j['opresult'][0][name]['nics'][0]:
            if isinstance(nic, dict) and 'ext_reservations' in nic:
                del nic['ext_reservations']
            if isinstance(nic, dict) and 'reservations' in nic:
                del nic['reservations']
            try:
                j['opresult'][0][name]['ip-address'] = str(ipaddress.ip_address(nic))
            except Exception:
                pass

        return j['opresult'][0][name]

    def _getVMs(self, hosts):
        retValue = {}
        url = "{}/2/instances".format(self.url)
        r = requests.get(url, auth=(self.user, self.apikey), verify=self.verify)
        j = r.json()
        if r.status_code != requests.codes.ok:
            click.echo('Failed: [{v[message]} :: {v[explain]}]'.format(v=j))
            return None

        foundVMs = [h['id'] for h in j]
        for h, v in hosts.items():
            if hosts[h]['enabled']:
                if h in foundVMs:
                    retValue[h] = self._getInfoVM(h)
                    retValue[h]['found'] = True
                else:
                    retValue[h] = {}
                    retValue[h]['found'] = False
                    retValue[h]['api'] = v
                    del retValue[h]['api']['ZBUILDER_PUBKEY']
                    del retValue[h]['api']['ZBUILDER_SYSUSER']
                    del retValue[h]['api']['enabled']
                    del retValue[h]['api']['aliases']
                    retValue[h]['api']['__version__'] = 1
                    retValue[h]['api']['hypervisor'] = 'kvm'
                    retValue[h]['api']['instance_name'] = h
                    retValue[h]['api']['name_check'] = False
                    retValue[h]['api']['ip_check'] = False
                    retValue[h]['api']['mode'] = 'create'

        return retValue

    def _findIP(self, nics):
        for nic in nics:
            try:
                return str(ipaddress.ip_address(nic))
            except Exception:
                pass

    def build(self, hosts):
        ips = {}
        for h, v in self._getVMs(hosts).items():
            if v['found']:
                click.echo("  - Status of host: {} is {}".format(h, v['run_state']))
                ips[h] = self._findIP(v['nics'][0])
            else:
                click.echo("  - Creating host: {} ".format(h))
                url = "{}/2/instances".format(self.url)
                r = requests.post(url, auth=(self.user, self.apikey), verify=self.verify, json=v['api'])
                if r.status_code != requests.codes.ok:
                    j = r.json()
                    click.echo('Failed: [{v[message]} :: {v[explain]}]'.format(v=j))

                jobid = r.text.rstrip('\n')
                j = self._getJob(jobid)
                j = self._getInfoVM(h)
                ips[h] = self._findIP(j['nics'][0])

        dnsUpdate(ips)

    def up(self, hosts):
        pass

    def halt(self, hosts):
        pass

    def destroy(self, hosts):
        updateHosts = {}
        for h, v in self._getVMs(hosts).items():
            if v['found']:
                click.echo("  - Destroying host: {} ".format(h))
                updateHosts[h] = {}
                url = "{}/2/instances/{}".format(self.url, h)
                r = requests.delete(url, auth=(self.user, self.apikey), verify=self.verify)

                jobid = r.text.rstrip('\n')
                j = self._getJob(jobid)

                if r.status_code != requests.codes.ok:
                    j = r.json()
                    click.echo('Failed: [{v[message]} :: {v[explain]}]'.format(v=j))
            else:
                click.echo("  - Host does not exists : {}".format(h))

        dnsRemove(updateHosts)

    def dnsupdate(self, hosts):
        ips = {}
        for h, v in self._getVMs(hosts).items():
            if 'ip-address' in v:
                ips[h] = v['ip-address']
        dnsUpdate(ips)

    def dnsremove(self, hosts):
        ips = {}
        for h in hosts:
            if hosts[h]['enabled']:
                ips[h] = None
        dnsRemove(hosts)

    def config(self):
        return "url: {}, user: {}".format(self.cfg['url'], self.cfg['user'])

    def status(self):
        return "PASS"

    def params(self, params):
        return {k: params[k] for k in ['beparams', 'disks', 'os_type', 'nics']}
