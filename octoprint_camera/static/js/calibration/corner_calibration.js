/*
 * View model for Mr Beam
 *
 * Author: Teja Philipp <teja@mr-beam.org>
 * License: AGPLv3
 */
/* global OctoPrint, OCTOPRINT_VIEWMODELS, INITIAL_CALIBRATION */

const DEFAULT_IMG_RES = [500, 390];
const CROPPED_IMG_RES = [500, 390];
const LOADING_IMG_RES = [512, 384];

$(function () {
    function CornerCalibrationViewModel(parameters) {
        let self = this;
        window.mrbeam.viewModels["cornerCalibrationViewModel"] = self;
        self.calibration = parameters[0];
        // self.workingArea = parameters[1];//TODO in MRBEAM plugin included
        // self.conversion = parameters[2]; //TODO in MRBEAM plugin included
        self.camera = parameters[1];
        // self.analytics = parameters[4]; //TODO disabled for watterott//todo enable analytic
        self.tabActive = ko.computed(function () {
            return (
                self.calibration.activeTab() === self.calibration.TABS.corner
            );
        });
        self.interval = null;
        self.cornerCalibrationActive = ko.observable(false);
        self.currentResults = ko.observable({});

        self.focusX = ko.observable(0);
        self.focusY = ko.observable(0);

        self.markersFoundPosition = ko.observable({});
        self.markersFoundPositionCopy = null;
        self.dbNWImgUrl = ko.observable("");
        self.dbNEImgUrl = ko.observable("");
        self.dbSWImgUrl = ko.observable("");
        self.dbSEImgUrl = ko.observable("");
        // Shadow calibration image shown to the user,
        // allows to keep showing this image during the calibration
        self._cornerCalImgUrl = ko.observable();

        // self.picType = ko.observable(""); // raw, lens_corrected, cropped
        self.correctedMarkersVisibility = ko.observable("hidden");
        self.croppedMarkersVisibility = ko.observable("hidden");

        self.currentMarker = 0;

        self.crossSize = ko.observable(50);

        self.calImgSize = ko.computed(function () {
            if (self._cornerCalImgUrl()) {
                let img = new Image();
                img.onload = function () {
                    self.calImgWidth(img.width);
                    self.calImgHeight(img.height);
                };
                img.src = self._cornerCalImgUrl();
            }
        });
        self.calImgWidth = ko.observable(DEFAULT_IMG_RES[0]);
        self.calImgHeight = ko.observable(DEFAULT_IMG_RES[1]);
        self.calSvgOffX = ko.observable(0);
        self.calSvgOffY = ko.observable(0);
        self.calSvgDx = ko.observable(0);
        self.calSvgDy = ko.observable(0);
        self.calSvgScale = ko.observable(1);

        self.calibrationMarkers = ko.computed(function () {
            return [
                { name: "start", desc: "click to start", focus: [0, 0, 1] },
                {
                    name: "NW",
                    desc: self.camera.MARKER_DESCRIPTIONS["NW"],
                    focus: [0, 0, 4],
                },
                {
                    name: "SW",
                    desc: self.camera.MARKER_DESCRIPTIONS["SW"],
                    focus: [0, self.calImgHeight(), 4],
                },
                {
                    name: "SE",
                    desc: self.camera.MARKER_DESCRIPTIONS["SE"],
                    focus: [self.calImgWidth(), self.calImgHeight(), 4],
                },
                {
                    name: "NE",
                    desc: self.camera.MARKER_DESCRIPTIONS["NE"],
                    focus: [self.calImgWidth(), 0, 4],
                },
            ];
        });

        self.calSvgViewBox = ko.computed(function () {
            var zoom = self.calSvgScale();
            var w = self.calImgWidth() / zoom;
            var h = self.calImgHeight() / zoom;
            var offX =
                Math.min(
                    Math.max(self.focusX() - w / zoom, 0),
                    self.calImgWidth() - w
                ) + self.calSvgDx();
            var offY =
                Math.min(
                    Math.max(self.focusY() - h / zoom, 0),
                    self.calImgHeight() - h
                ) + self.calSvgDy();
            self.calSvgOffX(offX);
            self.calSvgOffY(offY);
            return [self.calSvgOffX(), self.calSvgOffY(), w, h].join(" ");
        });

        self.calImgReady = ko.computed(function () {
            if (Object.keys(self.camera.markersFound).length !== 4)
                return false;
            return true;
        });

        // self.applySetting = function (picType, applyCrossVisibility) {
        //     // TODO with a dictionary
        //     let settings = [
        //         ["corners", CROPPED_IMG_RES, "hidden", "visible"],
        //         ["both", CROPPED_IMG_RES, "hidden", "visible"],
        //         ["lens", DEFAULT_IMG_RES, "hidden", "hidden"],
        //         ["plain", DEFAULT_IMG_RES, "visible", "hidden"],
        //         ["default", LOADING_IMG_RES, "hidden", "hidden"],
        //     ];
        //     for (let _t of settings)
        //         if (_t[0] === picType) {
        //             self.calImgWidth(_t[1][0]);
        //             self.calImgHeight(_t[1][1]);
        //             if (applyCrossVisibility) {
        //                 self.correctedMarkersVisibility(_t[2]);
        //                 self.croppedMarkersVisibility(_t[3]);
        //             }
        //             return;
        //         }
        //     new PNotify({
        //         title: gettext("Error"),
        //         text: "Something went wrong (applySettings)",
        //         type: "error",
        //         hide: true,
        //     });
        // };

        self._getImgUrl = function (type, applyCrossVisibility) {
            self.camera.getImage("next", type);
            return self.camera.rawUrl();
            if (type !== undefined) {
                self.applySetting(type, applyCrossVisibility);
                if (type === "default") return self.staticURL;
                else return self.camera.availablePicTypes[type]();
            }
            for (let _t of GET_IMG.pic_types)
                if (_t === "default" || self.camera.availablePicTypes[_t]()) {
                    self.applySetting(_t, applyCrossVisibility);
                    if (_t === "default") return self.staticURL;
                    else return self.camera.availablePicTypes[_t]();
                }
            self.applySetting("default");
            return self.staticURL; // precaution
        };

        self.cornerCalImgUrl = ko.computed(function () {
            if (!self.cornerCalibrationActive()) {
                if (self.camera.availablePicTypes.corners()) {
                    self._cornerCalImgUrl(self.camera.cornerUrl());
                    self.correctedMarkersVisibility("hidden");
                    self.croppedMarkersVisibility("visible");
                } else {
                    self._cornerCalImgUrl(self.camera.rawUrl());
                    self.correctedMarkersVisibility("visible");
                    self.croppedMarkersVisibility("hidden");
                }
            }
            return self._cornerCalImgUrl();
        });

        self.cornerCalibrationActive.subscribe(function (isActive) {
            // Change the plain picture when the calibration is started,
            // Only triggers once per state change.
            if (isActive) {
                self._cornerCalImgUrl(self.camera.rawUrl());
                self.correctedMarkersVisibility("visible");
                self.croppedMarkersVisibility("hidden");
            }
        });

        self.cornerCalibrationComplete = ko.computed(function () {
            if (Object.keys(self.currentResults()).length !== 4) return false;
            return Object.values(self.currentResults()).reduce(
                (x, y) => x && y
            );
        });

        self.zMarkersTransform = ko.computed(function () {
            // Like workArea.zObjectImgTransform(), but zooms
            // out the markers instead of the image itself
            let offset = [self.calImgWidth(), self.calImgHeight()].map(
                (x) => x * self.camera.imgHeightScale()
            );
            return (
                "scale(" +
                1 / (1 + 2 * self.camera.imgHeightScale()) +
                ") translate(" +
                offset.join(" ") +
                ")"
            );
        });

        self.svgCross = ko.computed(function () {
            let s = self.crossSize();
            return `M0,${s} h${2 * s} M${s},0 v${2 * s} z`;
        });

        self.onStartupComplete = function () {
            self.tabActive.subscribe(function (active) {
                if (active) {
                    self._startReloadImageLoop();
                } else {
                    self._stopReloadImageLoop();
                }
            });
            self._reloadImageLoop();
        };

        self._reloadImageLoop = function () {
            // Make sure that the latest plain and/or corner corrected pictures
            // are available to display.
            if (!self.cornerCalibrationActive()) {
                self.camera.loadAvaiableCorrection();
                if (self.camera.availablePicTypes.corners()) {
                    self.camera.getImage(GET_IMG.last, GET_IMG.pic_corner);
                } else {
                    self.camera.getImage(GET_IMG.last, GET_IMG.pic_plain);
                }
                self.dbNWImgUrl(
                    "/plugin/camera/image/NW.jpg" +
                        "?ts=" +
                        new Date().getTime()
                );
                self.dbNEImgUrl(
                    "/plugin/camera/image/NE.jpg" +
                        "?ts=" +
                        new Date().getTime()
                );
                self.dbSWImgUrl(
                    "/plugin/camera/image/SW.jpg" +
                        "?ts=" +
                        new Date().getTime()
                );
                self.dbSEImgUrl(
                    "/plugin/camera/image/SE.jpg" +
                        "?ts=" +
                        new Date().getTime()
                );
            }
        };
        self._startReloadImageLoop = function () {
            self.interval = setInterval(self._reloadImageLoop, 3000); //reloads image every 3 seconds
        };
        self._stopReloadImageLoop = function () {
            clearInterval(self.interval);
        };

        self.onSettingsHidden = function () {
            if (self.cornerCalibrationActive()) {
                self.abortCornerCalibration();
            }
        };

        self.onDataUpdaterPluginMessage = function (plugin, data) {
            console.log(plugin, data);
            if (plugin !== "camera" || !data) return;

            if (!self.calibration.calibrationScreenShown()) {
                return;
            }
            if ("newImage" in data) {
                self._reloadImageLoop();
                // Trigger reload if calibration not started
            }
        };

        self.startCornerCalibration = function () {
            // self.analytics.send_fontend_event("corner_calibration_start", {});//todo enable analytic
            self.cornerCalibrationActive(true);
            self._stopReloadImageLoop();
            // self.markersFoundPositionCopy = self.markersFoundPosition();
            let markers = {};
            MARKERS.forEach(function (m) {
                if (self.camera.markersFound[m]() == null) {
                    console.log(
                        "Not all Markers found, are the pink circles obstructed?"
                    );
                }
                markers[m] = self.camera.markersFound[m]()["pos"];
            });
            self.markersFoundPositionCopy = markers;
            self.nextMarker();
            self.correctedMarkersVisibility(true);
        };

        self.loadNewPicture = function () {
            self._reloadImageLoop();
        };

        self.abortCornerCalibration = function () {
            // self.analytics.send_fontend_event("corner_calibration_abort", {});//todo enable analytic
            self.stopCornerCalibration();
            self.resetView();
        };

        self.stopCornerCalibration = function () {
            self.cornerCalibrationActive(false);
        };

        self.saveCornerCalibrationData = function () {
            let data = {
                new_markers: self.markersFoundPositionCopy,
                new_corners: self.currentResults(),
            };
            self.calibration.simpleApiCommand(
                "save_corner_calibration",
                JSON.stringify(data),
                self._saveMarkersSuccess,
                self._saveMarkersError,
                "POST"
            );
            self.camera.loadAvaiableCorrection();
            self.resetView();
        };

        self.resetView = function () {
            self.focusX(0);
            self.focusY(0);
            self.calSvgScale(1);
            self.currentMarker = 0;

            self.calibration.resetUserView();
            self._startReloadImageLoop();
        };

        self._saveMarkersError = function () {
            self.cornerCalibrationActive(false);
            new PNotify({
                title: gettext("Couldn't send calibration data."),
                text: gettext("Please check your connection to the device."),
                type: "warning",
                hide: false,
            });

            self.resetView();
        };

        self._saveMarkersSuccess = function (response) {
            self.cornerCalibrationActive(false);
            // self.analytics.send_fontend_event("corner_calibration_finish", {});//todo enable analytic
            new PNotify({
                title: gettext("Camera Calibrated."),
                text: gettext("Camera calibration was successful."),
                type: "success",
                hide: true,
            });
            self.resetView();
        };

        self.engraveMarkers = function () {
            let success_callback = function (data) {
                let fileObj = {
                    date: Math.floor(Date.now() / 1000),
                    name: "CalibrationMarkers.svg",
                    origin: "local",
                    path: "CalibrationMarkers.svg",
                    refs: {
                        download:
                            "/downloads/files/local/CalibrationMarkers.svg",
                        resource: "/api/files/local/CalibrationMarkers.svg",
                    },
                    size: 594,
                    type: "model",
                    typePath: ["model", "svg"],
                };
                //clear workingArea from previous designs
                self.workingArea.clear();
                // put it on the working area
                self.workingArea.placeSVG(fileObj, function () {
                    // start conversion
                    self.conversion.show_conversion_dialog();
                });
            };
            let error_callback = function (jqXHR, textStatus, errorThrown) {
                new PNotify({
                    title: gettext("Error"),
                    text: _.sprintf(
                        gettext(
                            "Calibration failed.<br><br>Error:<br/>%(code)s %(status)s - %(errorThrown)s"
                        ),
                        {
                            code: jqXHR.status,
                            status: textStatus,
                            errorThrown: errorThrown,
                        }
                    ),
                    type: "error",
                    hide: false,
                });
            };

            self.calibration.simpleApiCommand(
                "generate_calibration_markers_svg",
                {},
                success_callback,
                error_callback,
                "GET"
            );
        };

        // MARKER NAVIGATION
        self.goToMarker = function (markerNum) {
            self.currentMarker = markerNum;
            self._highlightStep(self.calibrationMarkers()[markerNum]);
        };

        self.previousMarker = function () {
            let i = self.currentMarker - 1;
            if (!self.cornerCalibrationComplete() && i === 0) i = -1;
            if (i < 0) i = self.calibrationMarkers().length - 1;
            self.goToMarker(i);
        };

        self.nextMarker = function () {
            self.currentMarker =
                (self.currentMarker + 1) % self.calibrationMarkers().length;
            if (!self.cornerCalibrationComplete() && self.currentMarker === 0)
                self.currentMarker = 1;
            self.goToMarker(self.currentMarker);
        };

        self._highlightStep = function (step) {
            $(".cal-row").removeClass("active");
            $("#" + step.name).addClass("active");
            self.focusX(step.focus[0]);
            self.focusY(step.focus[1]);
            self.calSvgScale(step.focus[2]);
        };

        self._formatPoint = function (p) {
            if (typeof p === "undefined") return "?,?";
            else return p[0] + "," + p[1];
        };

        // USER CLICKS
        self.userClick = function (vm, ev) {
            // check if picture is loaded
            if (window.location.href.indexOf("localhost") === -1)
                if (self.cornerCalImgUrl() === STATIC_URL) {
                    console.log("Please wait until camera image is loaded...");
                    return;
                }

            // save current stepResult
            var step = self.calibrationMarkers()[self.currentMarker];
            if (self.currentMarker > 0) {
                var cPos = self._getClickPos(ev);
                var x = Math.round(cPos.xImg);
                var y = Math.round(cPos.yImg);
                var tmp = self.currentResults();
                tmp[step.name] = [x, y];
                self.currentResults(tmp);
                $("#click_" + step.name).attr({
                    x: x - self.crossSize(),
                    y: y - self.crossSize(),
                });
                // self.nextMarker()
            }
        };

        self._getClickPos = function (ev) {
            const bbox =
                ev.target.parentElement.parentElement.getBoundingClientRect();
            var clickpos = {
                xScreenPx: ev.clientX - bbox.left,
                yScreenPx: ev.clientY - bbox.top,
            };
            clickpos.xRel = clickpos.xScreenPx / bbox.width;
            clickpos.yRel = clickpos.yScreenPx / bbox.height;
            clickpos.xImg =
                self.calSvgOffX() +
                clickpos.xRel * (self.calImgWidth() / self.calSvgScale());
            clickpos.yImg =
                self.calSvgOffY() +
                clickpos.yRel * (self.calImgHeight() / self.calSvgScale());

            return clickpos;
        };
    }

    // view model class, parameters for constructor, container to bind to
    OCTOPRINT_VIEWMODELS.push([
        CornerCalibrationViewModel,

        // e.g. loginStateViewModel, settingsViewModel, ...
        [
            "calibrationViewModel",
            // "workingAreaViewModel", ##TODO in MRBEAM plugin included
            // "vectorConversionViewModel",#TODO in MRBEAM plugin included
            "cameraViewModel",
            // "analyticsViewModel",#TODO in MRBEAM plugin included//todo enable analytic
        ],

        // e.g. #settings_plugin_mrbeam, #tab_plugin_mrbeam, ...
        [
            "#corner_calibration_view",
            "#tab_corner_calibration",
            "#tab_corner_calibration_wrap",
        ],
    ]);
});
