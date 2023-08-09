$(function () {
    var calibrationModeMessage = null;

    function CalibrationmodeMessageViewModel(parameters) {
        var self = this;
        self.onStartup = function () {
            showDialog("#calibrationModeModal", function (dialog) {
                calibrationModeMessage.modal("hide");
            });
        };
    }

    OCTOPRINT_VIEWMODELS.push([
        CalibrationmodeMessageViewModel,

        // e.g. loginStateViewModel, settingsViewModel, ...
        [],

        // e.g. #settings_plugin_mrbeam, #tab_plugin_mrbeam, ...
        [],
    ]);

    function showDialog(dialogId, confirmFunction) {
        if (calibrationModeMessage != null) {
            return;
        }
        calibrationModeMessage = $(dialogId);
        if (calibrationModeMessage) {
            var cancelButton = $("button.btn-confirm", calibrationModeMessage);

            cancelButton.unbind("click");
            cancelButton.bind("click", function () {
                confirmFunction(calibrationModeMessage);
            });

            calibrationModeMessage
                .modal({
                    //minHeight: function() { return Math.max($.fn.modal.defaults.maxHeight() - 80, 250); }
                    keyboard: false,
                    clickClose: false,
                    showClose: false,
                    backdrop: "static",
                })
                .css({
                    width: "auto",
                    "margin-left": function () {
                        return -($(this).width() / 2);
                    },
                });
        }
    }
});
