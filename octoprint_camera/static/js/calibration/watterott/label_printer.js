/*
 * View model for Mr Beam
 *
 * Author: Teja Philipp <teja@mr-beam.org>
 * License: AGPLv3
 */
/* global OctoPrint, OCTOPRINT_VIEWMODELS, INITIAL_CALIBRATION */

$(function () {
    function LabelPrinterViewModel(parameters) {
        let self = this;
        window.mrbeam.viewModels["labelPrinterViewModel"] = self;
        self.calibration = parameters[0];
        self.lensCalibration = parameters[1];

        self.qaDone = ko.computed(function () {
            return (
                self.calibration.camera.availablePicTypes.corners() &&
                self.lensCalibration.lensCalibrationComplete()
            );
        });

        self.printLabel = function (labelType, event) {
            let button = $(event.target);
            let label = button.text().trim();
            button.prop("disabled", true);
            self.calibration.simpleApiCommand(
                "print_label",
                JSON.stringify({
                    command: "print_label",
                    labelType: labelType,
                    blink: true,
                }),
                function () {
                    button.prop("disabled", false);
                    new PNotify({
                        title: gettext("Printed: ") + label,
                        type: "success",
                        hide: false,
                    });
                },
                function (response) {
                    button.prop("disabled", false);
                    let data = response.responseJSON;
                    new PNotify({
                        title: gettext("Print Error") + ": " + label,
                        text: data ? data.error : "",
                        type: "error",
                        hide: false,
                    });
                },
                "POST"
            );
        };

        self.shutdown = function (d, ev) {
            successCallback = function () {
                new PNotify({
                    title: gettext("Device is turning off"),
                    text: gettext(
                        "The lights on the device will turn off in a few seconds"
                    ),
                    type: "info",
                    hide: false,
                });
            };
            failCallback = function () {
                new PNotify({
                    title: gettext("Turning off device"),
                    text: gettext("Is the device still connected?"),
                    type: "error",
                    hide: true,
                });
            };
            self.calibration.simpleApiCommand(
                "shutdown",
                {},
                successCallback,
                failCallback,
                "GET"
            );
        };
    }

    // view model class, parameters for constructor, container to bind to
    OCTOPRINT_VIEWMODELS.push([
        LabelPrinterViewModel,

        // e.g. loginStateViewModel, settingsViewModel, ...
        ["calibrationViewModel", "lensCalibrationViewModel"],

        // e.g. #settings_plugin_mrbeam, #tab_plugin_mrbeam, ...
        ["#tab_done_print_labels"],
    ]);
});
