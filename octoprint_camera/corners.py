#!/usr/bin/env python
from __future__ import absolute_import, print_function, unicode_literals, division

"""
Set of functions to transform a picture to conform with real world coordinates.
"""
import os
from octoprint_mrbeam.camera import corners, lens
from octoprint_mrbeam.camera.definitions import QD_KEYS
from octoprint_mrbeam.camera.undistort import _getColoredMarkerPositions
from octoprint_mrbeam.camera.corners import add_deltas, warpImgByCorners

from . import util

# This path will change to be cornerNW.jpg etc...
DEBUG_CORNERS_PATH="/tmp/.jpg"

def find_pink_circles(img, debug=False, **settings):
    if debug:
        settings.update(dict(debug_out_path=DEBUG_CORNERS_PATH))
        # Hack : symlink the debug images in the tm folder to the uploads folder
        for qd in QD_KEYS:
            img_name = ""+qd+".jpg"
            sym_path = "/home/pi/.octoprint/uploads/cam/debug/" + img_name
            target = "/tmp/"+ img_name
            if not os.path.islink(sym_path):
                os.symlink(
                    target,
                    sym_path,
                )
    return _getColoredMarkerPositions(img, **settings)

def get_workspace_corners(positions_pink_circles, pic_settings):
    return add_deltas(positions_pink_circles, pic_settings, False, from_factory=util.factory_mode())

def fit_img_to_corners(img, positions_workspace_corners, zoomed_out=True):
    """
    Warps the region delimited by the corners in order to straighten it.
    :param image: takes an opencv (numpy) image
    :param corners: as qd-dict {'NW': [x, y], ... }
    :param zoomed_out: wether to zoom out the pic to account for object height
    :return: image that was transformed and cropped to fit the real world measurements
    """
    return warpImgByCorners(img, positions_workspace_corners, zoomed_out)

def save_corner_calibration(path, *a, **kw):
    return corners.save_corner_calibration(path, *a, **kw)

def get_corner_calibration(pic_settings):
    return corners.get_corner_calibration(pic_settings)