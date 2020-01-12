from pyVmomi import vim
from pyVim.connect import SmartConnect, SmartConnectNoSSL


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

    def build(self, hosts):
        content = self.conn.RetrieveContent()
        esxi = self._get_obj(content, [vim.HostSystem], 'nuc.hasiotis.loc')
        print(esxi.summary)
        exit()

    def up(self, hosts):
        pass

    def halt(self, hosts):
        pass

    def destroy(self, hosts):
        pass

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
