#!/usr/bin/env python3
import cv2
import numpy as np

from moctoprint_mrbeam.util.img import differed_imwrite

def imdecode(stream, flags=cv2.IMREAD_COLOR):
    """Tries to convert an io.BytesIO buffer into an cv2/numpy image"""
    return cv2.imdecode(
        np.fromstring(stream.getvalue(), np.int8), flags
    )

def imwrite(buff, cv2_img, *a, **kw):
    return cv2.imwrite(buff, cv2_img, *a, **kw) == SUCCESS_WRITE_RETVAL
