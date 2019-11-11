class dnsProvider(object):
    def __init__(self, cfg):
        self.cfg = cfg

    def update(self, host, zone, ip):
        pass

    def remove(self, host, zone):
        pass
