# coding=utf-8
from __future__ import absolute_import

import os
import platform
import time
import socket

from octoprint_camera.camera import (
    MIN_BOARDS_DETECTED,
    lens,
    corners,
    config,
    ERR_NEED_CALIB,
    STATE_SUCCESS,
)
from octoprint_camera.camera.lens import BoardDetectorDaemon

IS_X86 = platform.machine() == "x86_64"  # TODO-josef check what this is for

import octoprint.plugin
from flask import request, jsonify, make_response, url_for
from flask_babel import gettext
from octoprint.server import NO_CONTENT
from octoprint.server.util.flask import add_non_caching_response_headers
from octoprint.settings import settings
from octoprint_mrbeam.mrbeam_events import MrBeamEvents
from octoprint_mrbeam.user_notification_system import user_notification_system
from octoprint_mrbeam.support import check_support_mode, check_calibration_tool_mode
from octoprint_mrbeam.util.cmd_exec import exec_cmd, exec_cmd_output
from octoprint_mrbeam.gcodegenerator.job_params import JobParams
from octoprint_mrbeam.util.device_info import deviceInfo
from octoprint_mrbeam.util.flask import (
    restricted_access_or_calibration_tool_mode,
    calibration_tool_mode_only,
)

from octoprint_camera import camera
from octoprint_camera.__version import __version__
from octoprint_camera.photo_creator import PhotoCreator
from octoprint_camera.camera.undistort import MIN_MARKER_PIX
from octoprint_camera.camera.label_printer import labelPrinter
from octoprint_camera.util.calibration_marker import CalibrationMarker
from octoprint_mrbeam.printing.profile import (
    laserCutterProfileManager,
    InvalidProfileError,
    CouldNotOverwriteError,
    Profile,
)
from threading import Event
from octoprint_camera.camera_handler import cameraHandler


class CameraPlugin(
    octoprint.plugin.StartupPlugin,
    octoprint.plugin.TemplatePlugin,
    octoprint.plugin.SettingsPlugin,
    octoprint.plugin.AssetPlugin,
    octoprint.plugin.BlueprintPlugin,
):
    BOOT_GRACE_PERIOD = 10  # seconds

    def __init__(self):
        self._plugin_version = __version__
        self._device_info = deviceInfo(use_dummy_values=IS_X86)
        self._hostname = None  # see self.getHosetname()
        self._lid_closed = True
        self._interlock_closed = True
        self._is_slicing = False
        self._client_opened = False
        self.force_taking_picture = Event()
        self.force_taking_picture.clear()
        self._device_series = self._device_info.get_series()
        self.laserCutterProfileManager = laserCutterProfileManager(
            profile_id="MrBeam" + self._device_series
        )

    def on_after_startup(self):
        # TODO Stage 1 - Start the camera.
        self._logger.debug("Hello World From Camera Plugin! (more: %s)")
        self.cameraHandler = cameraHandler(self)
        self.user_notification_system = user_notification_system(
            self
        )  # start usernotification system from mrbeam

    def get_settings_defaults(self):
        # TODO Stage 2 - Takes over the Camera settings from the MrBPlugin.
        image_default_width = 2048
        image_default_height = 1536

        cam_folder = os.path.join(
            settings().getBaseFolder("base"), camera.LENS_CALIBRATION["path"]
        )

        self._logger.info("cam folder %s" % cam_folder, camera.LENS_CALIBRATION["path"])

        return dict(
            cam=dict(
                cam_img_width=image_default_width,
                cam_img_height=image_default_height,
                frontendUrl="/downloads/files/local/cam/beam-cam.jpg",
                previewOpacity=1,
                localFilePath="cam/beam-cam.jpg",
                localUndistImage="cam/undistorted.jpg",
                keepOriginals=False,
                # TODO: we nee a better and unified solution for our custom paths. Some day...
                correctionSettingsFile="{}/cam/pic_settings.yaml".format(
                    settings().getBaseFolder("base")
                ),
                correctionTmpFile="{}/cam/last_markers.json".format(
                    settings().getBaseFolder("base")
                ),
                lensCalibration={
                    k: os.path.join(cam_folder, camera.LENS_CALIBRATION[k])
                    for k in ["legacy", "user", "factory"]
                },
                saveCorrectionDebugImages=False,
                markerRecognitionMinPixel=MIN_MARKER_PIX,
                remember_markers_across_sessions=True,
            ),
        )

    def get_template_configs(self):
        # TODO Stage 2 - Takes over the Camera settings from the MrBPlugin.
        return [dict(type="settings", custom_bindings=False)]

    def get_assets(self):
        # TODO Stage 1 - Camera Calibration UI
        self._logger.debug("Camer Plugin get assets")
        return dict(
            js=[
                # "js/settings/camera_settings.js",#user settings
                "js/camera.js",
                "js/settings/camera_settings.js",
                "js/calibration/calibration.js",
                "js/calibration/corner_calibration.js",
                "js/calibration/lens_calibration.js",
                "js/calibration/watterott/camera_alignment.js",
                "js/calibration/watterott/calibration_qa.js",
                "js/calibration/watterott/label_printer.js",
                "",
            ],
            css=[
                "css/calibration_qa.css",
                "css/mrbeam.css",
            ],
            less=[],
        )

    ##~~ Event Handler Plugin API

    def on_event(self, event, payload):

        if event == MrBeamEvents.BOOT_GRACE_PERIOD_END:
            if self.calibration_tool_mode:
                self._printer.home("Homing before starting calibration tool")
                self.cameraHandler.onLensCalibrationStart()

    def get_plugin_version(self):
        return self._plugin_version

    def get_env(self, type=None):
        return "TODO"  # TODO josef get from mrbeam plugin maybe plugin_manager.getplugininfo

    @property
    def calibration_tool_mode(self):
        """Get the calibration tool mode"""
        ret = check_calibration_tool_mode(self)
        # self._fixEmptyUserManager()
        return ret

    ##~~ BlueprintPlugin mixin

    # disable default api key check for all blueprint routes.
    # use @restricted_access, @firstrun_only_access to check permissions
    def is_blueprint_protected(self):
        return False  # No API key required to request API access

    @octoprint.plugin.BlueprintPlugin.route("/calibration", methods=["GET"])
    # @calibration_tool_mode_only
    def calibration_wrapper(self):
        from flask import make_response, render_template
        from octoprint.server import debug, VERSION, DISPLAY_VERSION, UI_API_KEY, BRANCH

        self._logger.info(
            UI_API_KEY + "Hello World! (more: %s)" % settings().get(["url"])
        )

        display_version_string = "{} on {}".format(
            self._plugin_version, self.getHostname()
        )

        # if self._branch:
        #     display_version_string = "{} ({} branch) on {}".format(
        #         self._plugin_version, self._branch, self.getHostname()
        #     )
        render_kwargs = dict(
            debug=debug,
            # firstRun=self.isFirstRun(),
            version=dict(number=VERSION, display=DISPLAY_VERSION, branch=BRANCH),
            uiApiKey=UI_API_KEY,
            templates=dict(tab=[]),
            pluginNames=dict(),
            locales=dict(),
            supportedExtensions=[],
            # beamOS version
            beamosVersionNumber=self._plugin_version,
            # beamosVersionBranch=self._branch,
            beamosVersionDisplayVersion=display_version_string,
            # beamosVersionImage=self._octopi_info,
            # environment
            # env=self.get_env(),
            # env_local=self.get_env(self.ENV_LOCAL),
            # env_laser_safety=self.get_env(self.ENV_LASER_SAFETY),
            # env_analytics=self.get_env(self.ENV_ANALYTICS),
            # env_support_mode=self.support_mode,
            #
            # product_name=self.get_product_name(),
            hostname=self.getHostname(),
            # serial=self._serial_num,
            # beta_label=self.get_beta_label(),
            e="null",
            gcodeThreshold=0,  # legacy
            gcodeMobileThreshold=0,  # legacy
        )

        r = make_response(
            render_template(
                "calibration/watterott/calibration_tool.jinja2", **render_kwargs
            )
        )

        r = add_non_caching_response_headers(r)
        return r

    def take_undistorted_picture(self, is_initial_calibration):
        self._logger.debug(
            "New undistorted image is requested. is_initial_calibration: %s",
            is_initial_calibration,
        )
        # self.cameraHandler._photo_creator.is_initial_calibration = is_initial_calibration //TODO josef move from lid handler?
        self.cameraHandler._startStopCamera("initial_calibration")
        succ = self.cameraHandler.takeNewPic()
        if succ:
            resp_text = {
                "msg": gettext("A new picture is being taken, please wait a little...")
            }
            code = 200
        else:
            resp_text = {
                "msg": gettext("Either the camera is busy or the lid is not open.")
            }
            code = 503
        image_response = make_response(jsonify(resp_text), code)
        self._logger.debug("Image_Response: {}".format(image_response))
        return image_response

    ### Camera Calibration - START ###
    # The next calls are needed for the camera calibration

    @octoprint.plugin.BlueprintPlugin.route(
        "/take_undistorted_picture", methods=["GET"]
    )
    @restricted_access_or_calibration_tool_mode
    def takeUndistortedPictureForInitialCalibration(self):
        self._logger.info("INITIAL_CALIBRATION TAKE PICTURE")
        # return same as the Simple Api Call
        return self.take_undistorted_picture(is_initial_calibration=True)

    @octoprint.plugin.BlueprintPlugin.route(
        "/on_camera_picture_transfer", methods=["GET"]
    )
    @restricted_access_or_calibration_tool_mode
    def onCameraPictureTransfer(self):
        self.cameraHandler.on_front_end_pic_received()
        return NO_CONTENT

    @octoprint.plugin.BlueprintPlugin.route(
        "/calibration_save_raw_pic", methods=["GET"]
    )
    @restricted_access_or_calibration_tool_mode
    def onCalibrationSaveRawPic(self):
        self._logger.debug("SAVE RAW IMAGE")
        self.cameraHandler.saveRawImg()
        return NO_CONTENT

    @octoprint.plugin.BlueprintPlugin.route("/calibration_get_raw_pic", methods=["GET"])
    @restricted_access_or_calibration_tool_mode
    def onCalibrationGetRawPic(self):
        self.cameraHandler.getRawImg()
        return NO_CONTENT

    @octoprint.plugin.BlueprintPlugin.route("/calibration_lens_start", methods=["GET"])
    @restricted_access_or_calibration_tool_mode
    def onLensCalibrationStart(self):
        self.cameraHandler.onLensCalibrationStart()
        return NO_CONTENT

    @octoprint.plugin.BlueprintPlugin.route("/calibration_del_pic", methods=["POST"])
    @restricted_access_or_calibration_tool_mode
    def onCalibrationDelRawPic(self):
        self._logger.debug("Command given : /calibration_del_pic")
        try:
            json_data = request.json
        except JSONBadRequest:
            return make_response("Malformed JSON body in request", 400)

        if not "name" in json_data.keys():
            # TODO correct error message
            return make_response("No profile included in request", 400)

        # TODO catch file not exist error
        self.cameraHandler.delRawImg(json_data["name"])
        return NO_CONTENT

    @octoprint.plugin.BlueprintPlugin.route(
        "/camera_run_lens_calibration", methods=["POST"]
    )
    @restricted_access_or_calibration_tool_mode
    def onCalibrationRunLensDistort(self):
        self._logger.debug("Command given : camera_run_lens_calibration")
        self.cameraHandler.saveLensCalibration()
        return NO_CONTENT

    @octoprint.plugin.BlueprintPlugin.route(
        "/camera_stop_lens_calibration", methods=["POST"]
    )
    @restricted_access_or_calibration_tool_mode
    def onCalibrationStopLensDistort(self):
        self._logger.debug("Command given : camera_stop_lens_calibration")
        self.cameraHandler.stopLensCalibration()
        return NO_CONTENT

    @octoprint.plugin.BlueprintPlugin.route(
        "/send_corner_calibration", methods=["POST"]
    )
    @restricted_access_or_calibration_tool_mode
    def sendInitialCalibrationMarkers(self):
        if not "application/json" in request.headers["Content-Type"]:
            return make_response("Expected content-type JSON", 400)
        try:
            json_data = request.json
        except JSONBadRequest:
            return make_response("Malformed JSON body in request", 400)

        self._logger.debug(
            "INITIAL camera_calibration_markers() data: {}".format(json_data)
        )

        if not "result" in json_data or not all(
            k in json_data["result"].keys() for k in ["newCorners", "newMarkers"]
        ):
            # TODO correct error message
            return make_response("No profile included in request", 400)

        self.camera_calibration_markers(json_data)
        return NO_CONTENT

    @octoprint.plugin.BlueprintPlugin.route("/print_label", methods=["POST"])
    @calibration_tool_mode_only
    def printLabel(self):
        res = labelPrinter(self, use_dummy_values=IS_X86).print_label(request)
        return make_response(jsonify(res), 200 if res["success"] else 502)

    @octoprint.plugin.BlueprintPlugin.route(
        "/engrave_calibration_markers/<string:intensity>/<string:feedrate>",
        methods=["GET"],
    )
    @restricted_access_or_calibration_tool_mode
    def engraveCalibrationMarkers(self, intensity, feedrate):
        profile = self.laserCutterProfileManager.get_current_or_default()
        try:
            i = int(int(intensity) / 100.0 * JobParams.Max.INTENSITY)
            f = int(feedrate)
        except ValueError:
            return make_response("Invalid parameters", 400)

        # validate input
        if (
            i < JobParams.Min.INTENSITY
            or i > JobParams.Max.INTENSITY
            or f < JobParams.Min.SPEED
            or f > JobParams.Max.SPEED
        ):
            return make_response("Invalid parameters", 400)
        cm = CalibrationMarker(
            str(profile["volume"]["width"]), str(profile["volume"]["depth"])
        )
        gcode = cm.getGCode(i, f)

        # run gcode
        # check serial connection
        if self._printer is None or self._printer._comm is None:
            return make_response("Laser: Serial not connected", 400)

        if self._printer.get_state_id() == "LOCKED":
            self._printer.home("xy")

        seconds = 0
        while (
            self._printer.get_state_id() != "OPERATIONAL" and seconds <= 26
        ):  # homing cycle 20sec worst case, rescue from home ~ 6 sec total (?)
            time.sleep(1.0)  # wait a second
            seconds += 1

        # check if idle
        if not self._printer.is_operational():
            return make_response("Laser not idle", 403)

        # select "file" and start
        self._printer._comm.selectGCode(gcode)
        self._printer._comm.startPrint()
        return NO_CONTENT

    ### Camera Calibration - END ###
    def getHostname(self):
        """
        Returns device hostname like 'MrBeam2-F930'.
        If system hostname (/etc/hostname) is different it'll be set (overwritten!!) to the value from device_info
        :return: String hostname
        """
        if self._hostname is None:
            hostname_dev_info = self._device_info.get_hostname()
            hostname_socket = None
            try:
                hostname_socket = socket.gethostname()
            except:
                self._logger.exception("Exception while reading hostname from socket.")
                pass

            # yes, let's go with the actual host name until changes have applied.
            self._hostname = hostname_socket

            if hostname_dev_info != hostname_socket and not IS_X86:
                self._logger.warn(
                    "getHostname() Hostname from device_info file does NOT match system hostname. device_info: {dev_info}, system hostname: {sys}. Setting system hostname to {dev_info}".format(
                        dev_info=hostname_dev_info, sys=hostname_socket
                    )
                )
                exec_cmd(
                    "sudo /root/scripts/change_hostname {}".format(hostname_dev_info)
                )
                exec_cmd(
                    "sudo /root/scripts/change_apname {}".format(hostname_dev_info)
                )
                self._logger.warn(
                    "getHostname() system hostname got changed to: {}. Requires reboot to take effect!".format(
                        hostname_dev_info
                    )
                )
        return self._hostname


__plugin_name__ = "Camera"
__plugin_pythoncompat__ = ">=2.7,<4"


# __plugin_implementation__ = CameraPlugin()


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
            ]  # accepts dict | pfad.yml | callable
        ),
        appearance=dict(
            components=dict(
                # order=dict(
                #     settings=[
                #         "plugin_mrbeam_about",
                #         "plugin_softwareupdate",
                #         "accesscontrol",
                #         "plugin_mrbeam_maintenance",
                #         "plugin_netconnectd",
                #         "plugin_findmymrbeam",
                #         "plugin_mrbeam_conversion",
                #         "plugin_mrbeam_camera",
                #         "plugin_mrbeamcamera",
                #         "plugin_mrbeam_backlash",
                #         "plugin_mrbeam_custom_material",
                #         "plugin_mrbeam_airfilter",
                #         "plugin_mrbeam_analytics",
                #         "plugin_mrbeam_reminders",
                #         "plugin_mrbeam_leds",
                #         "logs",
                #         "plugin_mrbeam_debug",
                #     ],
                # ),
                disabled=dict(
                    wizard=["plugin_softwareupdate"],
                    settings=["serial", "webcam", "terminalfilters"],
                ),
            )
        ),
    )
