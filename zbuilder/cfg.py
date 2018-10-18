import os

from zbuilder.helpers import load_yaml
from zbuilder.helpers import dump_yaml

def load():
    fname = os.path.expanduser("~/.config/zbuilder/zbuilder.yaml")
    return load_yaml(fname)


def view(cfg):
    dump_yaml(cfg)
