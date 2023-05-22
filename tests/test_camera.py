import logging
import time
from multiprocessing import TimeoutError
from os.path import dirname, realpath, join
import cv2
import numpy as np
import pytest

from octoprint_mrbeam import mrb_logger
from octoprint_mrbeam.camera import lens
from octoprint_mrbeam.camera.lens import handleBoardPicture
from octoprint_mrbeam.camera.undistort import prepareImage, _getColoredMarkerPositions

from octoprint_mrbeam.util.img import differed_imwrite

from octoprint_camera.lens import BOARD_ROWS, BOARD_COLS, BoardDetectorDaemon

PROJECTPATH = dirname(realpath(__file__))
RSC_PATH = join(PROJECTPATH, "test_rsc", "camera_plugin")
LOGGER = logging.getLogger(__name__)
_logger = mrb_logger("octoprint.plugins.camera.test")


def inspectState(data):
    """Inspect the state each time it changes"""
    if isinstance(data, dict):
        # yaml dumps create a LOT of output
        # _logger.debug(" - Calibration State Updated\n%s", yaml.dump(data))
        pass
    else:
        _logger.error(
            "Data returned by state should be dict. Instead data : %s, %s",
            type(data),
            data,
        )
        assert isinstance(data, dict)


def mse(imageA, imageB):
    # the 'Mean Squared Error' between the two images is the
    # sum of the squared difference between the two images;
    # NOTE: the two images must have the same dimension
    err = np.sum((imageA.astype("float") - imageB.astype("float")) ** 2)
    err /= float(imageA.shape[0] * imageA.shape[1])

    # return the MSE, the lower the error, the more "similar"
    # the two images are
    return err


BOARDS = pytest.mark.datafiles(
    join(RSC_PATH, "boards", "board_detection_good_001.jpg"),
    join(RSC_PATH, "boards", "board_detection_good_002.jpg"),
    join(RSC_PATH, "boards", "board_detection_good_003.jpg"),
    join(RSC_PATH, "boards", "board_detection_good_004.jpg"),
    join(RSC_PATH, "boards", "board_detection_good_005.jpg"),
    join(RSC_PATH, "boards", "board_detection_good_006.jpg"),
    join(RSC_PATH, "boards", "board_detection_good_007.jpg"),
    join(RSC_PATH, "boards", "board_detection_good_008.jpg"),
    join(RSC_PATH, "boards", "board_detection_good_008_2.jpg"),
)


@BOARDS
def test_lens_calibration(datafiles):
    calibration_file = "test_lens_calibration_correction.npz"
    test_lens_calibration_calibrated_image_path = join(
        RSC_PATH, "test_lens_calibration_calibrated_image.jpg"
    )
    test_lens_calibration_image_path = join(RSC_PATH, "test_lens_calibration_image.jpg")
    output_calibrated_image_path = str(datafiles / "output_calibrated_image.jpg")

    out_file = str(datafiles / calibration_file)
    b = BoardDetectorDaemon(
        out_file,
        runCalibrationAsap=False,
        stateChangeCallback=inspectState,
        debugPath=join(PROJECTPATH, "debug"),
    )

    try:
        b.start()
        logging.debug("files %s", datafiles.listdir())
        for path in datafiles.listdir():
            b.add(str(path))
            logging.debug("path %s", path)
            if len(b) >= lens.MIN_BOARDS_DETECTED:
                b.scaleProcessors(4)

        # Start detecting the chessboard in pending pictures.
        assert b.state.lensCalibration["state"] == lens.STATE_PENDING

        while not b.idle:  # wait while processing the boarddetection
            time.sleep(0.1)
            # logging.debug(
            #     "idle state %s proc %s pending %s",
            #     b.state.lensCalibration["state"],
            #     len(b.runningProcs),
            #     b.state.getPending(),
            # )
            # assert (
            #     len(b.runningProcs) > 1
            # ), "Something went wrong there should be a running process"

        if (
            b.detectedBoards >= lens.MIN_BOARDS_DETECTED
        ):  # continue with generation of the calibrationfile if all 9 boards are detected
            b.startCalibrationWhenIdle = True  # Do manually run the calibration
            while (
                b.state.lensCalibration["state"] != lens.STATE_SUCCESS
            ):  # wait till the calibration finishes
                time.sleep(0.1)

            # generate calibratet image
            settings_lens_test = np.load(out_file)
            test_lens_calibration_image = cv2.imread(test_lens_calibration_image_path)

            test_lens_calibration_calibrated_image = cv2.imread(
                test_lens_calibration_calibrated_image_path
            )
            img_test, _ = lens.undistort(
                test_lens_calibration_image,
                settings_lens_test["mtx"],
                settings_lens_test["dist"],
            )
            differed_imwrite(output_calibrated_image_path, img_test)
            output_calibrated_image = cv2.imread(output_calibrated_image_path)

            # generate a image to show difference
            difference = cv2.subtract(
                output_calibrated_image,
                test_lens_calibration_calibrated_image,
            )
            differed_imwrite(str(datafiles / "difference.jpg"), difference)

            # calculate the diffenrence between images
            m = mse(
                output_calibrated_image,
                test_lens_calibration_calibrated_image,
            )
            assert m * 1000 <= 1  # should be smaller as 0.001

    except Exception as e:
        logging.error(e)
        b.stop()
        b.join(1.0)
        raise

    b.stop()

    try:
        b.join(1.0)
    except TimeoutError:
        logging.error("Termination of the calibration Daemon should have been sooner")
        raise


# TODO take image with dummy camera or picamera if run on device
# def test_capture():
#     plugin = CameraPlugin()
#     path = dirname(realpath(__file__))
#     settings = join(path, "tests", "rsc", "pic_settings.yaml")
#     # plugin.on_after_startup()
#     # plugin.get_picture()
#     # octoprint_camera.get_picture()
#     camera_thread = CameraThread(settings, debug=True)
#     camera_thread._camera_run()
#     # camera_thread.get_next_img()


@pytest.mark.parametrize(
    "image, calib_file, out_compare",
    [
        ("test_lens_calibration_image.jpg", "lens_calib_bad.npz", "out_bad.jpg"),
    ],
)
def test_undistorted_bad(image, calib_file, out_compare):
    blackpixels, lens_corrected = undistort_image_with_calibfile(
        image, calib_file, out_compare
    )
    assert blackpixels > 100, "to feew black pixels it should be a bad warped image"
    assert lens_corrected, "lens_correction"


@pytest.mark.parametrize(
    "image, calib_file, out_compare",
    [
        (
            "test_lens_calibration_image.jpg",
            "lens_correction_2048x1536.npz",
            "out_good.jpg",
        ),
    ],
)
def test_undistorted_good(image, calib_file, out_compare):
    blackpixels, lens_corrected = undistort_image_with_calibfile(
        image, calib_file, out_compare
    )
    assert blackpixels < 100, "to many black pixels it seems to be warped bad"
    assert lens_corrected, "lens_correction"


# https://realpython.com/pytest-python-testing/
# returns the amount of black pixels in a image and if it is lens_corrected of the given 'image' with the calibration file 'calib_file'
# todo compare out_compare with calibrated image
def undistort_image_with_calibfile(image, calib_file, out_compare):
    in_img = cv2.imread(join(RSC_PATH, image))
    calib_file = join(RSC_PATH, calib_file)

    __cam = np.load(calib_file)
    res = prepareImage(
        in_img,
        join(RSC_PATH, "out.jpg"),
        join(RSC_PATH, "pic_settings.yaml"),
        cam_matrix=__cam["mtx"],
        cam_dist=__cam["dist"],
        undistorted=True,
        debug_out=True,
    )
    _logger.info(res)

    out_img = cv2.imread(
        join(RSC_PATH, "out.jpg"),
    )

    _logger.warning(np.sum(out_img == 0))

    for i, _type in enumerate([dict, dict, list, type(None), dict, dict]):
        if not isinstance(res[i], _type):
            _logger.error("%s should be of type %s" % (res[i], _type))

    return (
        np.sum(out_img == 0),
        res[5]["lens_corrected"],
    )  # returns the amount of black pixels and if the image is lens_corrected


# file: path to img file     MARKER_POS:False for markers which should not be detected
MARKER_FILES = [
    {
        "file": join(RSC_PATH, "markers", "corner_detection_missing_SE.jpg"),
        "SE": False,
    },
    {
        "file": join(RSC_PATH, "markers", "corner_detection_missing_SW.jpg"),
        "SW": False,
    },
    {
        "file": join(RSC_PATH, "markers", "corner_detection_missing_NW.jpg"),
        "NW": False,
    },
    {
        "file": join(RSC_PATH, "markers", "corner_detection_missing_NE.jpg"),
        "NE": False,
    },
    {
        "file": join(RSC_PATH, "markers", "corner_detection_missing_SE_partly.jpg"),
        "SE": False,
    },
    {
        "file": join(RSC_PATH, "markers", "corner_detection_missing_SE_partly2.jpg"),
    },
]

# tests the images if all markers except the given are found
def test_marker_detection():
    for file in MARKER_FILES:

        positions = _getColoredMarkerPositions(
            cv2.imread(file["file"]),
            join(RSC_PATH, "debug/test.jpg"),
        )

        _logger.info(positions)
        for key, value in list(positions.items()):
            if key in file:
                assert value is None, "Marker found but should not be detected"
            else:
                assert not value is None, "Marker should be detected at given position"


# returns if a board with the size of BOARD_ROWS and BOARD_COLS is detected in the given image 'boardimage'
def board_detection(boardimage):
    return handleBoardPicture(boardimage, 1, (BOARD_ROWS, BOARD_COLS), q_out=None)


@pytest.mark.datafiles(
    join(RSC_PATH, "boards", "board_detection_good_001.jpg"),
    join(RSC_PATH, "boards", "board_detection_good_002.jpg"),
    join(RSC_PATH, "boards", "board_detection_good_003.jpg"),
    join(RSC_PATH, "boards", "board_detection_good_004.jpg"),
    join(RSC_PATH, "boards", "board_detection_good_005.jpg"),
    join(RSC_PATH, "boards", "board_detection_good_006.jpg"),
    join(RSC_PATH, "boards", "board_detection_good_007.jpg"),
    join(RSC_PATH, "boards", "board_detection_good_008.jpg"),
)
@pytest.mark.skip(
    "skipping board detection positiv case, will be done in test_lens_calibration"
)
def test_board_detection_should_find(datafiles):
    assert (
        not board_detection(join(str(datafiles), "board_detection_good_001.jpg"))
        is None
    ), "Board should be detected"


@pytest.mark.parametrize(
    "boardimage",
    [
        # join(CAM_DIR, "boards", "board_detection_bad_001.jpg"),  # skip it takes to long
        # join(CAM_DIR, "boards", "board_detection_bad_002.jpg"),  # skip it takes to long
        # join(CAM_DIR, "boards", "board_detection_bad_003.jpg"),  # skip it takes to long
        # join(CAM_DIR, "boards", "board_detection_small_001.jpg"), #skip it takes to long
        join(RSC_PATH, "boards", "board_detection_small_008.jpg"),
    ],
)
# @pytest.mark.skip("skip, it takes to long")
def test_board_detection_should_not_find(boardimage):
    assert not board_detection(boardimage), "Board should not be detected"
