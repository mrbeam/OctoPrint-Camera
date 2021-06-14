#!/usr/bin/env python3
from __future__ import absolute_import, print_function, unicode_literals, division

import os
import time
from collections import deque
from datetime import datetime
import logging
from distutils import dirname
from os.path import realpath, join

import octoprint_mrbeam
from octoprint.settings import settings
from octoprint_mrbeam.camera.definitions import LEGACY_STILL_RES

# camera is a function that creates a new Camera object
# or returns the currently used camera object
from octoprint_mrbeam.camera.exc import MrbCameraError
from octoprint_mrbeam.camera.mrbcamera import mrbCamera
from octoprint_mrbeam.camera.worker import MrbPicWorker
from octoprint_mrbeam.camera.dummy import DummyCamera as BaseDummyCamera

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

    #

    def get_next_img(self):
        # Disgusting hack: Fix race condition with a sleep because I am myself deprived of some
        import time

        time.sleep(1.0)
        # Even if we wait for the camera to be available,
        # we will be getting the image that was taken during this call
        # hack : sleep an extra frame time
        self._cam.wait()
        return self.get_latest_img()


class DummyCamera(BaseDummyCamera):
    def __init__(self, *args, **kwargs):

        # from os.path import dirname, basename, join, split, realpath
        #
        BaseDummyCamera.__init__(self, *args, **kwargs)
        # path = dirname(realpath(__file__))
        # CAM_DIR = join(path, "rsc", "camera")
        # try:
        #     self.def_pic = settings().get(
        #         ["mrbeam", "mock", "img_static"], defaults=settings().get(["webcam"])
        #     )
        #     self.def_folder = settings().get(["mrbeam", "mock", "img_folder"])
        # except ValueError:
        #     sett = settings(init=True)
        #     self.def_pic = sett.get(
        #         ["mrbeam", "mock", "img_static"], defaults=sett.get(["webcam"])
        #     )
        #     self.def_folder = sett.get(["mrbeam", "mock", "img_folder"])
        self._input_files = deque([])
        # if self.def_folder:
        #     for path in self.def_folder:
        #         self._input_files.append(path)
        # elif self.def_pic:
        #     self._input_files.append(self.def_pic)
        # else:
        #     raise MrbCameraError(
        #         "No picture paths have been defined for the dummy camera."
        #     )

        # self.def_pic = settings().get(
        #     ["mrbeam", "mock", "img_static"], defaults=settings().get(["webcam"])
        # )
        # self.def_folder = settings().get(["mrbeam", "mock", "img_folder"])
        path = dirname(realpath(__file__))
        self.def_pic = join(path, "tests", "rsc")
        self.def_folder = join(path, "tests", "rsc", "tmp_raw_img_000.jpg")

    def capture(self, output=None, format="jpeg", *args, **kwargs):
        """Mocks the behaviour of picamera.PiCamera.capture, with the caviat that"""
        import numpy as np
        import cv2

        logging.info("dummy camera capture")

        if self._busy.locked():
            raise MrbCameraError("Camera already busy taking a picture")
        self._busy.acquire()
        if self._shutter_speed and self._shutter_speed > 0:
            time.sleep(1 / self._shutter_speed)
        else:
            time.sleep(0.3)
        if not output:
            output = self.worker
        _input = self._input_files[0]
        if isinstance(output, basestring):
            os.copy2(_input, output)
        elif "write" in dir(output):
            with open(_input, "rb") as f:
                output.write(f.read())
            if "flush" in dir(output):
                output.flush()
        else:
            raise MrbCameraError(
                "Nothing to write into - either output or the worker are no a path or writeable objects"
            )
        self._busy.release()
        self._input_files.rotate()


BaseDummyCamera = DummyCamera
