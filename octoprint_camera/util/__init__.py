from __future__ import absolute_import
import os

from octoprint_mrbeam.util import \
    logExceptions, logtime, logme, \
    dict_merge, dict_map, dict_get, \
    get_thread, \
    makedirs
from octoprint_mrbeam.support import CALIBRATION_STICK_FILE_PATH


def factory_mode():
    # TODO - Phase 2 - Make it dependent on the sticks 
    return True
    return os.path.isfile(CALIBRATION_STICK_FILE_PATH)