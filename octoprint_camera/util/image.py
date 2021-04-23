#!/usr/bin/env python3
import cv2
import logging
import numpy as np

from octoprint_mrbeam.util.img import differed_imwrite
from octoprint_mrbeam.camera.definitions import SUCCESS_WRITE_RETVAL

def imdecode(stream, flags=cv2.IMREAD_COLOR):
    """Tries to convert an io.BytesIO buffer into an cv2/numpy image"""
    streamval = stream.getvalue()
    if not streamval:
        return 
    return cv2.imdecode(
        np.fromstring(streamval, np.int8), flags
    )

def imwrite(buff, cv2_img, *a, **kw):
    """
    Write a cv2/numpy image to an io.BytesIO buffer or a filepath (str)
    returns True if successful
    """
    return cv2.imwrite(buff, cv2_img, *a, **kw) == SUCCESS_WRITE_RETVAL

def corner_settings_valid(settings):
    from typing import Mapping
    from octoprint_mrbeam.camera.config import is_corner_calibration
    return (
        isinstance(settings, Mapping) 
        and is_corner_calibration(settings)
    )

def lens_settings_valid(settings):
    #from octoprint_mrbeam.camera.config import  is_lens_calibration_file
    from typing import Mapping
    return (
        isinstance(settings, Mapping) 
        and all(k in settings.keys() for k in ("mtx", "dist"))
    )

class SettingsError(Exception):
    pass