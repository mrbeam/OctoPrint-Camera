#!/usr/bin/env python3
from __future__ import absolute_import, print_function, unicode_literals, division

from datetime import datetime
import logging

from octoprint_mrbeam.camera.definitions import LEGACY_STILL_RES

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
        self._logger.info("Starting camera Thread")
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
            framerate=0.5,
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
        if self._cam:
            return self._cam.worker[1]
        else:
            self._logger.warning("Camera not initalised, cannot return an image")
            return None

    def get_next_img(self):
        # Disgusting hack: Fix race condition with a sleep because I am myself deprived of some
        import time

        time.sleep(1.0)
        # Even if we wait for the camera to be available,
        # we will be getting the image that was taken during this call
        # hack : sleep an extra frame time
        self._cam.wait()
        return self.get_latest_img()
