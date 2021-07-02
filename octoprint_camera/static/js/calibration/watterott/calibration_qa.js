/*
 * View model for Mr Beam
 *
 * Author: Teja Philipp <teja@mr-beam.org>
 * License: AGPLv3
 */
/* global OctoPrint, OCTOPRINT_VIEWMODELS, INITIAL_CALIBRATION */

$(function () {
    //scale(1.0392920962199313) translate(-7.72302405498282 -9.731958762886599) #realy good in rectangle
    // scale(1.0452920962199313) translate(-8.72302405498282 -9.731958762886599) //good for arrow tips
    function CalibrationQAViewModel(parameters) {
        let self = this;
        window.mrbeam.viewModels["cameraQAViewModel"] = self;
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
        self.croppedImgWidth = "500";
        self.croppedImgHeight = 390;

        self.maxObjectHeight = ko.observable(38); // in mm
        self.objectheightparam = ko.observable(582)
        self.defaultMargin = ko.computed(function(){return (self.maxObjectHeight() / self.objectheightparam())});
        self.objectZ = ko.observable(0); // in mm
        self.cornerMargin = ko.computed(function(){return (self.defaultMargin() / 2)});
        self.imgHeightScale = ko.computed(function () {
            return (
                self.cornerMargin() *
                (1 - self.objectZ() / self.maxObjectHeight())
            );
        });
        self.workingAreaWidthMM = ko.observable(500);
        self.workingAreaHeightMM = ko.observable(390);
        self.imgTranslate = ko.computed(function () {
            // Used for the translate transformation of the picture on the work area
            return [-self.workingAreaWidthMM(), -self.workingAreaHeightMM()]
                .map((x) => x * self.imgHeightScale())
                .join(" ");
        });
        self.zObjectImgTransform = ko.computed(function () {
            console.log('zobjectimg trans', self.camera.imgHeightScale(), self.camera.imgTranslate(), self.workingAreaWidthMM(), self.workingAreaHeightMM(), 'imgheightscale params(',self.cornerMargin() *
                (1 - self.objectZ() / self.maxObjectHeight()), ';', self.cornerMargin(), self.objectZ(), self.maxObjectHeight(), ')', self.defaultMargin());
            return (
                "scale(" +
                (1 + 2 * self.imgHeightScale()) +
                ") translate(" +
                self.imgTranslate() +
                ")"
            );
        });

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

        self.viewBox = ko.computed(function () {
            let size = self.camera.pictureSize.both();
            return "0 0 500 390";
            // return "0 0 " + size.join(" ");
        });
        self.rectTransform = ko.computed(function () {
            // Like workArea.zObjectImgTransform(), but zooms
            // out the markers instead of the image itself
            let size = self.camera.pictureSize.both();
            let offset = size.map(
                (x) => - x * self.camera.imgHeightScale() // * size[0] / 500
            );
            let scale_ratio = (1 + 2 * self.camera.imgHeightScale())
            return (
                "scale(" +
                1 / ( size[0] / 500) * scale_ratio + 
                " " +
                1 / ( size[1] / 390) * scale_ratio + 
                ") translate(" +
                offset.join(" ") +
                ")"
            );
        });
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
