"""AWS provider tests.

No AWS here: the ec2 resource is swapped for a stand-in that records what
build() asks for.
"""

import types

import pytest

from zbuilder.vm import aws


class FakeEC2:
    def __init__(self, rootDevices):
        self.rootDevices = rootDevices
        self.created = []
        self.instances = types.SimpleNamespace(filter=lambda **_: [])

    def Image(self, ami):
        return types.SimpleNamespace(root_device_name=self.rootDevices[ami])

    def create_instances(self, **kwargs):
        self.created.append(kwargs)


@pytest.mark.parametrize("ami, rootDevice", [("ami-debian", "/dev/xvda"), ("ami-ubuntu", "/dev/sda1")])
def test_disksize_resizes_the_amis_own_root_device(monkeypatch, ami, rootDevice):
    monkeypatch.setattr(aws, "dnsUpdate", lambda ips: None)
    provider = aws.vmProvider({})
    provider.ec2 = FakeEC2({"ami-debian": "/dev/xvda", "ami-ubuntu": "/dev/sda1"})

    values = {"ami": ami, "vmtype": "t3.micro", "key": "k", "sg": ["sg-1"], "subnet": "subnet-1", "disksize": 30}
    provider.build({"host.example.com": {"enabled": True, **values}})

    (mapping,) = provider.ec2.created[0]["BlockDeviceMappings"]
    assert mapping["DeviceName"] == rootDevice
    assert mapping["Ebs"]["VolumeSize"] == 30
