/*
 * View model for Mr Beam
 *
 * Author: Teja Philipp <teja@mr-beam.org>
 * License: AGPLv3
 */
/* global OctoPrint, OCTOPRINT_VIEWMODELS, INITIAL_CALIBRATION */

$(function () {
    function CalibrationQAViewModel(parameters) {
        let self = this;
        window.mrbeam.viewModels["cameraAlignmentViewModel"] = self;
        self.calibration = parameters[0];
        self.camera = parameters[1];
        self.cornerCalibration = parameters[2];//size 500 390
        self.camera.loadPicture();
        self.tabActive = ko.computed(function () {
            return self.calibration.activeTab() === self.calibration.TABS.quality;
        });
        self.qa_image_loaded = ko.observable(false);
        self.camera.croppedUrl.subscribe(function (newValue) {
            if (newValue) {
                self.qa_image_loaded(true);
            } else {
                self.qa_image_loaded(false);
            }
        });
        self.croppedImgWidth = 500;
        self.croppedImgHeight = 390;

        self.onStartupComplete = function () {
            // self._reloadImageLoop();
            self.tabActive.subscribe(function (active) {
                if (active) {
                    console.log('qa tab get image');
                    self.camera.startReloadImageLoop("last", "both", "qa");
                } else {
                    self.camera.stopReloadImageLoop();
                }
            });
        };
    }

    // view model class, parameters for constructor, container to bind to
    OCTOPRINT_VIEWMODELS.push([
        CalibrationQAViewModel,

        // e.g. loginStateViewModel, settingsViewModel, ...
        [
            "calibrationViewModel",
            "cameraViewModel",
            "cornerCalibrationViewModel",
        ],

        // e.g. #settings_plugin_mrbeam, #tab_plugin_mrbeam, ...
        ["#tab_calibration_qa"],
    ]);
});
