var mrbeam = window.mrbeam;
mrbeam.isFactoryMode = function () {
    return INITIAL_CALIBRATION === true;
};

const MARKERS = ["NW", "NE", "SE", "SW"];
const PIC_TYPES = ["plain", "corners", "lens", "both"];

$(function () {
    function CameraViewModel(parameters) {
        var self = this;
        window.mrbeam.viewModels["cameraViewModel"] = self;

        self.settings = parameters[0];
        self.loginState = parameters[1];
        self.state = parameters[2];
        // self.state = {};
        // self.state.isPrinting = false;//#TODO hardcoded for watterott
        // self.state.isPaused = false;
        // self.state.isOperational = false;
        // self.state.isLocked = ko.observable(false);

        self.workingAreaWidthMM = ko.observable(500);
        self.workingAreaHeightMM = ko.observable(390);
        self.previewImgOpacity = ko.observable(1);

        self.TAB_NAME_WORKING_AREA = "#workingarea";
        self.FALLBACK_IMAGE_URL =
            "/plugin/camera/static/img/beam-cam-static.jpg";
        self.MARKER_DESCRIPTIONS = {
            NW: gettext("Top left"),
            SW: gettext("Bottom left"),
            NE: gettext("Top right"),
            SE: gettext("Bottom right"),
        };


        // TODO : plainPicture = {data: <base 64 src>, timestamp: <timestamp>}
        self.rawUrl = ko.observable(""); 
        ///downloads/files/local/cam/debug/raw.jpg// TODO get from settings
        // TODO : bestPicture = {data: <base 64 src>, timestamp: <timestamp>}
        self.croppedUrl = ko.observable("");
        self.cornerUrl = ko.observable("");
        self.lensUrl = ko.observable("");
        self.webCamImageElem = undefined;
        self.isCamCalibrated = false;
        self.countImagesLoaded = ko.observable(0);
        self.imagesInSession = ko.observable(0);
        self.imageLoading = ko.observable(false);

        self.markersFound = {
            NW: ko.observable(),
            SW: ko.observable(),
            SE: ko.observable(),
            NE: ko.observable(),
        };
        self.allMarkersFound = ko.computed(function(){
            return self.markersFound['NW']() && self.markersFound['SW']() && self.markersFound['SE']() && self.markersFound['NE']();
        })
        self.maxObjectHeight = 38; // in mm
        self.defaultMargin = self.maxObjectHeight / 582;
        self.objectZ = ko.observable(0); // in mm
        self.cornerMargin = ko.observable(self.defaultMargin / 2);
        self.imgHeightScale = ko.computed(function () {
            return (
                self.cornerMargin() *
                (1 - self.objectZ() / self.maxObjectHeight)
            );
        });

        self.picture = ko.observable();

        self.availablePicTypes = {
            plain: ko.observable(false),
            corners: ko.observable(false),
            lens: ko.observable(false),
            both: ko.observable(false),
        };
        self.pic_timestamp = ko.observable("");
        // We only refresh the picture if the timestamp has changed from the current one.
        self.pic_timestamp.subscribe(self.refreshPicture)

        self.needsCornerCalibration = ko.computed(function () {
            return !self.availablePicTypes.corners();
        });
        self.needsLensCalibration = ko.computed(function () {
            return !self.availablePicTypes.lens();
        });
        self._reloadImageInterval = null;

        self.simpleApiCommand = function (
            command,
            data,
            successCallback,
            errorCallback,
            type
        ) {
            data = data || {};
            data.command = command;
            if (window.mrbeam.isFactoryMode()) {
                $.ajax({
                    url: "/plugin/camera/" + command,
                    type: type, // POST, GET
                    headers: {
                        Accept: "application/json; charset=utf-8",
                        "Content-Type": "application/json; charset=utf-8",
                    },
                    data: data,
                    dataType: "json",
                    success: successCallback,
                    error: errorCallback,
                });
            } else if (self.loginState.loggedIn()) {
                OctoPrint.simpleApiCommand("camera", command, data)
                    .done(successCallback)
                    .fail(errorCallback);
            } else {
                console.warn(
                    "User not logged in, cannot send command '",
                    command,
                    "' with data",
                    data
                );
            }
        };
        self.loadAvaiableCorrection = function () {
            let success_callback = function (data) {
                console.log('corrections', data.available_corrections);
                PIC_TYPES.forEach(function (m) {
                    self.availablePicTypes[m](data.available_corrections.includes(m));
                });
            };

            let error_callback = function (resp) {
                console.log("available_corrections request error", resp);
            };
            self.simpleApiCommand("available_corrections", {}, success_callback, error_callback, "GET");
        }
        self.loadPicture = function () {
            self.getImage(GET_IMG.last, GET_IMG.pic_both);
        }
        self.loadPictureRaw = function () {
            self.getImage(GET_IMG.last, GET_IMG.pic_plain);
        }
        self.getImage = function (which, pic_type) {
            if (!self.imageLoading()) {
                self.imageLoading(true);
                if (which == null)
                    which = GET_IMG.last
                if (pic_type == null)
                    pic_type = GET_IMG.pic_plain
                let success_callback = function (data) {
                    self.imageLoading(false);
                    if(data.image) {
                        let imgData = 'data:image/jpg;base64,' + data.image
                        if (pic_type == GET_IMG.pic_plain)
                            self.rawUrl(imgData);
                        else if (pic_type == GET_IMG.pic_corner)
                            self.cornerUrl(imgData);
                        else if (pic_type == GET_IMG.pic_lens)
                            self.lensUrl(imgData);
                        else
                            self.croppedUrl(imgData);
                        self.timestamp = data.timestamp;
                        if (data.positions_found) {
                            MARKERS.forEach(function (m) {
                                self.markersFound[m](data.positions_found[m]);
                            });
                        }
                    }
                };

                let error_callback = function (resp) {
                    self.imageLoading(false);
                    console.log("image request error", resp);
                };
                self.simpleApiCommand("image", {
                    which: which,
                    pic_type: pic_type
                }, success_callback, error_callback, "GET");
            } else {
                console.log('image already loading, waiting for response');
            }
        }

        self.startReloadImageLoop = function (which="last", pic_type="plain", tab="undefined") {
            self.stopReloadImageLoop();
            self._reloadImageInterval = setInterval(function(){console.log('getImage', which, pic_type, tab);self.getImage(which, pic_type);}, 3000);//reloads image every 3 seconds
        }
        self.stopReloadImageLoop = function () {
            clearInterval(self._reloadImageInterval);
        }

        // event listener callbacks //
        // Called after all view models have been bound, with the list of all view models as the single parameter.
        self.onAllBound = function () {
            self.cameraActive = ko.computed(function () {
                // TODO : get value from backend / websocket
                return true;
            });
            self.webCamImageElem = $("#beamcam_image_svg");
            self.cameraMarkerElem = $("#camera_markers");

            //TODO Maybe needed for user calibration
            // if (window.mrbeam.browser.is_safari) {
            //     // svg filters don't really work in safari: https://github.com/mrbeam/MrBeamPlugin/issues/586
            //     self.webCamImageElem.attr("filter", "");
            // }

            self.webCamImageElem.load(function () {
                self.countImagesLoaded(self.countImagesLoaded() + 1);
            });

            // trigger initial loading of the image
            self.getImage(GET_IMG.last, GET_IMG.pic_plain);
        };

        // Image resolution notification //
        self.imgResolution = ko.observable("Low");
        self.imgResolutionNoticeDisplay = ko.computed(function () {
            if (self.imgResolution() === "Low") return "inherit";
            else return "none";
        });

        self.markerState = ko.computed(function () {
            // Returns the number of markers found
            if (
                MARKERS.reduce(
                    (prev, key) =>
                        prev || self.markersFound[key]() === undefined,
                    false
                )
            )
                return undefined;
            return MARKERS.reduce(
                (prev_val, key) => prev_val + self.markersFound[key](),
                0
            );
        });

        self.showMarkerWarning = ko.computed(function () {
            if (self.markerState() === undefined) return false;
            else if (self.markerState() < 4) return true;
            else return false;
        });

        self.firstRealimageLoaded = ko.computed(function () {
            return self.countImagesLoaded() >= 2;
        });

        self.markerMissedClass = ko.computed(function () {
            var ret = "";
            MARKERS.forEach(function (m) {
                if (
                    self.markersFound[m]() !== undefined &&
                    !self.markersFound[m]()
                )
                    ret = ret + " marker" + m;
            });
            if (self.cameraMarkerElem !== undefined) {
                if (self.imagesInSession() == 0) {
                    ret = ret + " gray";
                    // Somehow the filter in css doesn't work
                    self.cameraMarkerElem.attr({
                        style: "filter: url(#grayscale_filter)",
                    });
                } else self.cameraMarkerElem.attr({style: ""});
            }
            return ret;
        });

        self.onDataUpdaterPluginMessage = function (plugin, data) {
            console.log('plugin message', plugin, data);
            if ("newImage" in data) {
                console.log('new image get');
                self.pic_timestamp(data.timestamp)
            }

            if ("beam_cam_new_image" in data) {
                const mf = data["beam_cam_new_image"]["markers_found"];
                MARKERS.forEach(function (m) {
                    self.markersFound[m](mf.includes(m));
                });

                if (data["beam_cam_new_image"]["error"] === undefined) {
                    self._needCalibration(false);
                } else if (
                    data["beam_cam_new_image"]["error"] ===
                    "Camera_calibration_is_needed"
                ) {
                    self._needCalibration(true);
                }
                if ("workspace_corner_ratio" in data["beam_cam_new_image"]) {
                    // workspace_corner_ratio should be a float
                    // describing the fraction of the img where
                    // the z=0 view starts.
                    self.cornerMargin(
                        data["beam_cam_new_image"]["workspace_corner_ratio"]
                    );
                } else {
                    self.cornerMargin(0);
                }
                // self.loadImage(self.croppedUrl());
                self.getImage(GET_IMG.last, GET_IMG.pic_plain);
            }
        };

        self._needCalibration = function (val) {
            if ((val === undefined || val) &&
                !self.needsCornerCalibration() &&
                !window.mrbeam.isFactoryMode()) {
                new PNotify({
                    title: gettext("Corner Calibration needed"),
                    text: gettext(
                        "Please calibrate the camera under Settings -> Camera -> Corner Calibration."
                    ),
                    type: "warning",
                    tag: "calibration_needed",
                    hide: false,
                });
            }
            if (val !== undefined) self.needsCornerCalibration(val);
            else self.needsCornerCalibration(true);
        };

        // self.loadImage = function (url) {
        //     self.getImage();
        //     var myImageUrl = self.getTimestampedImageUrl(url);
        //     var img = $("<img>");
        //     img.load(function () {
        //         self.timestampedCroppedImgUrl(myImageUrl);
        //         //TODO Maybe needed for user calibration
        //         // if (window.mrbeam.browser.is_safari) {
        //         //     // load() event seems not to fire in Safari.
        //         //     // So as a quick hack, let's set firstImageLoaded to true already here
        //
        //         //     self.firstImageLoaded = true;
        //         //     self.countImagesLoaded(self.countImagesLoaded() + 1);
        //         // }
        //         if (this.width > 1500 && this.height > 1000)
        //             self.imgResolution("High");
        //         else self.imgResolution("Low");
        //
        //         // respond to backend to tell we have loaded the picture
        //         if (INITIAL_CALIBRATION) {
        //             $.ajax({
        //                 type: "GET",
        //                 url: "/plugin/camera/on_camera_picture_transfer",
        //             });
        //         } else if (self.loginState.loggedIn()) {
        //             OctoPrint.simpleApiCommand(
        //                 "camera",
        //                 "on_camera_picture_transfer",
        //                 {}
        //             );
        //         } else {
        //             console.warn(
        //                 "User not logged in, cannot confirm picture download."
        //             );
        //         }
        //         self.imagesInSession(self.imagesInSession() + 1);
        //     });
        //     img.attr({src: myImageUrl});
        // };

        // self.getTimestampedImageUrl = function (url) {
        //     var result = undefined;
        //     if (url) {
        //         result = url;
        //     } else if (self.croppedUrl()) {
        //         result = self.croppedUrl();
        //     }
        //     if (result) {
        //         if (result.match(/(\?|&)ts=/))
        //             result = result.replace(
        //                 /(\?|&)ts=[0-9]+/,
        //                 "$1ts=" + new Date().getTime()
        //             );
        //         else {
        //             result += result.lastIndexOf("?") > -1 ? "&ts=" : "?ts=";
        //             result += new Date().getTime();
        //         }
        //     }
        //     return result;
        // };

        // self.send_camera_image_to_analytics = function () {
        //     if (self.loginState.loggedIn()) {
        //         OctoPrint.simpleApiCommand(
        //             "camera",
        //             "send_camera_image_to_analytics",
        //             {}
        //         );
        //     } else {
        //         console.warn(
        //             "User not logged in, cannot send image to analytics."
        //         );
        //     }
        // };
        self.imgTranslate = ko.computed(function () {
            // Used for the translate transformation of the picture on the work area
            return [-self.workingAreaWidthMM(), -self.workingAreaHeightMM()]
                .map((x) => x * self.imgHeightScale())
                .join(" ");
        });
        self.zObjectImgTransform = ko.computed(function () {
            return (
                "scale(" +
                (1 + 2 * self.imgHeightScale()) +
                ") translate(" +
                self.imgTranslate() +
                ")"
            );
        });
        self.zoomOffX = ko.observable(0);
        self.zoomOffY = ko.observable(0);
        self.zoom = ko.observable(1.0);
        self.zoomViewBox = ko.computed(function () {
            var z = self.zoom();
            var w = self.workingAreaWidthMM() * z;
            var h = self.workingAreaHeightMM() * z;
            var x = self.zoomOffX();
            var y = self.zoomOffY();
            MRBEAM_WORKINGAREA_PAN_MM = [x, y];
            return [x, y, w, h].join(" ");
        });
    }

    // view model class, parameters for constructor, container to bind to
    ADDITIONAL_VIEWMODELS.push([
        CameraViewModel,
        [
            "settingsViewModel",
            "loginStateViewModel",
            "printerStateViewModel",
        ],
        [], // nothing to bind.
    ]);
});
