# coding=utf-8
from __future__ import absolute_import, print_function, unicode_literals, division
import platform
import socket

import octoprint.plugin
from octoprint.server.util.flask import add_non_caching_response_headers
from octoprint.settings import settings
from octoprint_mrbeam.support import check_support_mode, check_calibration_tool_mode


from .__version import __version__
from .camera import CameraThread
from .util import logme, logExceptions

from octoprint_mrbeam.camera.definitions import LEGACY_STILL_RES
IMG_WIDTH, IMG_HEIGHT = LEGACY_STILL_RES

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


    def on_after_startup(self):
        self.camera_thread = CameraThread(self._settings, debug=self._settings.get(['debug']))
        # TODO stage 2 - Only start the camera when required
        self.camera_thread.start()

    def on_shutdown(self):
        if self.camera_thread:
            self.camera_thread.stop()
        self._logger.debug("Camera thread joined")

    def get_settings_defaults(self):
        # TODO Stage 2 - Takes over the Camera settings from the MrBPlugin.
        base_folder = settings().getBaseFolder("base")

        return dict(
            cam_img_width=IMG_WIDTH,
            cam_img_height=IMG_HEIGHT,
            debug=True,
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
                # remember_markers_across_sessions=True,
            ),
        )

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
                "",
            ],
            css=[
                "css/calibration_qa.css",
                "css/mrbeam.css",
            ],
            less=[],
        )

    # NOTE : Can be re-enabled for the factory mode.
    #        For now, it is always in factory mode
    # TODO : calibration tool mode as long as the
    #        factory calibration is not done and validated
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

        render_kwargs = dict(
            debug=debug,
            version=dict(number=VERSION, display=DISPLAY_VERSION, branch=BRANCH),
            uiApiKey=UI_API_KEY,
            templates=dict(tab=[]),
            pluginNames=dict(),
            locales=dict(),
            supportedExtensions=[],
            # beamOS version
            beamosVersionNumber=__version__,
            hostname=socket.gethostname(),
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
