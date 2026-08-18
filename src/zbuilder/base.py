"""Base classes for provider plugins.

Every provider subclasses the base class of its family, and that base class is
the contract: `@abstractmethod` marks the actions a provider must implement,
the concrete methods are the defaults for the actions it may skip.
"""

from abc import ABC, abstractmethod

import click


class UnsupportedAction(click.ClickException):
    """Raised when a provider does not implement an optional action"""

    def __init__(self, provider, action):
        super().__init__("Provider [{}] does not implement action [{}]".format(provider, action))


class Provider(ABC):
    """Common behaviour of every provider plugin"""

    #: Entry point name the provider was loaded as, set by the loader facades
    factory = None

    def __init__(self, cfg=None):
        self.cfg = cfg

    def _unsupported(self, action):
        """Report an action this provider does not support"""
        raise UnsupportedAction(self.factory or type(self).__module__.rpartition(".")[2], action)

    def config(self):
        """Human readable summary of the credentials in use"""
        self._unsupported("config")

    def status(self):
        """Either "PASS" or the reason the provider is not usable"""
        self._unsupported("status")


class VMProvider(Provider):
    """A cloud able to create and manage VMs"""

    @abstractmethod
    def build(self, hosts):
        """Create the enabled hosts"""

    @abstractmethod
    def up(self, hosts):
        """Boot the enabled hosts"""

    @abstractmethod
    def halt(self, hosts):
        """Shut down the enabled hosts"""

    @abstractmethod
    def destroy(self, hosts):
        """Delete the enabled hosts"""

    def dnsupdate(self, hosts):
        """Publish the DNS records of the enabled hosts"""
        self._unsupported("dnsupdate")

    def dnsremove(self, hosts):
        """Withdraw the DNS records of the enabled hosts"""
        self._unsupported("dnsremove")

    def snapCreate(self, hosts):
        """Snapshot the enabled hosts"""
        self._unsupported("snapCreate")

    def snapRestore(self, hosts):
        """Restore the enabled hosts from their snapshot"""
        self._unsupported("snapRestore")

    def snapDelete(self, hosts):
        """Delete the snapshot of the enabled hosts"""
        self._unsupported("snapDelete")

    def params(self, params):
        """The VM options of a host, as shown by the summary"""
        self._unsupported("params")

    def enabled(self):
        """Whether the provider can be used on this machine"""
        return True


class DNSProvider(Provider):
    """A DNS zone able to hold the records of the VMs"""

    @abstractmethod
    def update(self, host, zone, ip):
        """Point the A record of `host` in `zone` to `ip`"""

    @abstractmethod
    def remove(self, host, zone):
        """Drop the A record of `host` in `zone`"""


class IPAMProvider(Provider):
    """An IPAM able to hand out addresses of the subnets of the VMs"""

    @abstractmethod
    def reserve(self, host, subnet):
        """Reserve an address of `subnet` for `host` and return it"""

    @abstractmethod
    def locate(self, host, subnet):
        """Return the address of `subnet` already reserved for `host`"""

    @abstractmethod
    def release(self, host, ip, subnet):
        """Give the address of `host` back to `subnet`"""
