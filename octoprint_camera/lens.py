#!/usr/bin/env python3
from __future__ import absolute_import, print_function, unicode_literals, division

import os
import octoprint_mrbeam
from octoprint_mrbeam.camera.lens import undistort, undist_dict
from octoprint_mrbeam.camera import lens, save_debug_img
from octoprint_mrbeam.camera.definitions import CB_ROWS, CB_COLS, STATE_PENDING_CAMERA
from .util.flask import file_to_b64

def capture_img_for_lens_calibration(board_detect_thread, camera_thread, datafolder=None):
    path = board_detect_thread.next_tmp_img_name() # From board_detect
    if datafolder:
        path = os.path.join(datafolder, path)
    img = camera_thread.get_next_img()
    ts = camera_thread.latest_img_timestamp
    with open(path, 'wb') as f:
        f.write(img.getvalue())
    board_detect_thread.add(str(path), extra_kw=dict(timestamp=ts))

SYMLINK_IMG_DIR = "/home/pi/.octoprint/uploads/cam/debug"

class BoardDetectorDaemon(lens.BoardDetectorDaemon):
    def __init__(self, 
        output_calib,
        stateChangeCallback=None,
        rawImgLock=None,
        **kw
    ):
        lens.BoardDetectorDaemon.__init__(
            self,
            output_calib,
            stateChangeCallback=stateChangeCallback,
            rawImgLock=rawImgLock,
            state=CalibrationState(
                changeCallback=stateChangeCallback,
                npzPath=output_calib,
                rawImgLock=rawImgLock,
            ),
            **kw
        )
    
    def add(
        self,
        image,
        chessboardSize=(CB_ROWS+1, CB_COLS+3),
        state=STATE_PENDING_CAMERA,
        index=None,
        **kw
    ):
        """prototype board detection with 1 extra row + 3 extra columns"""
        return lens.BoardDetectorDaemon.add(
            self, 
            image,
            chessboardSize=chessboardSize,
            state=state,
            index=index,
            **kw
        )

    def get_images(self, timestamp):
        recorded_images = self.state.get_from_timestamp(timestamp)
        for img_path in recorded_images.keys():
            recorded_images[img_path]["image"] = file_to_b64(img_path)
        return recorded_images
            

class CalibrationState(lens.CalibrationState):
    # Add / Remove symlink to uploads/cam/debug folder
    def add(
        self, path, *a, **kw
    ):
        lens.CalibrationState.add(self, path, *a, **kw)
        octoprint_mrbeam.util.makedirs(SYMLINK_IMG_DIR)
        symlink_path = os.path.join(SYMLINK_IMG_DIR, os.path.basename(path))
        self._logger.warning("Symlink %s PATH %s", symlink_path, path)
        if not os.path.islink(symlink_path):
            os.symlink(path, symlink_path)

    def remove(self, path):
        lens.CalibrationState.remove(self, path)
        symlink_path = os.path.join(SYMLINK_IMG_DIR, os.path.basename(path))
        self._logger.warning("Symlink %s PATH %s", symlink_path, path)
        if os.path.islink(symlink_path):
            os.remove(symlink_path)