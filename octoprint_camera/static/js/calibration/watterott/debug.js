$(function () {
    var msg = [
        "MRBEAM_MODEL: " + MRBEAM_MODEL,
        "MRBEAM_HOSTNAME: " + MRBEAM_HOSTNAME,
        "MRBEAM_SERIAL: " + MRBEAM_SERIAL,
        // "MRBEAM_LASER_HEAD_SERIAL: " + MRBEAM_LASER_HEAD_SERIAL,
        // "MRBEAM_GRBL_VERSION: " + MRBEAM_GRBL_VERSION,
        // "MRBEAM_ENV_SUPPORT_MODE: " + MRBEAM_ENV_SUPPORT_MODE,
        // "BEAMOS_IMAGE: " + BEAMOS_IMAGE,
        // "MRBEAM_LANGUAGE: " + MRBEAM_LANGUAGE,
        // "BEAMOS_VERSION: " + MRBEAM_PLUGIN_VERSION,
        // "MRBEAM_SW_TIER: " + MRBEAM_SW_TIER,
        // "MRBEAM_ENV: " + MRBEAM_ENV,
    ];
    $("#settings_mrbeam_debug_state").html(msg.join("\n"));
});
