#!/usr/bin/env python3
import os
from octoprint_mrbeam.camera.lens import undistort, BoardDetectorDaemon, undist_points
from octoprint_mrbeam.camera import save_debug_img

def capture_img_for_lens_calibration(board_detect_thread, camera_thread, datafolder=None):
    path = board_detect_thread.next_tmp_img_name() # From board_detect
    if datafolder:
        path = os.path.join(datafolder, path)
    img = camera_thread.get_next_img()
    with open(path, 'wb') as f:
        f.write(img.getvalue())
    board_detect_thread.add(str(path))
