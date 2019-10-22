import os
import site

def getAssetsDir():
    USER_BASE = os.path.join(site.getuserbase(), 'zbuilder', 'assets')
    if os.path.exists(USER_BASE):
        return USER_BASE
    else:
        this_dir, _ = os.path.split(__file__)
        return os.path.join(this_dir, 'assets')
