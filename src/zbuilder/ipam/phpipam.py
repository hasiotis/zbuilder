import click
import requests
import urllib3

from zbuilder.base import IPAMProvider

urllib3.disable_warnings()


class ipamProvider(IPAMProvider):
    def __init__(self, cfg):
        super().__init__(cfg)
        if cfg:
            self.username = cfg["username"]
            self.password = cfg["password"]
            self.ssl = cfg.get("ssl", True)
            self.verify = cfg.get("verify", True)
            self.server = "http{}://{}".format("s" if self.ssl else "", cfg["server"])
            self.headers = {"Content-Type": "application/json"}
            self._refresh_token()

    def _refresh_token(self):
        url = f"{self.server}/api/zbuilder/user/"
        try:
            r = requests.post(
                url,
                auth=(self.username, self.password),
                verify=self.verify,
                headers=self.headers,
            )
        except requests.exceptions.RequestException as e:
            raise click.ClickException(f"Error {e}") from e
        if r.status_code == 200:
            j = r.json()
            if "data" in j:
                self.headers["token"] = j["data"]["token"]
        else:
            j = r.json()
            raise click.ClickException(j["message"])

    def _get_subnet(self, subnet):
        url = f"{self.server}/api/zbuilder/subnets/cidr/{subnet}"
        r = requests.get(url, headers=self.headers, verify=self.verify)
        j = r.json()
        if j["data"]:
            return j["data"][0]["id"]

    def _get_subnet_gw(self, sid):
        url = f"{self.server}/api/zbuilder/subnets/{sid}"
        r = requests.get(url, headers=self.headers, verify=self.verify)
        j = r.json()
        if j["data"]:
            return j["data"]["gateway"]["ip_addr"]

    def _locate(self, sid, host):
        url = f"{self.server}/api/zbuilder/subnets/{sid}/addresses"
        r = requests.get(url, headers=self.headers, verify=self.verify)
        j = r.json()
        if j["success"]:
            for r in j["data"]:
                if r["hostname"] == host:
                    return r["ip"]

    def release(self, host, ip, subnet):
        self._refresh_token()
        url = f"{self.server}/api/zbuilder/addresses/search/{ip}"
        r = requests.get(url, headers=self.headers, verify=self.verify)
        j = r.json()
        if j["code"] == 200 and j["data"][0]["hostname"] == host:
            ipid = j["data"][0]["id"]
            if j["data"][0]["tag"] == "3":
                click.echo(f"      Not removing ip [{ip}] due to reservation")
            else:
                click.echo(f"      Releasing ip [{ip}] for host [{host}]")
                url = f"{self.server}/api/zbuilder/addresses/{ipid}/"
                r = requests.delete(url, headers=self.headers, verify=self.verify)

    def reserve(self, host, subnet):
        self._refresh_token()
        sid = self._get_subnet(subnet)
        gw = self._get_subnet_gw(sid)
        ip = self._locate(sid, host)
        if not ip:
            url = f"{self.server}/api/zbuilder/subnets/{sid}/first_free/"
            r = requests.get(url, headers=self.headers, verify=self.verify)
            j = r.json()
            ip = j["data"]
            click.echo(f"      Reserving ip [{ip}] for host [{host}]")
            url = f"{self.server}/api/zbuilder/addresses"
            data = {"subnetId": sid, "ip": ip, "hostname": host}
            r = requests.post(url, json=data, headers=self.headers, verify=self.verify)
            j = r.json()
            if not j["success"]:
                ip = None

        return ip, gw

    def locate(self, host, subnet):
        self._refresh_token()
        sid = self._get_subnet(subnet)
        gw = self._get_subnet_gw(sid)
        ip = self._locate(sid, host)
        return ip, gw

    def config(self):
        return f"server: {self.cfg['server']}, username: {self.cfg['username']}"

    def status(self):
        return "PASS"
