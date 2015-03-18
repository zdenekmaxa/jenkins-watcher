"""
Setup script for unittets, paths adjustments ...

"""

import os
import sys

# check PYTHONPATH if AppEngine libs path is set
# the list can container OS platform specific locations
# so that this script be shared
#
SDK_PATHS = [
    "/Applications/GoogleAppEngineLauncher.app/Contents/Resources/GoogleAppEngine-default.bundle/Contents/Resources/google_appengine",
    "/usr/local/soft/google_appengine",
    "/usr/local/soft/google-cloud-sdk/platform/google_appengine"
]

for path in SDK_PATHS:
    if os.path.exists(path):
        break
sys.path.insert(0, path)

# add project directory into PYTHONPATH
PROJECT_DIR = os.path.split(os.path.dirname(os.path.abspath(__file__)))[0]
sys.path.insert(0, PROJECT_DIR)

import appengine_config
import dev_appserver
dev_appserver.fix_sys_path()