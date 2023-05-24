
import pwd
import os

from octoprint_mrbeam.util import (
    logExceptions,
    logtime,
    dict_merge,
    dict_map,
    dict_get,
    get_thread,
    makedirs,
)
from octoprint_mrbeam.support import CALIBRATION_STICK_FILE_PATH


def factory_mode():
    # username = pwd.getpwuid(os.getuid())[0]
    return (
        os.path.isfile(CALIBRATION_STICK_FILE_PATH) and len(os.listdir("/media/")) > 0
    )
