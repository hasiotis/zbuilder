import zbuilder.plugins


def vmProvider(factory, cfg=None):
    """Instantiate the VM provider registered as `factory`"""
    provider = zbuilder.plugins.load(zbuilder.plugins.VM, factory)(cfg)
    provider.factory = factory
    return provider
