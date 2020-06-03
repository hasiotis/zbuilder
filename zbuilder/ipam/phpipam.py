import click
import requests
import urllib3


urllib3.disable_warnings()


class ipamProvider(object):
    def __init__(self, cfg):
        if cfg:
            self.cfg = cfg
            self.username = cfg['username']
            self.password = cfg['password']
            self.ssl = cfg.get('ssl', True)
            self.verify = cfg.get('verify', True)
            self.server = "http{}://{}".format('s' if self.ssl else '', cfg['server'])
            self.token = None
            self._refresh_token()

    def _refresh_token(self):
        url = "{}/api/zbuilder/user/".format(self.server)
        try:
            r = requests.post(url, auth=(self.username, self.password), verify=self.verify)
        except Exception as e:
            click.echo("Error {}".format(e))
        if r.status_code == 200:
            j = r.json()
            if 'data' in j:
                self.token = j['data']['token']
        else:
            j = r.json()
            raise Exception(j['message'])

    def _get_subnet(self, subnet):
        url = "{}/api/zbuilder/subnets/cidr/{}".format(self.server, subnet)
        r = requests.get(url, headers={'token': self.token}, verify=self.verify)
        j = r.json()
        if j['data']:
            return j['data'][0]['id']

    def _get_subnet_gw(self, sid):
        url = "{}/api/zbuilder/subnets/{}".format(self.server, sid)
        r = requests.get(url, headers={'token': self.token}, verify=self.verify)
        j = r.json()
        if j['data']:
            return j['data']['gateway']['ip_addr']

    def _locate(self, sid, host):
        url = "{}/api/zbuilder/subnets/{}/addresses/".format(self.server, sid)
        r = requests.get(url, headers={'token': self.token}, verify=self.verify)
        j = r.json()
        for r in j['data']:
            if r['hostname'] == host:
                return r['ip']

    def release(self, host, ip, subnet):
        self._refresh_token()
        url = "{}/api/zbuilder/addresses/search/{}".format(self.server, ip)
        r = requests.get(url, headers={'token': self.token}, verify=self.verify)
        j = r.json()
        if j['code'] == 200 and j['data'][0]['hostname'] == host:
            ipid = j['data'][0]['id']
            if j['data'][0]['tag'] == '3':
                click.echo("      Not removing ip [%s] due to reservation" % ip)
            else:
                click.echo("      Releasing ip [{}] for host [{}]".format(ip, host))
                url = "{}/api/zbuilder/addresses/{}/".format(self.server, ipid)
                r = requests.delete(url, headers={'token': self.token}, verify=self.verify)

    def reserve(self, host, subnet):
        self._refresh_token()
        sid = self._get_subnet(subnet)
        gw = self._get_subnet_gw(sid)
        ip = self._locate(sid, host)
        if not ip:
            url = "{}/api/zbuilder/subnets/{}/first_free/".format(self.server, sid)
            r = requests.get(url, headers={'token': self.token}, verify=self.verify)
            j = r.json()
            ip = j['data']
            click.echo("      Reserving ip [{}] for host [{}]".format(ip, host))
            url = "{}/api/zbuilder/addresses".format(self.server)
            data = {'subnetId': sid, 'ip': ip, 'hostname': host}
            r = requests.post(url, data=data, headers={'token': self.token}, verify=self.verify)
            j = r.json()
            if not j['success']:
                ip = None

        return ip, gw

    def locate(self, host, subnet):
        self._refresh_token()
        sid = self._get_subnet(subnet)
        gw = self._get_subnet_gw(sid)
        ip = self._locate(sid, host)
        return ip, gw

    def config(self):
        return "server: {v[server]}, username: {v[username]}".format(v=self.cfg)

    def status(self):
        return 'PASS'
