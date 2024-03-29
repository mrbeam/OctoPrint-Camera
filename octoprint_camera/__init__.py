# coding=utf-8
from __future__ import absolute_import, print_function, unicode_literals, division

import base64
import cv2
import flask
from flask import jsonify, request, make_response
import io
import json
import platform
import numpy as np
import os
from os import path
from random import randint
import socket
import sys
import time

from werkzeug.exceptions import BadRequest

PY3 = sys.version_info >= (3,)

import octoprint.plugin
from octoprint.server.util.flask import add_non_caching_response_headers
from octoprint.server import NO_CONTENT
from octoprint.settings import settings
from octoprint.util import dict_merge
from octoprint_mrbeam.camera.definitions import (
    LEGACY_STILL_RES,
    LENS_CALIBRATION,
    MIN_BOARDS_DETECTED,
)
import octoprint_mrbeam.camera
from octoprint_mrbeam.camera.undistort import (
    _getCamParams,
    _debug_drawCorners,
    _debug_drawMarkers,
)
from octoprint_mrbeam.camera.label_printer import labelPrinter
from octoprint_mrbeam.mrbeam_events import MrBeamEvents

# from octoprint_mrbeam.support import check_support_mode
from octoprint_mrbeam.util import dict_map, get_thread
from octoprint_mrbeam.util.log import json_serialisor

import pkg_resources

__version__ = pkg_resources.require("octoprint_camera")

from . import corners, lens, util, iobeam
from .camera import CameraThread

# from .image import LAST, NEXT, WHICH, PIC_PLAIN, PIC_CORNER, PIC_LENS, PIC_BOTH, PIC_TYPES
from .iobeam import IoBeamEvents
from .leds import LedEventListener
from .util import logExceptions
from .util.image import (
    corner_settings_valid,
    lens_settings_valid,
    SettingsError,
    MarkerError,
)
from .util.flask import send_image, send_file_b64

IMG_WIDTH, IMG_HEIGHT = LEGACY_STILL_RES
PIC_PLAIN = "plain"  # The equivalent of "raw" pictures
PIC_CORNER = "corner"  # Corrected for the position of the work area corners
PIC_LENS = "lens"  # Corrected for the lens distortion
PIC_BOTH = "both"  # Corrected corners + lens
PIC_TYPES = (PIC_PLAIN, PIC_CORNER, PIC_LENS, PIC_BOTH)
LAST = "last"
NEXT = "next"
WHICH = (LAST, NEXT)
IS_X86 = platform.machine() == "x86_64"


class CameraPlugin(
    octoprint.plugin.StartupPlugin,
    octoprint.plugin.ShutdownPlugin,
    octoprint.plugin.TemplatePlugin,
    octoprint.plugin.SettingsPlugin,
    octoprint.plugin.AssetPlugin,
    octoprint.plugin.BlueprintPlugin,
):
    def __init__(self):
        self.camera_thread = None
        self.lens_calibration_thread = None
        self.iobeam_thread = None
        self.lens_settings = {}
        # Shadow settings for the pink circles position history
        self.__corners_hist_datafile = None
        self.__corners_hist_settings = {}
        # Shadow settings for the lens settings
        self.__lens_datafile = None
        self.__lens_settings = {}
        # Led event listener and client
        self.led_client = None

        from octoprint.server import debug

        self.debug = debug

    def initialize(self):
        self.led_client = LedEventListener(self)

    ##~~ StartupPlugin mixin

    def on_after_startup(self, *a, **kw):
        self.camera_thread = CameraThread(
            self._settings, debug=self._settings.get(["debug"])
        )
        # TODO stage 2 - Only start the camera when required
        self.camera_thread.start()
        # TODO Stage 2 - Only start the lens calibration daemon when required
        self.start_lens_calibration_daemon()
        # TODO Stage 3 - Separate into an iobeam plugin
        self.iobeam_thread = iobeam.IoBeamHandler(self)
        self.iobeam_thread._initWorker()
        # TODO Stage 3 - Remove, should only trigger via plugin hook.
        self._event_bus.subscribe(
            IoBeamEvents.ONEBUTTON_PRESSED,
            get_thread()(self.capture_img_for_lens_calibration),
        )
        if util.factory_mode():
            # Invite to take a picture for the lens calibration
            self._event_bus.fire(MrBeamEvents.LENS_CALIB_IDLE)
            self.led_client.set_inside_brightness(60)

    ##~~ ShutdownPlugin mixin

    def on_shutdown(self, *a, **kw):
        if self.camera_thread:
            self.camera_thread.stop()
        self._logger.debug("Camera thread joined")

    ##~~ SettingsPlugin mixin

    def get_settings_defaults(self):
        # TODO Stage 2 - Takes over the Camera settings from the MrBPlugin.
        base_folder = settings().getBaseFolder("base")
        return dict(
            cam_img_width=IMG_WIDTH,
            cam_img_height=IMG_HEIGHT,
            debug=False,
            frontendUrl="/downloads/files/local/cam/beam-cam.jpg",
            previewOpacity=1,
            localFilePath="cam/beam-cam.jpg",
            localUndistImage="cam/undistorted.jpg",
            keepOriginals=False,
            corrections=dict(
                settingsFile="{}/cam/pic_settings.yaml".format(base_folder),
                tmpFile="{}/cam/last_markers.json".format(base_folder),
                # lensCalibration={
                #     k: os.path.join(cam_folder, camera.LENS_CALIBRATION[k])
                #     for k in ["legacy", "user", "factory"]
                # },
                # saveCorrectionDebugImages=False,
                # markerRecognitionMinPixel=MIN_MARKER_PIX,
                remember_markers_across_sessions=True,
            ),
            # The list of options that usually get saved to pic_settings.yaml
            # TODO : migration : Get values from _getCamParams
            # lens=dict(
            #     factory=dict(),
            #     user=dict(),
            # ),
            lens_datafile=path.join(self.get_plugin_data_folder(), "lens.npz"),
            lens_legacy_datafile=path.join(
                "/home/pi/.octoprint/cam/", LENS_CALIBRATION["factory"]
            ),
            corners_legacy_datafile=path.join(
                "/home/pi/.octoprint/cam/", "pic_settings.yaml"
            ),
            corners=dict(
                factory=dict(
                    arrows_px={},
                    pink_circles_px={},
                ),
                user=dict(
                    arrows_px={},
                    pink_circles_px={},
                ),
                history=dict(
                    # The last recorded position of the pink_circles.
                    # Should only be saved on shutdown & camera stop
                    pink_circles_px={},
                ),
                history_datafile=path.join(
                    self.get_plugin_data_folder(), "pink_marker_history.yaml"
                ),
            ),
        )

    # def on_settings_initialized(self):
    # shadow the lens settings and save them as a .npz file
    # self.__lens_datafile = self._settings.get(['lens_datafile'], "")
    # try:
    #     self.__lens_settings = np.load(self.__lens_datafile)
    # except IOError:
    #     self.__lens_settings = {}
    # # shadow the pink circle history settings - they are in a separate .yaml file
    # self.__corners_hist_datafile = self._settings.get(['corners', 'history_datafile'], "")
    # try:
    #     self.__corners_hist_settings = np.load(self.__corners_hist_datafile)
    # except IOError:
    #     self.__corners_hist_settings = {}
    # update self._settings to have the shadow values available
    # self._settings.set([], self._merge_shadow_settings({}))

    # def on_settings_load(self):
    #     # include the shadow settings into the complete settings
    #     return self._merge_shadow_settings(
    #         dict(octoprint.plugin.SettingsPlugin.on_settings_load(self))
    #     )

    # def on_settings_save(self, data):
    #     return octoprint.plugin.SettingsPlugin.on_settings_save(
    #         self,
    #         self._remove_shadow_settings(data)
    #     )

    # def _merge_shadow_settings(self, data):
    #     return dict_merge(
    #         dict(
    #             corners=dict(history=self.__corners_hist_settings),
    #             # lens=self.__lens_settings
    #         ),
    #         data,
    #     )

    # def _remove_shadow_settings(self, data):
    #     """Save the shadow settings and remove them from `data` *in place*"""
    #     # mega ugly, needs to be made properly with something
    #     # like `dict_map_paths(paths, func=lambda x: del x, data)`
    #     self.__lens_settings = dict_merge(self.__lens_settings, data.get('lens', {}))
    #     # if 'lens' in data:
    #     #     del data['lens']
    #     if 'corners' in data and isinstance(data['corners'], dict):
    #         self.__corners_hist_settings = dict_merge(self.__corners_hist_settings,
    #                                                 data['corners'].get('history'), {})
    #         if 'history' in data['corners']:
    #             del data['corners']['history']

    ##~~ TemplatePlugin mixin

    # def get_template_configs(self):
    #     # TODO Stage 2 - Takes over the Camera settings from the MrBPlugin.
    # return [dict(type="settings", custom_bindings=False)]

    def get_assets(self):
        # TODO Stage 1 - Camera Calibration UI
        return dict(
            js=[
                "js/calibrationmodeMessage.js",
                "js/camera.js",
                "js/settings/camera_settings.js",
                "js/calibration/calibration.js",
                "js/calibration/corner_calibration.js",
                "js/calibration/lens_calibration.js",
                "js/calibration/watterott/camera_alignment.js",
                "js/calibration/watterott/calibration_qa.js",
                "js/calibration/watterott/label_printer.js",
            ],
            css=[
                "css/calibration_qa.css",
                "css/mrbeam.css",
                "css/calibration_corner.css",
                "css/calibration_lens.css",
            ],
            less=[],
        )

    ##~~ BlueprintPlugin mixin

    @octoprint.plugin.BlueprintPlugin.route("/shutdown", methods=["GET"])
    @logExceptions
    def force_shutdown(self):
        """
        This is only required because the lens calibration processes can
        lock up the other threads, preventing a normal shutdown
        """
        import os
        from octoprint.events import Events

        # Fire shutdown event ourselves because OctoPrint will not be able to.
        # It will change the LED lights
        self._event_bus.fire(Events.SHUTDOWN)
        # First ask to shutdown as a background process
        os.system("sudo shutdown now &")
        # Cyanide pill because of how the lens calibration prcesses hang
        os.system("killall -9 /home/pi/oprint/bin/python2")

    # disable default api key check for all blueprint routes.
    # use @restricted_access, @firstrun_only_access to check permissions
    def is_blueprint_protected(self):
        return False  # No API key required to request API access

    @octoprint.plugin.BlueprintPlugin.route("/calibration", methods=["GET"])
    # @calibration_tool_mode_only
    @logExceptions
    def calibration_wrapper(self):
        from flask import render_template
        from octoprint.server import debug, VERSION, DISPLAY_VERSION, UI_API_KEY, BRANCH
        from octoprint_mrbeam.util.device_info import DeviceInfo

        device_info = DeviceInfo()
        beamos_version, beamos_date = device_info.get_beamos_version()
        render_kwargs = dict(
            debug=debug,
            version=dict(number=VERSION, display=DISPLAY_VERSION, branch=BRANCH),
            uiApiKey=UI_API_KEY,
            templates=dict(tab=[]),
            pluginNames=dict(),
            locales=dict(),
            supportedExtensions=[],
            # beamOS version - Not the plugin version
            beamosVersionNumber=beamos_version,
            beamosBuildDate=beamos_date,
            hostname=socket.gethostname(),
            serial=device_info.get_serial(),
            # beta_label=self.get_beta_label(),
            e="null",
            gcodeThreshold=0,  # legacy - OctoPrint render bug
            gcodeMobileThreshold=0,  # legacy - OctoPrint render bug
            get_img=json.dumps(
                dict(
                    last=LAST,
                    next=NEXT,
                    pic_plain=PIC_PLAIN,
                    pic_corner=PIC_CORNER,
                    pic_lens=PIC_LENS,
                    pic_both=PIC_BOTH,
                    pic_types=PIC_TYPES,
                )
            ),
        )

        r = make_response(
            render_template(
                "calibration/watterott/calibration_tool.jinja2", **render_kwargs
            )
        )

        r = add_non_caching_response_headers(r)
        return r

    # Returns the latest available image to diplay on the interface
    @octoprint.plugin.BlueprintPlugin.route("/image", methods=["GET"])
    @logExceptions
    def getImage(self):
        # FIXME : Divergence between raw jpg image and b64 encoded image.
        values = request.values
        which = values.get("which", "something else")
        if not which in WHICH:
            return flask.make_response(
                "which should be a selection of {}, not {}".format(WHICH, which), 405
            )
        pic_type = values.get("pic_type")
        if not pic_type in PIC_TYPES:
            return flask.make_response(
                "type should be a selection of {}, not {}".format(PIC_TYPES, pic_type),
                407,
            )
        if self._settings.get(["debug"]):
            # Return a static image
            if which == "next":
                # returns the next avaiable image
                filepath = "static/img/calibration/undistorted_bad1.jpg"
            else:
                # get random file for test
                f = []
                for root, dirs, files in os.walk(
                    os.path.join(os.path.dirname(__file__), "static/img/calibration")
                ):
                    for filename in files:
                        if filename.split(".")[-1] == "jpg":
                            f.append(filename)
                filepath = os.path.join(
                    os.path.dirname(__file__),
                    "static/img/calibration",
                    f[randint(0, len(f) - 1)],
                )
                # filepath = "static/img/calibration/qa_final_rectangle.jpg"
            return send_image(
                os.path.join(
                    os.path.dirname(__file__),
                    filepath,
                ),
                pic_type=pic_type,
                which=which,
                positions_found={
                    "NE": {
                        "avg_hsv": [
                            156.04775828460038,
                            127.38206627680312,
                            75.5906432748538,
                        ],
                        "pix_size": 1026,
                        "pos": [1965, 266],
                    },
                    "NW": {
                        "avg_hsv": [
                            156.04775828460038,
                            127.38206627680312,
                            75.5906432748538,
                        ],
                        "pix_size": 1026,
                        "pos": [1965, 266],
                    },
                    "SE": {
                        "avg_hsv": [
                            156.04775828460038,
                            127.38206627680312,
                            75.5906432748538,
                        ],
                        "pix_size": 1026,
                        "pos": [1965, 266],
                    },
                    "SW": {
                        "avg_hsv": [
                            156.04775828460038,
                            127.38206627680312,
                            75.5906432748538,
                        ],
                        "pix_size": 1026,
                        "pos": [1965, 266],
                    },
                },
            )
        else:
            # TODO return correct image
            corners = dict_merge(
                self._settings.get(["corners", "factory"]) or {},
                self._settings.get(["corners", "history"]) or {},
            )
            lens_settings_path = self._settings.get(["lens_legacy_datafile"]) or ""
            if os.path.isfile(lens_settings_path):
                settings_lens = np.load(lens_settings_path)
            else:
                settings_lens = {}
            try:
                image, timestamp, positions_workspace_corners = self.get_picture(
                    pic_type,
                    which,
                    settings_corners=corners,
                    settings_lens=settings_lens,
                )
            except SettingsError as e:
                return flask.make_response(
                    "Wrong camera settings for the requested picture %s" % e, 506
                )
            except MarkerError as e:
                self._logger.debug("MARKERERROR: %s", e)
                return flask.make_response(
                    flask.jsonify(
                        dict_map(
                            json_serialisor,
                            {
                                "message": "Didn't found all Markers %s" % e,
                                "positions_found": e.positions_found,
                            }
                            # e
                        )
                    ),
                    506,
                )
            else:
                if image:
                    return send_image(
                        image,
                        timestamp=timestamp,
                        pic_type=pic_type,
                        which=which,
                        positions_found=positions_workspace_corners,
                    )
                else:
                    return flask.make_response("No image available (yet).", 404)

    # send plugin message via websocket to inform frontend about new image, with timestamp
    def _informFrontend(self):
        self._plugin_manager.send_plugin_message(
            "camera",
            dict_map(json_serialisor, dict(newImage=time.time())),
        )

    # Returns the timestamp of the latest available image
    @octoprint.plugin.BlueprintPlugin.route("/timestamp", methods=["GET"])
    @octoprint.plugin.BlueprintPlugin.route("/ts", methods=["GET"])
    @logExceptions
    def getTimestamp(self):
        data = dict_map(
            json_serialisor, {"timestamp": self.camera_thread.latest_img_timestamp}
        )
        return jsonify(data)

    # Whether the camera is running or not
    @octoprint.plugin.BlueprintPlugin.route("/running", methods=["GET"])
    @logExceptions
    def getRunningState(self):
        data = {"running": self.camera_thread.active()}
        return jsonify(data)

    # return whether the camera can run now
    @octoprint.plugin.BlueprintPlugin.route("/available", methods=["GET"])
    @logExceptions
    def getAvailableState(self):
        data = {"available": True}  # TODO return correct available state
        return jsonify(data)

    # return the available corretions to the image
    @octoprint.plugin.BlueprintPlugin.route("/available_corrections", methods=["GET"])
    @logExceptions
    def getAvailableCorrections(self):
        ret = ["plain"]
        try:
            lens_ok = lens_settings_valid(
                np.load(self._settings.get(["lens_legacy_datafile"]))
            )
        except Exception as e:
            self._logger.error("Error when retrieving lens settings %s" % e)
            lens_ok = False
        corners_ok = corner_settings_valid(
            corners.get_corner_calibration(
                self._settings.get(["corners_legacy_datafile"])
            )
        )
        if corners_ok:
            ret += ["corners"]
        if lens_ok:
            ret += ["lens"]
        if lens_ok and corners_ok:
            ret += ["both"]

        data = {"available_corrections": ret}
        return jsonify(data)

    @octoprint.plugin.BlueprintPlugin.route(
        "/lens_calibration_capture", methods=["GET"]
    )
    @logExceptions
    def flask_capture_img_for_lens_calibration(self):
        return jsonify(dict(ret=self.capture_img_for_lens_calibration()))

    @octoprint.plugin.BlueprintPlugin.route(
        "/save_corner_calibration", methods=["POST"]
    )
    # @restricted_access_or_calibration_tool_mode #TODO activate
    @logExceptions
    def saveInitialCalibrationMarkers(self):
        if not "application/json" in request.headers["Content-Type"]:
            return make_response("Expected content-type JSON", 400)
        try:
            json_data = request.get_json()
        except BadRequest:
            return make_response("Malformed JSON body in request", 400)
        if not all(k in json_data.keys() for k in ["newCorners", "newMarkers"]):
            # TODO correct error message
            return make_response("No profile included in request", 400)
        corners.save_corner_calibration(
            self._settings.get(["corners_legacy_datafile"]),
            hostname=socket.gethostname(),
            plugin_version=self._plugin_version,
            from_factory=util.factory_mode(),
            newCorners=json_data["newCorners"],
            newMarkers=json_data["newMarkers"],
        )
        key = "factory" if util.factory_mode() else "user"
        self._settings.set(["corners", key], json_data)
        return NO_CONTENT

    @logExceptions
    def send_lens_calibration_state(self, data):
        self._plugin_manager.send_plugin_message(
            "camera", dict_map(json_serialisor, dict(chessboardCalibrationState=data))
        )

    @octoprint.plugin.BlueprintPlugin.route(
        "/send_lens_captured_img_list", methods=["GET"]
    )
    @logExceptions
    def send_lens_captured_img_list(self):
        # This function will trigger the lens calibration on_change callback
        # This callback sends the whole list of images available
        self.lens_calibration_thread.state.onChange()
        return NO_CONTENT

    # Returns the image to diplay on the interface
    @octoprint.plugin.BlueprintPlugin.route(
        "/get_lens_calibration_image", methods=["POST"]
    )
    @logExceptions
    def get_lens_calibration_image(self):
        # values = request.values
        _json = request.get_json()
        # timestamp = values.get("timestamp", None)
        timestamp = _json.get("timestamp", None)
        if timestamp:
            images = self.lens_calibration_thread.get_images(timestamp)
            if images:
                return make_response(images, default=json_serialisor)
        # In every other case, there is no images with that timestamp
        return make_response(
            "The timestamp does not correspond to any known image", 406
        )

    @octoprint.plugin.BlueprintPlugin.route(
        "/lens_calibration_del_image", methods=["POST"]
    )
    # @restricted_access_or_calibration_tool_mode #TODO activate
    @logExceptions
    def deleteCalibrationImage(self):
        _json = request.get_json()
        file_path = _json.get("path", None)
        self.lens_calibration_thread.remove(file_path)
        return NO_CONTENT

    @octoprint.plugin.BlueprintPlugin.route("/print_label", methods=["POST"])
    # @calibration_tool_mode_only
    def printLabel(self):
        res = labelPrinter(self, use_dummy_values=IS_X86).print_label(request)
        self._logger.info("print label %s", res.response)
        return make_response(jsonify(res), 200 if res["success"] else 502)

    ##~~ Camera Plugin

    def get_picture(
        self,
        pic_type="plain",
        which="last",
        settings_corners=dict(),
        settings_lens=dict(),
    ):
        """Returns a jpg     picture which can be corrected for
        - lens distortion,
        - Real world coordinates
        Also returns a set of workspace coordinates and whether the pink circles were all found
        """
        from functools import reduce  # Not necessary in PY2, but compatible

        def save_debug_img(img, name):
            return octoprint_mrbeam.camera.save_debug_img(
                img, name + ".jpg", folder=path.join("/tmp")
            )

        err_txt = "Unrecognised Picture {} : {}, should be one of {}"
        if pic_type not in PIC_TYPES:
            raise ValueError(err_txt.format("Type", pic_type, PIC_TYPES))
        if which not in WHICH:
            raise ValueError(err_txt.format("desired", which, WHICH))
        do_corners = pic_type in (PIC_CORNER, PIC_BOTH)
        do_lens = pic_type in (PIC_LENS, PIC_BOTH)

        if which == LAST:
            img_jpg = self.camera_thread.get_latest_img()
        elif which == NEXT:
            img_jpg = self.camera_thread.get_next_img()
        else:
            raise Exception("We shouldn't be here, huhoo..")
        if not img_jpg:
            return None, -1, {}
        ts = self.camera_thread.latest_img_timestamp

        if do_corners:
            # Hack to get the show on the road
            settings_corners = corners.get_corner_calibration(
                self._settings.get(["corners_legacy_datafile"])
            )
        if do_corners and not corner_settings_valid(settings_corners):
            raise SettingsError(
                "Corner settings invalid - provided settings: %s" % settings_corners
            )
        if do_lens and not lens_settings_valid(settings_lens):
            raise SettingsError(
                "Lens settings invalid - provided settings: %s" % settings_lens
            )

        # Work is done on a numpy version of the image
        img = util.image.imdecode(img_jpg)
        if img is None:
            return None, -1, {}
        # Hack again : Ask the camera to adjust brightness -> Do auto inside the capture()
        self.camera_thread._cam.compensate_shutter_speed()
        settings = {}
        positions_pink_circles = corners.find_pink_circles(
            img, debug=util.factory_mode(), **settings
        )

        if not (img_jpg and (do_corners or do_lens)):
            # Will return if the image is None
            return img_jpg, ts, positions_pink_circles

        if do_lens:
            mtx = settings_lens["mtx"]
            dist = settings_lens["dist"]
            img, dest_mtx = lens.undistort(img, mtx, dist)
        else:
            mtx = None
            dist = None
            dest_mtx = None
        if do_corners:
            # settings_corners = plugin._settings.get(['corners'], {})
            # positions_pink_circles = dict_merge(
            #     settings_corners, positions_pink_circles
            # )
            try:
                simple_pos = {qd: v["pos"] for qd, v in positions_pink_circles.items()}
            except Exception as e:
                self._logger.debug("do corners error %s", e)
                raise MarkerError(
                    "Not all pink cirlces found",
                    positions_pink_circles,
                )
            positions_workspace_corners = corners.get_workspace_corners(
                simple_pos,
                settings_corners,
                undistorted=do_lens,
                mtx=mtx,
                dist=dist,
                new_mtx=dest_mtx,
            )
            if len(dict(positions_workspace_corners)) == 4:
                img = corners.fit_img_to_corners(
                    img, positions_workspace_corners, zoomed_out=True
                )
        # Write the modified image to a jpg binary
        buff = util.image.imencode(img)
        return buff, ts, positions_pink_circles

    def start_lens_calibration_daemon(self):
        """Start the Lens Calibration"""
        from .lens import BoardDetectorDaemon

        if self.lens_calibration_thread:
            self.lens_calibration_thread.start()
        else:
            self.lens_calibration_thread = BoardDetectorDaemon(
                self._settings.get(["lens_legacy_datafile"]),
                stateChangeCallback=self.send_lens_calibration_state,
                factory=True,
                runCalibrationAsap=util.factory_mode(),
                event_bus=self._event_bus,
            )
            # FIXME - Right now the npz files get loaded funny
            #         and some values aren't json pickable etc...
            self.lens_calibration_thread.state.rm_from_origin("factory")
            self.lens_calibration_thread.start()
        self.lens_calibration_thread.load_dir("/tmp")

    def stop_lens_calibration(self, blocking=True):
        # TODO : blocking behaviour goes into the daemon itself
        self.lens_calibration_thread.stop()
        if blocking:
            self.lens_calibration_thread.join()

    def capture_img_for_lens_calibration(self, *a, **kw):
        from threading import Timer

        # Ignore the arguments in case it getas triggered by an event that wants to pass on a payload etc...
        if len(self.lens_calibration_thread) == MIN_BOARDS_DETECTED - 1:
            self._logger.info("Last picture to be taken")
            self._event_bus.fire(MrBeamEvents.RAW_IMG_TAKING_LAST)
        elif (
            len(self.lens_calibration_thread) >= MIN_BOARDS_DETECTED
            and util.factory_mode()
        ):
            self._event_bus.fire(MrBeamEvents.RAW_IMG_TAKING_FAIL)
            self._logger.info("Ignoring this picture")
            return
        else:
            self._event_bus.fire(MrBeamEvents.RAW_IMAGE_TAKING_START)

        lens.capture_img_for_lens_calibration(
            self.lens_calibration_thread, self.camera_thread, "/tmp"
        )
        if len(self.lens_calibration_thread) >= MIN_BOARDS_DETECTED:
            self._event_bus.fire(MrBeamEvents.LENS_CALIB_PROCESSING_BOARDS)
            self.lens_calibration_thread.scaleProcessors(2)
        else:
            self._event_bus.fire(MrBeamEvents.RAW_IMAGE_TAKING_DONE)


__plugin_name__ = "Camera"
__plugin_pythoncompat__ = ">=2.7,<4"


def __plugin_load__():
    plugin = CameraPlugin()
    global __plugin_implementation__
    __plugin_implementation__ = plugin

    global __plugin_settings_overlay__
    if util.factory_mode():
        disabled_plugins = [
            "cura",
            "pluginmanager",
            "announcements",
            "corewizard",
            "octopi_support",
            "mrbeam",
            "mrbeamdoc",
            "virtual_printer",
        ]
    else:
        # disables itself
        disabled_plugins = [
            "camera",
        ]
    __plugin_settings_overlay__ = dict(
        plugins=dict(_disabled=disabled_plugins),  # accepts dict | pfad.yml | callable
        appearance=dict(
            components=dict(
                disabled=dict(
                    wizard=["plugin_softwareupdate"],
                    settings=["serial", "webcam", "terminalfilters"],
                ),
            )
        ),
    )
    global __plugin_hooks__
    __plugin_hooks__ = {
        "octoprint.camera.get_picture": plugin.get_picture,
        # TODO Stage 3 - Trigger from iobeam or mrbeam plugin
        "octoprint.camera.capture_pic_to_lens_calibration": plugin.capture_img_for_lens_calibration,
    }
