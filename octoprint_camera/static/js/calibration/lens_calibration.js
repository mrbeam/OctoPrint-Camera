/*
 * View model for Mr Beam
 *
 * Author: Teja Philipp <teja@mr-beam.org>
 * License: AGPLv3
 */
/* global OctoPrint, OCTOPRINT_VIEWMODELS, INITIAL_CALIBRATION */

const MAX_BOARD_SCORE = 5;
const MIN_BOARDS_FOR_CALIBRATION = 9;

$(function () {
    function LensCalibrationViewModel(parameters) {
        let self = this;
        window.mrbeam.viewModels["lensCalibrationViewModel"] = self;
        self.calibration = parameters[0];
        self.camera = parameters[1];
        // self.analytics = parameters[2]; //TODO disabled for watterott
        // TODO Pahse 2 - Determine whether the lens calibration is active from backend 
        self.lensCalibrationActive = ko.observable(true);

        self.lensCalibrationNpzFileTs = ko.observable(null);
        self.rawPicSelection = ko.observableArray([]);
        self.images = {};
        self.updateCounter = ko.observable(0)
        /*  Apply the info to our list of images
            The imgInfo could also contain the b64 encoded images
        */
        self.images_update = function(imgInfo) {
            // imgInfo = {
            // '/home/pi/.octoprint/uploads/cam/debug/tmp_raw_img_4.jpg': {
            //      state: "processing",
            //      tm_proc: 1590151819.735044,
            //      tm_added: 1590151819.674166,
            //      board_bbox: [[767.5795288085938, 128.93748474121094],
            //                   [1302.0089111328125, 578.4738159179688]], // [xmin, ymin], [xmax, ymax]
            //      board_center: [1039.291259765625, 355.92547607421875], // cx, cy
            //      found_pattern: null,
            //      index: 2,
            //      board_size: [5, 6]
            //    }, ...
            // }
        
            for (const [path, value] of Object.entries(imgInfo)) {
                value.path = ko.observable(path);
                // Check if the image had already been saved previously
                if (self.images[path]) {
                    // only update the image if there is data
                    if (value.image){
                        if (self.images[path].image)
                            self.images[path].image(value.image);
                        else
                            self.images[path].image = ko.observable(value.image);
                    }
                    // update all other observables
                    for (const [key, val] of Object.entries(value)) {
                        if (key != "image") {
                            if (self.images[path][key] instanceof ko.observable)
                                self.images[path][key](val)
                            else
                                self.images[path][key] = ko.observable(val)
                        }
                    }
                } else {
                    self.images[path] = {}
                    // initialise our image with observables
                    for (const [key, val] of Object.entries(value)) {
                        self.images[path][key] = ko.observable(val);
                    }
                    // KO version < 3.5 hack to update the successful images
                    //   1. self.getLensCalibrationImage receives the timestamp for the image we need
                    self.images[path].timestamp.subscribe(self.getLensCalibrationImage);
                    //   2. Run self.getLensCalibrationImage when the state becomes successful
                    self.images[path].state.subscribe(function(newValue) {
                        if (newValue == "success")
                            self.images[path].timestamp.notifySubscribers();
                    })
                    // Attach a processing duration attached to each image
                    self.images[path].processing_duration = ko.computed(function() {
                        self.images[path].tm_end() !== null
                            ? (self.images[path].tm_end() - self.images[path].tm_proc()).toFixed(1) + " sec"
                            : "?";
                    });
                    // Download the image
                    self.getLensCalibrationImage(self.images[path].timestamp());
                }
                //  KO version >= 3.5 (currently 3.4)
                // // When there is a success, refresh the image
                // ko.when(function () {
                //     return self.images[path].status() == "success";
                // }, function (result) {
                //     self.getLensCalibrationImage(self.images[path].timestamp());
                // });
            }

            // TODO : Remove images that were dropped
            Object.keys(self.images).filter(x => ! Object.keys(imgInfo).includes(x))
                                    .forEach(function(path){
                delete self.images[path];
            })
            // Hack : Refresh the array of images to display
            //        The rawPicSelection does not have direct 
            //        bindings to the observables in self.images
            self.updateCounter(self.updateCounter()+1)
            // self.update_rawPicSelection();
        };

        self.update_rawPicSelection = ko.computed(function() {
            // Hack : Use the counter as a direct observable 
            //        The rawPicSelection does not have direct 
            //        bindings to the observables in self.images
            self.updateCounter()
            // inneficient:
            // 1. ko.toJS(img_arr) will make a copy of the content, 
            //    including the images  -> huge waste of ram
            let img_arr = [];
            for (const [path, value] of Object.entries(self.images)) {
                value.path = path;
                img_arr.push(value);
            }
            // Add empty slots (up to 9)
            for (let i = img_arr.length; i < 9; i++) {
                img_arr.push({
                    index: -1,
                    path: null,
                    state: "missing",
                });
            }
            // Sort the array so that the pictures don't move in the grid
            img_arr.sort(function (l, r) {
                if (l.index == r.index) return 0;
                else if (l.index == -1) return 1;
                else if (r.index == -1) return -1;
                else return l.index < r.index ? -1 : 1;
            });
            self.rawPicSelection(ko.toJS(img_arr));
        });

        self.imagesAdd = function(imagesToUpdate) {
            self.images_update(ko.toJS({...self.images, ...imagesToUpdate}))
        }

        self.cameraBusy = ko.computed(function () {
            return self
                .rawPicSelection()
                .some((elm) => elm.state === "camera_processing");
        });

        self.lensCalibrationNpzFileVerboseDate = ko.computed(function () {
            const ts = self.lensCalibrationNpzFileTs();
            if (ts !== null) {
                const d = new Date(ts);
                const verbose = d.toLocaleString("de-DE", {
                    timeZone: "Europe/Berlin",
                });
                return `Using .npz created at ${verbose}`;
            } else {
                return "No .npz file available";
            }
        });

        self.lensCalibrationComplete = ko.computed(function () {
            return "lensCalibration" in self.calibration.calibrationState()
                ? self.calibration.calibrationState().lensCalibration ===
                      "success"
                : false;
        });

        self.lensCalibrationBusy = ko.computed(function () {
            return "lensCalibration" in self.calibration.calibrationState()
                ? self.calibration.calibrationState().lensCalibration ===
                      "processing"
                : false;
        });

        self.boardsFound = ko.computed(function () {
            return self
                .rawPicSelection()
                .filter((elm) => elm.state === "success").length;
        });

        self.hasMinBoardsFound = ko.computed(function () {
            return self.boardsFound() >= MIN_BOARDS_FOR_CALIBRATION;
        });

        self.onStartupComplete = function () {
            if (window.mrbeam.isFactoryMode()) {
                self._refreshPics();
                // $("#lenscal_tab_btn").click(function () {
                //     self.startLensCalibration();
                // });
            }
        };

        self.onSettingsHidden = function () {
            if (self.lensCalibrationActive()) {
                self.abortLensCalibration();
            }
        };

        self.onDataUpdaterPluginMessage = function (plugin, data) {
            if (plugin !== "camera" || !data) return;

            if ("chessboardCalibrationState" in data) {
                let _d = data["chessboardCalibrationState"];

                self.calibration.calibrationState(_d);
                self.images_update(_d.pictures);

                if ("lensCalibrationNpzFileTs" in _d) {
                    self.lensCalibrationNpzFileTs(
                        _d.lensCalibrationNpzFileTs > 0
                            ? _d.lensCalibrationNpzFileTs * 1000
                            : null
                    );
                }

                self.updateHeatmap(_d.pictures);
            }
        };

        self.getLensCalibrationImage = function(timestamp) {
            self.calibration.simpleApiCommand(
                "get_lens_calibration_image",
                JSON.stringify({"timestamp": timestamp}),
                self.imagesAdd,
                self._getRawPicError,
                "POST"
            );
        }

        self.startLensCalibration = function () {
            // self.analytics.send_fontend_event("lens_calibration_start", {});//todo enable analytic
            self.lensCalibrationActive(true);
            self.calibration.simpleApiCommand(
                "calibration_lens_start",
                {},
                self._refreshPics,
                self._getRawPicError,
                "GET"
            );

            // $("#settingsTabs").on("click", function () {
            //     self.abortLensCalibration();
            // });
        };

        self.runLensCalibration = function () {
            self.calibration.simpleApiCommand(
                "camera_run_lens_calibration",
                {},
                function () {
                    new PNotify({
                        title: gettext("Calibration started"),
                        text: gettext(
                            "It shouldn't take long. Your device shows a green light when it is done."
                        ),
                        type: "info",
                        hide: true,
                    });
                },
                function () {
                    new PNotify({
                        title: gettext("Couldn't start the lens calibration."),
                        text: gettext(
                            "Is the machine on? Have you taken any pictures before starting the calibration?"
                        ),
                        type: "warning",
                        hide: false,
                    });
                },
                "POST"
            );
        };

        self.abortLensCalibration = function () {
            // TODO - Axel - Allow to kill the board detection.
            // self.analytics.send_fontend_event("lens_calibration_abort", {});//todo enable analytic
            self.stopLensCalibration();
            self.resetView();
        };

        self.stopLensCalibration = function () {
            self.camera.simpleApiCommand(
                "camera_stop_lens_calibration",
                {},
                function () {
                    self.resetLensCalibration();
                },
                function () {
                    // In case the users experience weird behaviour
                    new PNotify({
                        title: gettext("Couldn't stop the lens calibration."),
                        text: gettext(
                            "Please verify your connection to the device. Did you try canceling multiple times?"
                        ),
                        type: "warning",
                        hide: false,
                    });
                },
                "POST"
            );
        };

        self.onEventLensCalibExit = function () {
            // Is called by OctoPrint when this event is fired
            new PNotify({
                title: gettext("Lens Calibration stopped."),
                type: "info",
                hide: true,
            });
        };

        self.resetLensCalibration = function () {
            self.lensCalibrationActive(false);
            self.resetHeatmap();
        };

        self.saveLensCalibrationData = function () {
            // TODO Gray out button when calibration state is STATE_PROCESSING
            // self.analytics.send_fontend_event("lens_calibration_finish", {});//todo enable analytic
            self.runLensCalibration();
            self.resetView();
        };

        self.resetView = function () {
            self.camera.resetUserView();
        };

        self.saveRawPic = function () {
            self.camera.simpleApiCommand(
                "lens_calibration_capture",
                {},
                self._rawPicSuccess,
                self._saveRawPicError,
                "GET"
            );
        };

        self.delRawPic = function () {
            $("#heatmap_board" + this.index).remove(); // remove heatmap
            self.camera.simpleApiCommand(
                "lens_calibration_del_image",
                JSON.stringify({ path: this["path"] }),
                self._refreshPics,
                self._delRawPicError,
                "POST"
            );
        };

        self.restoreFactory = function () {
            // message type not defined - not implemented for Calibration tool
            self.camera.simpleApiCommand(
                "calibration_lens_restore_factory",
                {},
                function () {
                    new PNotify({
                        title: gettext("Reverted to factory settings."),
                        text: gettext(
                            "Your previous calibration has been deleted."
                        ),
                        type: "info",
                        hide: false,
                    });
                },
                function (response) {
                    new PNotify({
                        title: gettext("Failed to revert to factory settings."),
                        text: gettext(
                            "Information :\n" + response.responseText
                        ),
                        type: "warning",
                        hide: false,
                    });
                }
            );
        };

        self._refreshPics = function () {
            self.calibration.simpleApiCommand(
                "send_lens_captured_img_list",
                {},
                self._rawPicSuccess,
                self._getRawPicError,
                "GET"
            );
        };

        // HEATMAP
        self.resetHeatmap = function () {
            $("#segment_group rect").remove();
        };

        self.dehighlightHeatmap = function () {
            $("#segment_group rect").removeClass("highlight");
        };

        self.highlightHeatmap = function (data) {
            if (!data.path || data.state !== "success") return;
            let fileName = data.path.split("/").reverse()[0];
            let id = "heatmap_board" + fileName;
            // $("#"+id).addClass('highlight'); // no idea why this doesn't work anymore
            document.getElementById(id).classList.add("highlight");
        };

        self.updateHeatmap = function (picturesState) {
            let boxes = [];
            for (const [path, value] of Object.entries(picturesState)) {
                if (value.board_bbox) {
                    let fileName = path.split("/").reverse()[0];
                    const [x1, y1] = value.board_bbox[0];
                    const [x2, y2] = value.board_bbox[1];
                    boxes.push(
                        `<rect id="heatmap_board${fileName}" x="${x1}" y="${y1}" width="${
                            x2 - x1
                        }" height="${y2 - y1}" />`
                    );
                }
            }
            let heatmapGroup = $("#segment_group");
            heatmapGroup.empty();
            heatmapGroup.append(boxes);
            // required to refresh the heatmap
            $("#heatmap_container").html($("#heatmap_container").html());
        };

        // RAW PIC
        self._rawPicSuccess = function (response) {};
        self._saveRawPicError = function () {
            self._rawPicError(
                gettext("Failed to save the latest image."),
                gettext("Please check your connection to the device.")
            );
        };
        self._delRawPicError = function () {
            self._rawPicError(
                gettext("Failed to delete the latest image."),
                gettext("Please check your connection to the device.")
            );
        };
        self._getRawPicError = function () {
            self._rawPicError(
                gettext("Failed to refresh the list of images."),
                gettext("Please check your connection to the device.")
            );
        };

        self._rawPicError = function (err, msg) {
            // Shorthand - Only shows "I have no clue why" when no message was defined
            if (msg === undefined)
                msg = gettext("...and I have no clue why. Sorry.");
            new PNotify({
                title: err,
                text: msg,
                type: "warning",
                hide: true,
            });
        };

        // WATTEROTT ONLY
        self.lensCalibrationToggleQA = function () {
            $("#lensCalibrationPhases").toggleClass("qa_active");
        };
    }

    // view model class, parameters for constructor, container to bind to
    OCTOPRINT_VIEWMODELS.push([
        LensCalibrationViewModel,

        // e.g. loginStateViewModel, settingsViewModel, ...
        [
            "calibrationViewModel",
            "cameraViewModel"
            // "analyticsViewModel", #TODO in MRBEAM plugin included
        ],

        // e.g. #settings_plugin_mrbeam, #tab_plugin_mrbeam, ...
        [
            "#lens_calibration_view",
            "#tab_lens_calibration",
            "#tab_lens_calibration_wrap",
        ],
    ]);
});
