# coding=utf-8
from __future__ import absolute_import

import os
import time
from random import randint

import flask
import octoprint.plugin
from flask import jsonify
from octoprint.server.util.flask import add_non_caching_response_headers
from octoprint.settings import settings
from octoprint_mrbeam.support import check_support_mode, check_calibration_tool_mode


from octoprint_camera.__version import __version__


class CameraPlugin(
    octoprint.plugin.StartupPlugin,
    octoprint.plugin.TemplatePlugin,
    octoprint.plugin.SettingsPlugin,
    octoprint.plugin.AssetPlugin,
    octoprint.plugin.BlueprintPlugin,
):
    def __init__(self):
        self._plugin_version = __version__

    def on_after_startup(self):
        # TODO Stage 1 - Start the camera.
        self._logger.debug("Hello World From Camera Plugin! (more: %s)")

    def get_settings_defaults(self):
        # TODO Stage 2 - Takes over the Camera settings from the MrBPlugin.
        image_default_width = 2048
        image_default_height = 1536

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
                # lensCalibration={
                #     k: os.path.join(cam_folder, camera.LENS_CALIBRATION[k])
                #     for k in ["legacy", "user", "factory"]
                # },
                saveCorrectionDebugImages=False,
                # markerRecognitionMinPixel=MIN_MARKER_PIX,
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

    # @property
    # def calibration_tool_mode(self):
    #     """Get the calibration tool mode"""
    #     ret = check_calibration_tool_mode(self)
    #     # self._fixEmptyUserManager()
    #     return ret

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

        # display_version_string = "{} on {}".format(
        #     self._plugin_version, self.getHostname()
        # )

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
            # beamosVersionDisplayVersion=display_version_string,
            # beamosVersionImage=self._octopi_info,
            # environment
            # env=self.get_env(),
            # env_local=self.get_env(self.ENV_LOCAL),
            # env_laser_safety=self.get_env(self.ENV_LASER_SAFETY),
            # env_analytics=self.get_env(self.ENV_ANALYTICS),
            # env_support_mode=self.support_mode,
            #
            # product_name=self.get_product_name(),
            # hostname=self.getHostname(),
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

    # Returns the latest available image to diplay on the interface
    @octoprint.plugin.BlueprintPlugin.route("/image", methods=["GET"])
    def getImage(self):
        # TODO return correct image
        # get random file for test
        f = []
        for root, dirs, files in os.walk(
            os.path.join(os.path.dirname(__file__), "static/img/calibration")
        ):
            for filename in files:
                f.append(filename)
        randomfilenumber = randint(0, len(f) - 1)

        # return file
        file = os.path.join(
            os.path.dirname(__file__), "static/img/calibration", f[randomfilenumber]
        )
        self._logger.debug("selected file " + file + " ending " + file.split(".")[1])
        filetype = file.split(".")[1]
        if filetype == "svg":
            filetype = "svg+xml"

        # returns the next avaiable image
        if "type" in flask.request.values and flask.request.values["type"] == "next":
            return flask.send_file(
                os.path.join(
                    os.path.dirname(__file__),
                    "static/img/calibration/undistorted_bad1.jpg",
                ),
                mimetype="image/jpg",
            )
        # returns the currently avaiable image
        return flask.send_file(
            file,
            mimetype="image/" + filetype,
        )

    # Returns the latest unprocessed image from the camera
    @octoprint.plugin.BlueprintPlugin.route("/imageRaw", methods=["GET"])
    def getRawImage(self):
        # TODO return correct raw image
        file = os.path.join(
            os.path.dirname(__file__), "static/img/calibration/undistorted_ok.jpg"
        )
        # returns the next avaiable image
        if "type" in flask.request.values and flask.request.values["type"] == "next":
            return flask.send_file(
                os.path.join(
                    os.path.dirname(__file__),
                    "static/img/calibration/undistorted_bad1.jpg",
                ),
                mimetype="image/jpg",
            )
        # returns the currently avaiable image
        return flask.send_file(file, mimetype="image/jpg")

    # Returns the timestamp of the latest available image
    @octoprint.plugin.BlueprintPlugin.route("/timestamp", methods=["GET"])
    @octoprint.plugin.BlueprintPlugin.route("/ts", methods=["GET"])
    def getTimestamp(self):
        data = {"timestamp": time.time() - 5 * 60}  # TODO return correct timestamp
        return jsonify(data)

    # Returns the timestamp of the latest "raw" image
    @octoprint.plugin.BlueprintPlugin.route("/timestamp_raw", methods=["GET"])
    @octoprint.plugin.BlueprintPlugin.route("/ts_raw", methods=["GET"])
    def getTimestampRaw(self):
        data = {"timestamp": time.time()}  # TODO return correct timestamp
        return jsonify(data)

    # Whether the camera is running or not
    @octoprint.plugin.BlueprintPlugin.route("/running", methods=["GET"])
    def getRunningState(self):
        data = {"running": True}  # TODO return correct state
        return jsonify(data)

    # return whether the camera can run now
    @octoprint.plugin.BlueprintPlugin.route("/available", methods=["GET"])
    def getAvailableState(self):
        data = {"available": True}  # TODO return correct available state
        return jsonify(data)


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
