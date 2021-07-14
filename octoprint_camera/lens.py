#!/usr/bin/env python3
from __future__ import absolute_import, print_function, unicode_literals, division

import os
import octoprint_mrbeam
from octoprint_mrbeam.camera import lens
from octoprint_mrbeam.camera.definitions import STATE_PENDING_CAMERA

from .util.flask import file_to_b64

BOARD_COLS = 9
BOARD_ROWS = 6


def capture_img_for_lens_calibration(
    board_detect_thread, camera_thread, datafolder=None
):
    path = board_detect_thread.next_tmp_img_name()  # From board_detect
    if datafolder:
        path = os.path.join(datafolder, path)
    img = camera_thread.get_next_img()
    ts = camera_thread.latest_img_timestamp
    with open(path, "wb") as f:
        f.write(img.getvalue())
    board_detect_thread.add(str(path), extra_kw=dict(timestamp=ts))


SYMLINK_IMG_DIR = "/home/pi/.octoprint/uploads/cam/debug"


class BoardDetectorDaemon(lens.BoardDetectorDaemon):
    def __init__(
        self,
        output_calib,
        stateChangeCallback=None,
        rawImgLock=None,
        debugPath=SYMLINK_IMG_DIR,
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
                debugPath=debugPath,
            ),
            **kw
        )

    def add(
        self,
        image,
        chessboardSize=(BOARD_ROWS, BOARD_COLS),
        state=STATE_PENDING_CAMERA,
        index=None,
        **kw
    ):
        """prototype board detection with 1 extra row + 3 extra columns"""
        return lens.BoardDetectorDaemon.add(
            self, image, chessboardSize=chessboardSize, state=state, index=index, **kw
        )

    def get_images(self, timestamp):
        recorded_images = self.state.get_from_timestamp(timestamp)
        for img_path in recorded_images.keys():
            recorded_images[img_path]["image"] = file_to_b64(img_path)
        return recorded_images


class CalibrationState(lens.CalibrationState):
    def __init__(self, debugPath=SYMLINK_IMG_DIR, **kw):
        self.debugPath = debugPath
        lens.CalibrationState.__init__(self, **kw)

    # Add / Remove symlink to uploads/cam/debug folder
    def add(self, path, *a, **kw):
        lens.CalibrationState.add(self, path, *a, **kw)
        octoprint_mrbeam.util.makedirs(self.debugPath)
        symlink_path = os.path.join(self.debugPath, os.path.basename(path))
        if not os.path.islink(symlink_path):
            os.symlink(path, symlink_path)

    def remove(self, path):
        lens.CalibrationState.remove(self, path)
        symlink_path = os.path.join(self.debugPath, os.path.basename(path))
        if os.path.islink(symlink_path):
            os.remove(symlink_path)
