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
