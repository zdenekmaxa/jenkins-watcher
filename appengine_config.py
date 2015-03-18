"""
The AppEngine configuration.

The file gets run automatically in the production environment.

"""

import os
import sys


# if there are python libraries in the libs directory:
#LIB_PROJECT_DIR = os.path.join(os.path.dirname(__file__), "libs")
#sys.path.insert(0, LIB_PROJECT_DIR)

# in case of egg files in the libs directory:
from config import egg_files

for egg_file in egg_files:
    sys.path.append(os.path.join(os.path.dirname(__file__), "libs", egg_file))