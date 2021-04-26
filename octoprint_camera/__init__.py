# coding=utf-8
from __future__ import absolute_import, print_function, unicode_literals, division

import base64
import flask
from flask import jsonify, request
import io
import json
import os
from os import path
from random import randint
import socket
import sys
import time

PY3 = sys.version_info >= (3,)

import octoprint.plugin
from octoprint.server.util.flask import add_non_caching_response_headers
from octoprint.settings import settings
from octoprint.util import dict_merge
from octoprint_mrbeam.camera.definitions import LEGACY_STILL_RES
from octoprint_mrbeam.camera.undistort import _getCamParams
from octoprint_mrbeam.support import check_support_mode, check_calibration_tool_mode

import pkg_resources
__version__ = pkg_resources.require("octoprint_camera")

from . import corners, lens, util
from .camera import CameraThread
# from .image import LAST, NEXT, WHICH, PIC_PLAIN, PIC_CORNER, PIC_LENS, PIC_BOTH, PIC_TYPES
from .util import logme, logExceptions
from .util.image import corner_settings_valid, lens_settings_valid, SettingsError
from .util.flask import send_image


IMG_WIDTH, IMG_HEIGHT = LEGACY_STILL_RES
PIC_PLAIN = "plain" # The equivalent of "raw" pictures
PIC_CORNER = "corner" # Corrected for the position of the work area corners
PIC_LENS = "lens" # Corrected for the lens distortion
PIC_BOTH = "both" # Corrected corners + lens
PIC_TYPES = (PIC_PLAIN, PIC_CORNER, PIC_LENS, PIC_BOTH)
LAST = "last"
NEXT = "next"
WHICH = (LAST, NEXT)


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
        self.lens_settings = {}
        # Shadow settings for the pink circles position history
        self.__corners_hist_datafile = None
        self.__corners_hist_settings = {}
        # Shadow settings for the lens settings
        self.__lens_datafile = None
        self.__lens_settings = {}

        from octoprint.server import debug
        self.debug = debug

    ##~~ StartupPlugin mixin

    def on_after_startup(self, *a, **kw):
        self.camera_thread = CameraThread(self._settings, debug=self._settings.get(['debug']))
        # TODO stage 2 - Only start the camera when required
        self.camera_thread.start()

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
                history_datafile=path.join(self.get_plugin_data_folder(), "pink_marker_history.yaml"),
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

    def get_template_configs(self):
        # TODO Stage 2 - Takes over the Camera settings from the MrBPlugin.
        return [dict(type="settings", custom_bindings=False)]

    def get_assets(self):
        # TODO Stage 1 - Camera Calibration UI
        return dict(
            js=[
                "js/camera.js",
                "js/settings/camera_settings.js",
                "js/calibration/calibration.js",
                "js/calibration/corner_calibration.js",
                "js/calibration/lens_calibration.js",
                "js/calibration/watterott/camera_alignment.js",
                "js/calibration/watterott/calibration_qa.js",
                "js/calibration/watterott/label_printer.js",
                "js/calibrationmodeMessage.js",
            ],
            css=[
                "css/calibration_qa.css",
                "css/mrbeam.css",
            ],
            less=[],
        )

    ##~~ BlueprintPlugin mixin

    # disable default api key check for all blueprint routes.
    # use @restricted_access, @firstrun_only_access to check permissions
    def is_blueprint_protected(self):
        return False  # No API key required to request API access

    @octoprint.plugin.BlueprintPlugin.route("/calibration", methods=["GET"])
    # @calibration_tool_mode_only
    @logExceptions
    def calibration_wrapper(self):
        from flask import make_response, render_template
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
            get_img=json.dumps(dict(
                last = LAST,
                next = NEXT,
                pic_plain=PIC_PLAIN,
                pic_corner=PIC_CORNER,
                pic_lens=PIC_LENS,
                pic_both=PIC_BOTH,
                pic_types=PIC_TYPES,)),
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
        which=values.get("which", "something else")
        if not which in WHICH:
            return flask.make_response(
                "which should be a selection of {}, not {}".format(WHICH, which), 405
            )
        pic_type = values.get("pic_type")
        if not pic_type in PIC_TYPES:
            return flask.make_response("type should be a selection of {}, not {}".format(PIC_TYPES, pic_type), 407)
        if self._settings.get(['debug']):
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
                    os.path.dirname(__file__), "static/img/calibration", f[randint(0, len(f) - 1)]
                )
                # filepath = "static/img/calibration/qa_final_rectangle.jpg"
            return send_image(
                os.path.join(
                    os.path.dirname(__file__),
                    filepath,
                ),
                timestamp=time.time(),
                pic_type=pic_type,
                which=which,
            )
        else:
            # TODO return correct image
            corners = dict_merge(
                self._settings.get(['corners', 'factory']) or {},
                self._settings.get(['corners', 'history']) or {},
            )
            try:
                image, timestamp, positions_workspace_corners = self.get_picture(pic_type, which, settings_corners=corners)
            except SettingsError as e:
                return flask.make_response("Wrong camera settings for the requested picture %s" % e, 500)
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
            dict(newImage=time.time()),
        )

    # Returns the timestamp of the latest available image
    @octoprint.plugin.BlueprintPlugin.route("/timestamp", methods=["GET"])
    @octoprint.plugin.BlueprintPlugin.route("/ts", methods=["GET"])
    @logExceptions
    def getTimestamp(self):
        data = {"timestamp": time.time() - 5 * 60}  # TODO return correct timestamp
        return jsonify(data)

    # Whether the camera is running or not
    @octoprint.plugin.BlueprintPlugin.route("/running", methods=["GET"])
    @logExceptions
    def getRunningState(self):
        data = {"running": True}  # TODO return correct state
        return jsonify(data)

    # return whether the camera can run now
    @octoprint.plugin.BlueprintPlugin.route("/available", methods=["GET"])
    @logExceptions
    def getAvailableState(self):
        data = {"available": True}  # TODO return correct available state
        return jsonify(data)


    ##~~ Camera Plugin


    # NOTE : Can be re-enabled for the factory mode.
    #        For now, it is always in factory mode
    # TODO : Phase 2 - calibration tool mode as long as the
    #        factory calibration is not done and validated
    # @property
    # def calibration_tool_mode(self):
    #     """Get the calibration tool mode"""
    #     ret = check_calibration_tool_mode(self)
    #     # self._fixEmptyUserManager()
    #     return ret

    def get_picture(self, pic_type="plain", which="last", settings_corners=dict(), settings_lens=dict()):
        """Returns a jpg     picture which can be corrected for
        - lens distortion,
        - Real world coordinates
        Also returns a set of workspace coordinates and whether the pink circles were all found
        """
        from functools import reduce # Not necessary in PY2, but compatible
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
        ts = self.camera_thread.latest_img_timestamp
        
        if do_corners and not corner_settings_valid(settings_corners):
            raise SettingsError("Corner settings invalid - provided settings: %s" % settings_corners)
        if do_lens and not lens_settings_valid(settings_lens):
            raise SettingsError("Lens settings invalid - provided settings: %s" % settings_lens)
        
        # Work is done on a numpy version of the image
        img = util.image.imdecode(img_jpg)
        settings = {}
        positions_pink_circles = corners.find_pink_circles(img, debug=self.debug, **settings)

        if not (img_jpg and (do_corners or do_lens)):
            # Will return if the image is None
            return img_jpg, ts, positions_pink_circles
        
        if do_corners:
            # settings_corners = plugin._settings.get(['corners'], {})
            positions_pink_circles = dict_merge(settings_corners, positions_pink_circles)
            positions_workspace_corners = corners.get_workspace_corners(positions_pink_circles, **settings)
        else:
            positions_workspace_corners = None
        if do_lens:
            img = lens.undistort(img, **settings)
            if do_corners:
                positions_workspace_corners = lens.undist_points(positions_workspace_corners, **settings)
        if do_corners and len(positions_workspace_corners) == 4:
            img = corners.fit_img_to_corners(img, positions_workspace_corners)
        # Write the modified image to a jpg binary
        buff = io.BytesIO()
        util.image.imwrite(buff, img)
        return buff, ts, positions_pink_circles

    def start_lens_calibration_daemon(self):
        """Start the Lens Calibration"""
        from .lens import BoardDetectorDaemon
        if self.lens_calibration_thread:
            self.lens_calibration_thread.start()
        else:
            self.lens_calibration_thread = BoardDetectorDaemon()
            self.lens_calibration_thread.start()

    def stop_lens_calibration(self, blocking=True):
        # TODO : blocking behaviour goes into the daemon itself
        self.lens_calibration_thread.stop()
        if blocking:
            self.lens_calibration_thread.join()



__plugin_name__ = "Camera"
__plugin_pythoncompat__ = ">=2.7,<4"


def __plugin_load__():
    global __plugin_implementation__
    __plugin_implementation__ = CameraPlugin()

    global __plugin_settings_overlay__
    __plugin_settings_overlay__ = dict(
        plugins=dict(
            _disabled=[
                "cura",
                "pluginmanager",
                "announcements",
                "corewizard",
                "octopi_support",
                "mrbeam",
                "mrbeamdoc",
                "virtual_printer",
            ]  # accepts dict | pfad.yml | callable
        ),
        appearance=dict(
            components=dict(
                disabled=dict(
                    wizard=["plugin_softwareupdate"],
                    settings=["serial", "webcam", "terminalfilters"],
                ),
            )
        ),
    )
