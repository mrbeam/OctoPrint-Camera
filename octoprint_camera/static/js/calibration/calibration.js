/*
 * View model for Mr Beam
 *
 * Author: Teja Philipp <teja@mr-beam.org>
 * License: AGPLv3
 */
/* global OctoPrint, OCTOPRINT_VIEWMODELS, INITIAL_CALIBRATION */
const STATIC_URL = "/plugin/camera/static/img/calibration/calpic_wait.svg";

$(function () {
    function CalibrationViewModel(parameters) {
        let self = this;
        window.mrbeam.viewModels["calibrationViewModel"] = self;
        self.TABS = {
            alignment: "camera_alignment_tab_btn",
            lens: "lenscal_tab_btn",
            corner: "cornercal_tab_btn",
            quality: "qacal_tab_btn",
            labels: "done_tab_btn",
            debug: "debug_tab_btn",
        };
        self.cameraSettings = parameters[0];
        self.camera = parameters[1];
        self.loginState = parameters[2];

        self.calibrationScreenShown = ko.observable(false);
        self.activeTab = ko.observable();

        // calibrationState is constantly refreshed by the backend
        // as an immutable array that contains the whole state of the calibration
        self.calibrationState = ko.observable({});

        self.onStartupComplete = function () {
            self.calibrationScreenShown(true);
            self._loginUser();
            self._showCalibrationTool();
        };

        self.resetUserView = function () {
            self.cameraSettings.changeUserView("settings");
        };

        self.simpleApiCommand = self.camera.simpleApiCommand;

        self._showCalibrationTool = function () {
            $("#calibration_tool_content").show();
            $("#calibration_tool_loading_overlay").hide();
            $('a[data-toggle="tab"]').on("shown", function (e) {
                // e.target // activated tab
                // e.relatedTarget // previous tab
                self.activeTab(e.target.id);
            });
        };

        self.onAllBound = function () {
            PNotify.prototype.options.stack.context = $(
                "#initial_camera_calibration"
            ); // we explicitly override the octoprint main.js to bin the Pnotifys to out id so the uistate will not be loaded
        };
        self._loginUser = function (data2, callback) {
            console.log("Login user for calibration.");
            const data = { test: "test" };
            OctoPrint.postJson("plugin/camera/calibration_login", data)
                .done(function () {
                    const user = "calibration@mr-beam.org";
                    const pass = "a";
                    self.loginState.login(user, pass, true).done(function () {
                        if (callback) callback();
                    });
                })
                .fail(function () {
                    console.error("Failed to set up calibration user.");
                    new PNotify({
                        title: gettext("Failed to create user"),
                        text: _.sprintf(
                            gettext(
                                "An error happened while creating user account.<br/><br/>%(opening_tag)sPlease click here to start over.%(closing_tag)s"
                            ),
                            {
                                opening_tag:
                                    '<a href="/?ts=' + Date.now() + '">',
                                closing_tag: "</a>",
                            }
                        ),
                        type: "error",
                        hide: false,
                    });
                });
        };

        // This isn't used for now, but it's planned to use it for Watterott
        self.engrave_markers_without_gui = function () {
            var intensity = $("#initialcalibration_intensity").val();
            var feedrate = $("#initialcalibration_feedrate").val();
            self.simpleApiCommand(
                "engrave_calibration_markers/" + intensity + "/" + feedrate,
                {},
                function (data) {
                    console.log("Success", url, data);
                },
                function (jqXHR, textStatus, errorThrown) {
                    new PNotify({
                        title: gettext("Error"),
                        text: _.sprintf(
                            gettext(
                                "Marker engraving failed: <br>%(errmsg)s<br>Error:<br/>%(code)s %(status)s - %(errorThrown)s"
                            ),
                            {
                                errmsg: jqXHR.responseText,
                                code: jqXHR.status,
                                status: textStatus,
                                errorThrown: errorThrown,
                            }
                        ),
                        type: "error",
                        hide: false,
                    });
                }
            );
        };
    }

    // view model class, parameters for constructor, container to bind to
    OCTOPRINT_VIEWMODELS.push([
        CalibrationViewModel,

        // e.g. loginStateViewModel, settingsViewModel, ...
        ["cameraSettingsViewModel", "cameraViewModel", "loginStateViewModel"],

        // e.g. #settings_plugin_mrbeam, #tab_plugin_mrbeam, ...
        [""],
    ]);
});
