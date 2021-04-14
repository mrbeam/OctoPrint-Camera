import copy
import json
import numpy as np
import time
import cv2
import base64
import threading
from threading import Event, Timer, Lock
import os
from os import path
import shutil
import logging
import re
import yaml


from flask.ext.babel import gettext

# from typing import Dict, Any, Union, Callable

from octoprint_mrbeam.mrbeam_events import MrBeamEvents


from octoprint_camera.camera.definitions import (
    TMP_RAW_FNAME_RE,
    STATE_SUCCESS,
    CAMERA_HEIGHT,
    DIST_KEY,
    ERR_NEED_CALIB,
    LEGACY_STILL_RES,
    LENS_CALIBRATION,
    MAX_OBJ_HEIGHT,
    MTX_KEY,
    MIN_BOARDS_DETECTED,
    QD_KEYS,
    TMP_RAW_FNAME_RE_NPZ,
)
from octoprint_camera.camera.worker import MrbPicWorker
from octoprint_camera.camera import exc as exc

from octoprint_camera.camera.mrbcamera import mrbCamera
from octoprint_camera.camera.undistort import (
    _getCamParams,
    prepareImage,
)
from octoprint_camera.camera import corners, config, lens
from octoprint_camera.camera.lens import (
    BoardDetectorDaemon,
    FACTORY,
    USER,
)
from octoprint_mrbeam.util import dict_merge, dict_map, get_thread, makedirs
from octoprint_mrbeam.util.log import json_serialisor, logme

from octoprint_camera import PhotoCreator

SIMILAR_PICS_BEFORE_UPSCALE = 1
LOW_QUALITY = 65  # low JPEG quality for compressing bigger pictures
OK_QUALITY = 75  # default JPEG quality served to the user
TOP_QUALITY = 90  # best compression quality we want to serve the user
DEFAULT_MM_TO_PX = 1  # How many pixels / mm is used for the output image

SIMILAR_PICS_BEFORE_REFRESH = 20
MAX_PIC_THREAD_RETRIES = 2


from octoprint_mrbeam.iobeam.iobeam_handler import IoBeamEvents
from octoprint.events import Events as OctoPrintEvents
from octoprint_mrbeam.mrb_logger import mrb_logger
import octoprint_mrbeam
from octoprint_camera.camera.corners import get_corner_calibration

_instance = None


def cameraHandler(plugin):
    global _instance
    if _instance is None:
        _instance = CameraHandler(plugin)
    return _instance


class CameraHandler(object):
    def __init__(self, plugin):
        self._plugin = plugin
        self._event_bus = plugin._event_bus
        self._settings = plugin._settings
        self._printer = plugin._printer
        self._plugin_manager = plugin._plugin_manager
        self._laserCutterProfile = (
            plugin.laserCutterProfileManager.get_current_or_default()
        )
        self._logger = mrb_logger(
            "octoprint.plugins.camera.camera_handler", lvl=logging.INFO
        )
        self._lid_closed = True
        self._interlock_closed = True
        self._is_slicing = False
        self._client_opened = False
        self.lensCalibrationStarted = False
        self.force_taking_picture = Event()
        self.force_taking_picture.clear()
        self.board_calibration_number_pics_taken_in_session = 0
        self.saveRawImgThread = None

        self.imagePath = (
            self._settings.getBaseFolder("uploads")
            + "/"
            + self._settings.get(["cam", "localFilePath"])
        )
        makedirs(self.imagePath, parent=True)
        makedirs(self.debugFolder)
        self._photo_creator = PhotoCreator(
            self._plugin, self._plugin_manager, self.imagePath, debug=False
        )
        self.refresh_pic_settings = (
            Event()
        )  # TODO placeholder for when we delete PhotoCreator

        # self._analytics_handler = self._plugin.analytics_handler #todo josef maybe needed for usercalibration
        self._analytics_handler = None
        self._event_bus.subscribe(MrBeamEvents.MRB_PLUGIN_INITIALIZED, self._subscribe)

        # TODO carefull if photocreator is None
        rawLock = self._photo_creator.rawLock if self._photo_creator else None
        self.boardDetectorDaemon = BoardDetectorDaemon(
            self.get_calibration_file("user"),
            stateChangeCallback=self.updateFrontendCC,
            event_bus=self._event_bus,
            rawImgLock=rawLock,
            factory=self._plugin.calibration_tool_mode,
        )

    def _subscribe(self, event, payload):
        self._event_bus.subscribe(IoBeamEvents.LID_OPENED, self.onEvent)
        self._event_bus.subscribe(IoBeamEvents.INTERLOCK_OPEN, self.onEvent)
        self._event_bus.subscribe(IoBeamEvents.INTERLOCK_CLOSED, self.onEvent)
        self._event_bus.subscribe(IoBeamEvents.LID_CLOSED, self.onEvent)
        self._event_bus.subscribe(IoBeamEvents.ONEBUTTON_RELEASED, self.onEvent)
        self._event_bus.subscribe(OctoPrintEvents.CLIENT_OPENED, self.onEvent)
        self._event_bus.subscribe(OctoPrintEvents.SHUTDOWN, self.onEvent)
        self._event_bus.subscribe(OctoPrintEvents.CLIENT_CLOSED, self.onEvent)
        self._event_bus.subscribe(OctoPrintEvents.SLICING_STARTED, self._onSlicingEvent)
        self._event_bus.subscribe(OctoPrintEvents.SLICING_DONE, self._onSlicingEvent)
        self._event_bus.subscribe(OctoPrintEvents.SLICING_FAILED, self._onSlicingEvent)
        self._event_bus.subscribe(
            OctoPrintEvents.SLICING_CANCELLED, self._onSlicingEvent
        )
        self._event_bus.subscribe(
            OctoPrintEvents.PRINTER_STATE_CHANGED, self._printerStateChanged
        )
        self._event_bus.subscribe(
            OctoPrintEvents.LENS_CALIB_START, self._startStopCamera
        )
        self._event_bus.subscribe(MrBeamEvents.LENS_CALIB_DONE, self.onEvent)

    def onEvent(self, event, payload):
        self._logger.debug("onEvent() event: %s, payload: %s", event, payload)
        if event == OctoPrintEvents.CLIENT_OPENED:
            self._logger.debug(
                "onEvent() CLIENT_OPENED sending client lidClosed: %s", self._lid_closed
            )
            self._client_opened = True
            self.tell_client_calibration_status()
            self._startStopCamera(event)
        # Please re-enable when the OctoPrint is more reliable at
        # detecting when a user actually disconnected.
        # elif event == OctoPrintEvents.CLIENT_CLOSED:
        # 	self._client_opened = False
        # 	self._startStopCamera(event)
        elif event == OctoPrintEvents.SHUTDOWN:
            self.shutdown()
        elif (
            event == IoBeamEvents.ONEBUTTON_RELEASED
            and self.lensCalibrationStarted
            and payload < 5.0
        ):
            self._logger.info("onEvent() ONEBUTTON_RELEASED - payload : %s" % payload)
            if self.saveRawImgThread is not None and self.saveRawImgThread.is_alive():
                self._logger.info("save Img Thread still alive, ignoring request")
            else:
                self.saveRawImgThread = get_thread(daemon=True)(self.saveRawImg)()

        elif event in [
            MrBeamEvents.LENS_CALIB_EXIT,
            MrBeamEvents.LENS_CALIB_DONE,
            MrBeamEvents.LENS_CALIB_START,
        ]:
            self._plugin_manager.send_plugin_message("mrbeam", {"event": event})
            if event == MrBeamEvents.LENS_CALIB_DONE:
                self._plugin.user_notification_system.show_notifications(
                    self._plugin.user_notification_system.get_notification(
                        "lens_calibration_done"
                    )
                )

    def is_lid_open(self):
        return False  # self._lid_closed #todo josef get from mrbeam plugin

    def on_front_end_pic_received(self):
        self._logger.debug("Front End finished downloading the picture")
        if self._photo_creator is not None:
            self._photo_creator.send_pic_asap()

    def send_camera_image_to_analytics(self):
        if self._photo_creator:
            if self._plugin.is_dev_env():
                user = "dev"
            else:
                user = "user"
            self._photo_creator.send_last_img_to_analytics(
                force_upload=True, trigger=user, notify_user=True
            )

    def _printerStateChanged(self, event, payload):
        if payload["state_string"] == "Operational":
            # TODO CHECK IF CLIENT IS CONNECTED FOR REAL, with PING METHOD OR SIMILAR
            self._client_opened = True
            self._startStopCamera(event)

    def _onSlicingEvent(self, event, payload):
        self._is_slicing = event == OctoPrintEvents.SLICING_STARTED
        self._startStopCamera(event)

    def _startStopCamera(self, event, payload=None):
        if self._photo_creator is not None:
            status = " - event: {}\nclient_opened {}, is_slicing: {}\nlid_closed: {}, printer.is_locked(): {}, save_debug_images: {}".format(
                event,
                self._client_opened,
                self._is_slicing,
                self._lid_closed,
                None,  # todo why not working#self._printer.is_locked() if self._printer else None,
                self._photo_creator.save_debug_images,
            )
            if event in (
                IoBeamEvents.LID_CLOSED,
                OctoPrintEvents.SLICING_STARTED,
                OctoPrintEvents.CLIENT_CLOSED,
            ):
                self._plugin._logger.info("Camera stopping" + status)
                self._end_photo_worker()
            elif event in ["initial_calibration", MrBeamEvents.LENS_CALIB_START]:
                # See self._photo_creator.is_initial_calibration if it used from /plugin/mrbeam/calibration
                self._logger.info(
                    "Camera starting: initial_calibration. event: {}".format(event)
                )
                self._start_photo_worker()
            else:
                # TODO get the states from _printer or the global state, instead of having local state as well!
                if self._plugin.calibration_tool_mode or (
                    self._client_opened
                    and not self._is_slicing
                    and not self._interlock_closed
                    and not self._printer.is_locked()
                ):
                    self._logger.info("Camera starting" + status)
                    self._start_photo_worker()
                else:
                    self._logger.debug("Camera not supposed to start now." + status)

    def shutdown(self):
        self._logger.info("Shutting down")
        self.boardDetectorDaemon.stopAsap()
        if self.boardDetectorDaemon.started:
            self._logger.info("shutdown() stopping board detector daemon")
            self.boardDetectorDaemon.join()
        if self._photo_creator is not None:
            self._logger.debug("shutdown() stopping _photo_creator")
            self._end_photo_worker()

    def _start_photo_worker(self):
        if self._photo_creator.active:
            self._logger.debug(
                "Another PhotoCreator thread is already active! Not starting a new one."
            )
            return
        path_to_cam_params = self.get_calibration_file()
        path_to_pic_settings = self._settings.get(["cam", "correctionSettingsFile"])

        mrb_volume = self._laserCutterProfile["volume"]
        out_pic_size = mrb_volume["width"], mrb_volume["depth"]
        self._logger.debug("Will send images with size %s", out_pic_size)

        # load cam_params from file
        cam_params = _getCamParams(path_to_cam_params)
        self._plugin._logger.debug("Loaded cam_params: {}".format(cam_params))

        if self._photo_creator.stopping:
            self._photo_creator.restart(
                pic_settings=path_to_pic_settings,
                cam_params=cam_params,
                out_pic_size=out_pic_size,
            )
        else:
            self._photo_creator.start(
                pic_settings=path_to_pic_settings,
                cam_params=cam_params,
                out_pic_size=out_pic_size,
            )

    def _end_photo_worker(self):
        if self._photo_creator is not None:
            self._photo_creator.stop()
            self._photo_creator.save_debug_images = False
            self._photo_creator.undistorted_pic_path = None

    def restart_worker(self):
        raise NotImplementedError()
        # if self._photo_creator:
        # 	self._photo_creator.restart()

    def refresh_settings(self):
        # Let's the worker know to refresh the picture settings while running
        self._photo_creator.refresh_pic_settings.set()
        self.tell_client_calibration_status()

    def need_corner_calibration(self, pic_settings=None):
        args = (
            self._settings.get(["cam", "lensCalibration", "legacy"]),
            self._settings.get(["cam", "lensCalibration", "user"]),
        )
        if pic_settings is None:
            return config.calibration_needed_from_file(
                self._settings.get(["cam", "correctionSettingsFile"]), *args
            )
        else:
            return config.calibration_needed_from_flat(pic_settings, *args)

    def tell_client_calibration_status(self):
        try:
            with open(self._settings.get(["cam", "correctionSettingsFile"])) as f:
                pic_settings = yaml.load(f)
        except IOError:
            need_corner_calibration = True
            need_raw_camera_calibration = True
            pic_settings = None
        else:
            need_corner_calibration = self.need_corner_calibration(pic_settings)
            need_raw_camera_calibration = config.calibration_needed_from_flat(
                pic_settings
            )
        # self._logger.warning("pic settings %s", pic_settings)

        self._plugin_manager.send_plugin_message(
            "mrbeam",
            dict(
                need_camera_calibration=need_corner_calibration,
                need_raw_camera_calibration=need_raw_camera_calibration,
            ),
        )
        if need_corner_calibration:
            self._logger.warning(ERR_NEED_CALIB)

    def get_calibration_file(self, calibration_type=None):
        """Gives the location of the best existing lens calibration file, or
        the demanded type (calibration_type).
        If in calibration tool mode, it always returns the path to the factory
        file.
        """
        if self._plugin.calibration_tool_mode:
            return self._settings.get(["cam", "lensCalibration", "factory"])

        def check(t):
            path = self._settings.get(["cam", "lensCalibration", t])
            if os.path.isfile(path):
                return path
            else:
                return None

        if calibration_type is None:
            ret = check("user") or check("factory") or check("legacy")
            if ret is not None:
                return ret
            else:
                # Lens calibration by the user is necessary
                return self._settings.get(["cam", "lensCalibration", "user"])
        else:
            return self._settings.get(["cam", "lensCalibration", calibration_type])

    def compensate_for_obj_height(self, compensate=False):
        if self._photo_creator is not None:
            self._photo_creator.zoomed_out = compensate

    def onLensCalibrationStart(self):
        """
        When pressing the button 'start lens calibration'
        Doesn't run the cv2 lens calibration at that point.
        """
        self._photo_creator.is_initial_calibration = True
        self._start_photo_worker()
        if not self.lensCalibrationStarted and self.boardDetectorDaemon.load_dir(
            self.debugFolder
        ):
            self._logger.info("Found pictures from previous session")
        if not self._plugin.calibration_tool_mode:
            # clean up from the latest calibraton session
            self.boardDetectorDaemon.state.rm_unused_images()
            self.boardDetectorDaemon.state.rm_from_origin(origin=FACTORY)
        self.getRawImg()
        self.lensCalibrationStarted = True
        self._event_bus.fire(MrBeamEvents.LENS_CALIB_START)
        self._logger.info("Lens calibration Started : %s" % self.lensCalibrationStarted)

    def getRawImg(self):
        # Sends the current state to the front end
        self.boardDetectorDaemon.state.onChange()

    def saveRawImg(self):
        # TODO debug/raw.jpg -> copy image over
        # TODO careful when deleting pic + setting new name -> hash
        self._plugin._logger.debug("Test")
        self._logger.debug(
            "debug folder %s %s", os.path.isdir(self.debugFolder), self.debugFolder
        )
        self._plugin._logger.debug(
            "debug folder %s %s", os.path.isdir(self.debugFolder), self.debugFolder
        )
        if os.path.isdir(self.debugFolder):
            lens.clean_unexpected_files(self.debugFolder)
            self._plugin._logger.debug(
                "save raw image %s - %s - %s",
                self._photo_creator,
                self._photo_creator.active,
                self._photo_creator.stopping,
            )
        if (
            self._photo_creator
            and self._photo_creator.active
            and not self._photo_creator.stopping
        ):
            # take a new picture and save to the specific path
            self._plugin._logger.debug(
                "board detector %s from %s",
                self.boardDetectorDaemon,
                MIN_BOARDS_DETECTED,
            )
            if len(self.boardDetectorDaemon) == MIN_BOARDS_DETECTED - 1:
                self._logger.info("Last picture to be taken")
                self._event_bus.fire(MrBeamEvents.RAW_IMG_TAKING_LAST)
            elif (
                len(self.boardDetectorDaemon) >= MIN_BOARDS_DETECTED
                and self._plugin.calibration_tool_mode
            ):
                self._event_bus.fire(MrBeamEvents.RAW_IMG_TAKING_FAIL)
                self._logger.info("Ignoring this picture")
                return
            else:
                self._event_bus.fire(MrBeamEvents.RAW_IMAGE_TAKING_START)
            imgName = self.boardDetectorDaemon.next_tmp_img_name()
            self._photo_creator.saveRaw = imgName
            self._plugin._logger.info("Saving new picture %s" % imgName)
            self.takeNewPic()
            imgPath = path.join(self.debugFolder, imgName)
            # Tell the boardDetector to listen for this file
            self.boardDetectorDaemon.add(imgPath)
            _s = self.boardDetectorDaemon.state
            if not self.boardDetectorDaemon.is_alive():
                self.boardDetectorDaemon.start()
            else:
                self.boardDetectorDaemon.waiting.clear()
            if len(self.boardDetectorDaemon) >= MIN_BOARDS_DETECTED:
                if self._plugin.calibration_tool_mode:
                    # Watterott - Auto save calibration
                    self.saveLensCalibration()
                    t = Timer(
                        1.2,
                        self._event_bus.fire,
                        args=(MrBeamEvents.LENS_CALIB_PROCESSING_BOARDS,),
                    )
                    t.start()
                else:
                    self._event_bus.fire(MrBeamEvents.LENS_CALIB_PROCESSING_BOARDS)
                self.boardDetectorDaemon.scaleProcessors(2)

    @logme(True)
    def delRawImg(self, path):
        try:
            os.remove(path)
        except OSError as e:
            self._logger.warning("Error trying to delete file: %s\n%s" % (path, e))
        finally:
            self.boardDetectorDaemon.remove(path)
        return (
            self.boardDetectorDaemon.state.keys()
        )  # TODO necessary? Frontend update now happens via plugin message

    def removeAllTmpPictures(self):
        if os.path.isdir(self.debugFolder):
            for filename in os.listdir(self.debugFolder):
                if re.match(TMP_RAW_FNAME_RE, filename):
                    my_path = path.join(self.debugFolder, filename)
                    self._logger.debug("Removing tmp calibration file %s" % my_path)
                    os.remove(my_path)
            lens.clean_unexpected_files(self.debugFolder)

    def stopLensCalibration(self):
        self._analytics_handler.add_camera_session_details(
            {
                "message": "Stopping lens calibration",
                "id": "cam_lens_calib_stop",
                "lens_calib_state": self.boardDetectorDaemon.state.analytics_friendly(),
            }
        )
        self.boardDetectorDaemon.stopAsap()
        if self.boardDetectorDaemon.is_alive():
            self.boardDetectorDaemon.join()
        self.lensCalibrationStarted = False
        self.boardDetectorDaemon = BoardDetectorDaemon(
            self.get_calibration_file("user"),
            stateChangeCallback=self.updateFrontendCC,
            event_bus=self._event_bus,
            rawImgLock=self._photo_creator.rawLock,
        )
        if not self._plugin.calibration_tool_mode and not self._plugin.is_dev_env():
            self.removeAllTmpPictures()

    def ignoreCalibrationImage(self, path):
        myPath = path.join(self.debugFolder, "debug", path)
        if myPath in self.boardDetectorDaemon.state.keys():
            self.boardDetectorDaemon.state.ignore(path)

    def takeNewPic(self):
        """Forces agent to take a new picture."""
        if self.force_taking_picture.isSet():
            self._logger.info("Already analysing a picture, please wait")
            return False
        else:
            if (
                self._photo_creator
                and self._photo_creator.active
                and not self._photo_creator.stopping
            ):
                self._photo_creator.forceNewPic.set()
                self._logger.info("Force take new picture.")
                return True
            else:
                return False

    def saveLensCalibration(self):
        if (
            not self.boardDetectorDaemon.is_alive()
            and not self.boardDetectorDaemon.stopping
        ):
            self._logger.info("Board detector not alive, starting now")
            self.boardDetectorDaemon.start()

        self._analytics_handler.add_camera_session_details(
            {
                "message": "Saving lens calibration",
                "id": "cam_lens_calib_save",
                "lens_calib_state": self.boardDetectorDaemon.state.analytics_friendly(),
            }
        )
        self.boardDetectorDaemon.saveCalibration()
        # Remove the lens distorted corner calibration keys
        pic_settings_path = self._settings.get(["cam", "correctionSettingsFile"])
        pic_settings = corners.get_corner_calibration(pic_settings_path)
        config.rm_undistorted_keys(
            pic_settings, factory=self._plugin.calibration_tool_mode
        )
        corners.write_corner_calibration(
            pic_settings,
            pic_settings_path,
        )
        if self.need_corner_calibration(pic_settings):
            self._logger.warning(ERR_NEED_CALIB)
            self._plugin_manager.send_plugin_message(
                "mrbeam", dict(need_camera_calibration=True)
            )
        if not self._plugin.calibration_tool_mode:
            # Tool mode (watterott) : Continues taking pictures
            self.boardDetectorDaemon.stopAsap()
        return True

    def revert_factory_lens_calibration(self):
        """
        The camera reverts to the factory or legacy calibration file.
        - Removes the user lens calibration file,
        - Removes the calibration pictures
        - Refreshes settings.
        """
        files = []
        lens_calib = self._settings.get(["cam", "lensCalibration", USER])
        if os.path.isfile(lens_calib):
            os.remove(lens_calib)
        for fname in os.listdir(self.debugFolder):
            if re.match(TMP_RAW_FNAME_RE, fname) or re.match(
                TMP_RAW_FNAME_RE_NPZ, fname
            ):
                files.append(os.path.join(self.debugFolder, fname))
        for fname in files:
            try:
                os.remove(fname)
            except OSError as e:
                self._logger.warning("Err during factory restoration : %s", e)
                # raising error because I made sure all the files existed before-hand
                self.refresh_settings()
                raise
        self._analytics_handler.add_camera_session_details(
            {
                "message": "Reverting lens calibration",
                "id": "cam_lens_calib_revert",
            }
        )
        self.refresh_settings()

    def updateFrontendCC(self, data):
        if data["lensCalibration"] == STATE_SUCCESS:
            self.refresh_settings()
        self._plugin_manager.send_plugin_message(
            "mrbeam", dict(chessboardCalibrationState=data)
        )

    def send_mrb_state(self):
        self._plugin_manager.send_plugin_message(
            "mrbeam", dict(mrb_state=self._plugin.get_mrb_state())
        )

    @property
    def debugFolder(self):
        return path.join(path.dirname(self.imagePath), "debug")
