# coding=utf-8
from __future__ import absolute_import

import octoprint.plugin

class CameraPlugin(octoprint.plugin.StartupPlugin,
                       octoprint.plugin.TemplatePlugin,
                       octoprint.plugin.SettingsPlugin,
                       octoprint.plugin.AssetPlugin):
	def on_after_startup(self):
		# TODO Stage 1 - Start the camera.
		self._logger.info("Hello World! (more: %s)" % self._settings.get(["url"]))

	def get_settings_defaults(self):
		# TODO Stage 2 - Takes over the Camera settings from the MrBPlugin.
		return dict(url="https://en.wikipedia.org/wiki/Hello_world")

	def get_template_configs(self):
		# TODO Stage 2 - Takes over the Camera settings from the MrBPlugin.
		return [
			dict(type="settings", custom_bindings=False)
		]

	def get_assets(self):
		# TODO Stage 1 - Camera Calibration UI
		return dict(
			js=["js/helloworld.js"],
			css=["css/helloworld.css"],
			less=["less/helloworld.less"]
		)

__plugin_name__ = "Camera"
__plugin_pythoncompat__ = ">=2.7,<4"
__plugin_implementation__ = CameraPlugin()
