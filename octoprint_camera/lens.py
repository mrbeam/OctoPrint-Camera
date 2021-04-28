#!/usr/bin/env python3
from __future__ import absolute_import, print_function, unicode_literals, division

import os
import octoprint_mrbeam
from octoprint_mrbeam.camera.lens import undistort, undist_points
from octoprint_mrbeam.camera import lens, save_debug_img


def capture_img_for_lens_calibration(board_detect_thread, camera_thread, datafolder=None):
    path = board_detect_thread.next_tmp_img_name() # From board_detect
    if datafolder:
        path = os.path.join(datafolder, path)
    img = camera_thread.get_next_img()
    with open(path, 'wb') as f:
        f.write(img.getvalue())
    board_detect_thread.add(str(path))

SYMLINK_IMG_DIR = symlink_path = "/home/pi/.octoprint/uploads/cam/debug"

class BoardDetectorDaemon(lens.BoardDetectorDaemon):
    def __init__(self, 
        output_calib,
        stateChangeCallback=None,
        rawImgLock=None,
        *a, **kw
    ):
        self.state = CalibrationState(
            changeCallback=stateChangeCallback,
            npzPath=output_calib,
            rawImgLock=rawImgLock,
        )
        lens.BoardDetectorDaemon.__init__(
            self,
            output_calib,
            stateChangeCallback=stateChangeCallback,
            rawImgLock=stateChangeCallback,
            *a, **kw
        )

class CalibrationState(lens.CalibrationState):
    # Add / Remove symlink to uploads/cam/debug folder
    def add(
        self, path, *a, **kw
    ):
        lens.CalibrationState.add(self, path, *a, **kw)
        octoprint_mrbeam.util.makedirs(SYMLINK_IMG_DIR)
        symlink_path = os.path.join(SYMLINK_IMG_DIR, os.path.basename(path))
        if not os.path.islink(symlink_path):
            os.symlink(path, symlink_path)

    def remove(self, path):
        lens.BoardDetectorDaemon.remove(self, path)
        symlink_path = os.path.join(SYMLINK_IMG_DIR, os.path.basename(path))
        if os.path.islink(symlink_path):
            os.remove(symlink_path)