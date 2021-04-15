#!/usr/bin/env python3

from datetime import datetime
import logging

from octoprint_mrbeam.camera.definitions import (
    TMP_RAW_FNAME_RE,
    STATE_SUCCESS,
    CAMERA_HEIGHT,
    DIST_KEY,
    ERR_NEED_CALIB,
    LEGACY_STILL_RES,)
# camera is a function that creates a new Camera object
# or returns the currently used camera object
from octoprint_mrbeam.camera.mrbcamera import mrbCamera
from octoprint_mrbeam.camera.worker import MrbPicWorker

from .util import get_thread


class CameraThread(object):
    def __init__(self, settings, debug=False):
        self._logger = logging.getLogger(__name__)
        self.settings = settings
        self.debug = debug
        self._stop = False
        self._active = False
        self._cam = None
        self._thread = None
        self.latest_img_timestamp = None

    def start(self):
        if self._thread:
            self._thread.start()
        else:
            self._thread = self._camera_run()

    @get_thread(daemon=True)
    def _camera_run(self):
        camera_worker = MrbPicWorker(maxlen=2, debug=self.debug)
        self._logger.debug("Starting the camera now.")
        self._active = True
        with mrbCamera(
            camera_worker,
            framerate=1,
            resolution=LEGACY_STILL_RES,  # TODO camera.DEFAULT_STILL_RES,
        ) as self._cam:
            while not self._stop:
                self._cam.capture()
                self._logger.debug("Image captured!")
                self.latest_img_timestamp = datetime.now()
        self._active = False

    def stop(self, blocking=True):
        self._stop = True
        if blocking:
            self._thread.join()

    def active(self):
        return self._active

    def stopping(self):
        return self.active() and self._stop

    def get_latest_img(self):
        # TODO read locks
        return self._cam.worker[1]

    def get_next_img(self):
        self._cam.wait()
        return self.get_latest_img()
