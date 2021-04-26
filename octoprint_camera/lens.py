#!/usr/bin/env python3

from octoprint_mrbeam.camera.lens import undistort, BoardDetectorDaemon, undist_points

def capture_img_for_lens_calibration(board_detect_thread, camera_thread):
    path = board_detect_thread.next_tmp_img_name() # From board_detect
    img = camera_thread.get_next_img()
    with open(path, 'wb') as f:
        f.write(img)
    board_detect_thread.add(path)
