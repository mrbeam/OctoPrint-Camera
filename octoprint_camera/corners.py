#!/usr/bin/env python
from __future__ import absolute_import, print_function, unicode_literals, division

"""
Set of functions to transform a picture to conform with real world coordinates.
"""

from octoprint_mrbeam.camera.undistort import _getColoredMarkerPositions
from octoprint_mrbeam.camera.corners import add_deltas, warpImgByCorners

def find_pink_circles(img, **settings):
    return _getColoredMarkerPositions(img, **settings)

def get_workspace_corners(positions_pink_circles, **settings):
    return add_deltas(positions_pink_circles, **settings)

def fit_img_to_corners(img, positions_workspace_corners, zoomed_out=True):
    """
    Warps the region delimited by the corners in order to straighten it.
    :param image: takes an opencv (numpy) image
    :param corners: as qd-dict {'NW': [x, y], ... }
    :param zoomed_out: wether to zoom out the pic to account for object height
    :return: image that was transformed and cropped to fit the real world measurements
    """
    return warpImgByCorners(img, positions_workspace_corners, zoomed_out)
