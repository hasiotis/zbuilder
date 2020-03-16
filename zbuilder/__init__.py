import os
import site

__version__ = '0.0.15'


def getAssetsDir():
    try:
        USER_BASE = os.path.join(site.getuserbase(), 'zbuilder', 'assets')
    except Exception:
        this_dir, _ = os.path.split(__file__)
        USER_BASE = os.path.join(this_dir, 'assets')

    if os.path.exists(USER_BASE):
        return USER_BASE
    else:
        this_dir, _ = os.path.split(__file__)
        return os.path.join(this_dir, 'assets')
