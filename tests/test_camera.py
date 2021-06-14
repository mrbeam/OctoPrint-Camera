import logging
import time
from multiprocessing import TimeoutError
from os.path import dirname, realpath, join

import cv2
import numpy as np
import pytest
import yaml
from octoprint_mrbeam.camera import lens
from octoprint_mrbeam.camera.lens import handleBoardPicture
from octoprint_mrbeam.camera.undistort import prepareImage, _getColoredMarkerPositions
from os import pardir

from octoprint_camera.lens import BOARD_ROWS, BOARD_COLS, BoardDetectorDaemon

path = dirname(realpath(__file__))
CAM_DIR = join(
    path,
    "rsc",
)
LOGGER = logging.getLogger(__name__)

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
        ("lens_calibraton_test_image.jpg", "lens_calib_bad.npz", "out_bad.jpg"),
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
            "lens_calibraton_test_image.jpg",
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
    rsc_path = join(
        path,
        "rsc",
    )
    in_img = cv2.imread(join(rsc_path, image))
    calib_file = join(rsc_path, calib_file)

    __cam = np.load(calib_file)
    res = prepareImage(
        in_img,
        join(rsc_path, "out.jpg"),
        join(rsc_path, "pic_settings.yaml"),
        cam_matrix=__cam["mtx"],
        cam_dist=__cam["dist"],
        undistorted=True,
        debug_out=True,
    )
    logging.info(res)

    out_img = cv2.imread(
        join(rsc_path, "out.jpg"),
    )

    logging.warning(np.sum(out_img == 0))

    for i, _type in enumerate([dict, dict, list, type(None), dict, dict]):
        if not isinstance(res[i], _type):
            logging.error("%s should be of type %s" % (res[i], _type))

    return (
        np.sum(out_img == 0),
        res[5]["lens_corrected"],
    )  # returns the amount of black pixels and if the image is lens_corrected


# returns if a board with the size of BOARD_ROWS and BOARD_COLS is detected in the given image 'boardimage'
def board_detection(boardimage):
    # TODO change to use handle board picture, has to work with temp images so the don't get changed
    # boardimage = join(path, "rsc", "boards", boardimage)
    # img = cv2.imread(boardimage)
    # gray = cv2.cvtColor(img, cv2.COLOR_BGR2GRAY)
    # success, found_pattern = lens.findBoard(gray, (BOARD_ROWS, BOARD_COLS))
    # return success
    # boardimage
    # logging.debug(
    return handleBoardPicture(boardimage, 1, (BOARD_ROWS, BOARD_COLS), q_out=None)
    # )


@pytest.mark.datafiles(
    join(path, "rsc", "boards", "board_detection_good_001.jpg"),
    # "board_detection_good_002.jpg",
    # "board_detection_good_003.jpg",
    # "board_detection_good_004.jpg",
    # "board_detection_good_005.jpg",
    # "board_detection_good_006.jpg",
    # "board_detection_good_007.jpg",
    # "board_detection_good_008.jpg",
)
def test_board_detection_should_find(datafiles):
    assert (
        not board_detection(
            join(str(datafiles), "board_detection_good_001.jpg")
        )  # TODO change that it works for the others as well
        is None
    ), "Board should be detected"


@pytest.mark.parametrize(
    "boardimage",
    [
        "board_detection_bad_001.jpg",  # false
        "board_detection_bad_002.jpg",  # false
        "board_detection_bad_003.jpg",  # false
        "board_detection_small_001.jpg",
        "board_detection_small_008.jpg",
    ],
)
def test_board_detection_should_not_find(boardimage):
    assert not board_detection(boardimage), "Board should not be detected"


@pytest.mark.parametrize(
    "boardimage",
    [
        "board_detection_good_001.jpg",
        "board_detection_good_002.jpg",
        "board_detection_good_003.jpg",
        "board_detection_good_004.jpg",
        "board_detection_good_005.jpg",
        "board_detection_good_006.jpg",
        "board_detection_good_007.jpg",
        "board_detection_good_008.jpg",
        # TODO 9th file
    ],
)
def inspectState(data):
    """Inspect the state each time it changes"""
    if isinstance(data, dict):
        # yaml dumps create a LOT of output
        # logging.debug(" - Calibration State Updated\n%s", yaml.dump(data))
        pass
    else:
        logging.error(
            "Data returned by state should be dict. Instead data : %s, %s",
            type(data),
            data,
        )
        assert isinstance(data, dict)


# todo input 9 images with correct board, generate lens correction file, check if file is not producing black pixels
# BOARDS = [
#     join(CAM_DIR, "boards", "board_detection_good_001.jpg"),
#     join(CAM_DIR, "boards", "board_detection_good_002.jpg"),
#     join(CAM_DIR, "boards", "board_detection_good_003.jpg"),
#     join(CAM_DIR, "boards", "board_detection_good_004.jpg"),
#     join(CAM_DIR, "boards", "board_detection_good_005.jpg"),
#     join(CAM_DIR, "boards", "board_detection_good_006.jpg"),
#     join(CAM_DIR, "boards", "board_detection_good_007.jpg"),
#     join(CAM_DIR, "boards", "board_detection_good_008.jpg"),
#     join(CAM_DIR, "boards", "board_detection_good_008_2.jpg"),  # TODO add 9th image
#     # join(CAM_DIR, "boards", "board_detection_good_008_2.jpg"),  # TODO add 9th image
#     # join(CAM_DIR, "boards", "board_detection_bad_001.jpg"),  # TODO add 9th image
# ]
images = [
    "board_detection_good_001.jpg",
    "board_detection_good_002.jpg",
    "board_detection_good_003.jpg",
    "board_detection_good_004.jpg",
    "board_detection_good_005.jpg",
    "board_detection_good_006.jpg",
    "board_detection_good_007.jpg",
    "board_detection_good_008.jpg",
    "board_detection_good_008_2.jpg",
]
BOARDS = pytest.mark.datafiles(
    join(CAM_DIR, "boards", "board_detection_good_001.jpg"),
    join(CAM_DIR, "boards", "board_detection_good_002.jpg"),
    join(CAM_DIR, "boards", "board_detection_good_003.jpg"),
    join(CAM_DIR, "boards", "board_detection_good_004.jpg"),
    join(CAM_DIR, "boards", "board_detection_good_005.jpg"),
    join(CAM_DIR, "boards", "board_detection_good_006.jpg"),
    join(CAM_DIR, "boards", "board_detection_good_007.jpg"),
    join(CAM_DIR, "boards", "board_detection_good_008.jpg"),
    join(CAM_DIR, "boards", "board_detection_good_008_2.jpg"),
)


@BOARDS
def test_lens_calibration(datafiles):
    out_file = join(CAM_DIR, "out2.npz")  # str(datafiles / "out.npz")

    # add file put in que if enough detected you can save the calibration
    print(out_file)
    LOGGER.debug("test")
    # b = BoardDetectorDaemon(
    #     out_file, runCalibrationAsap=True, stateChangeCallback=inspectState
    # )

    lens_calibration_thread = BoardDetectorDaemon(
        out_file,
        stateChangeCallback=inspectState,
        factory=True,
        runCalibrationAsap=True,
    )
    # FIXME - Right now the npz files get loaded funny
    #         and some values aren't json pickable etc...
    # lens_calibration_thread.state.rm_from_origin("factory")
    # lens_calibration_thread.load_dir(join(CAM_DIR, "boards"))
    logging.debug("sleep thread idle %s", lens_calibration_thread.idle)
    # lens_calibration_thread.start()
    # Board Detector doesn't start automatically
    assert (
        not lens_calibration_thread.is_alive()
    ), "Board Detector doesn't start automatically"
    try:
        # _images = [img for img in BOARDS]
        # logging.debug(_images)
        # for path in _images:
        #     lens_calibration_thread.add(path)
        #     logging.debug("add %s", path)
        #     logging.debug(
        #         "sleep thread idle %s boards:%s",
        #         lens_calibration_thread.idle,
        #         lens_calibration_thread.detectedBoards,
        #     )
        _images = [str(datafiles / img) for img in images]
        for path in _images:
            logging.debug("add %s", path)
            lens_calibration_thread.add(path)
        logging.debug(_images)
        assert (
            not lens_calibration_thread.is_alive()
        ), "Board Detector doesn't start when adding pictures to it"
        lens_calibration_thread.start()
        assert lens_calibration_thread.is_alive(), "Board Detector should now run"
        # assert False
        # Start detecting the chessboard in pending pictures.
        logging.debug(
            "boards detected p:%s %s",
            lens_calibration_thread,
            lens_calibration_thread.detectedBoards,
        )
        if len(lens_calibration_thread) >= 8:
            # self._event_bus.fire(MrBeamEvents.LENS_CALIB_PROCESSING_BOARDS)
            logging.debug("slace processors")
            lens_calibration_thread.scaleProcessors(4)
        while not lens_calibration_thread.idle:
            # print("sleep lens_calib_thread")
            logging.debug(
                "sleep thread %s p:%s boards:%s",
                lens_calibration_thread.idle,
                len(lens_calibration_thread),
                lens_calibration_thread.detectedBoards,
            )
            time.sleep(1)
        # assert False
        if lens_calibration_thread.detectedBoards >= lens.MIN_BOARDS_DETECTED:
            # Do not automatically run the calibration
            assert (
                lens_calibration_thread.state.lensCalibration["state"]
                == lens.STATE_PENDING
            )
            lens_calibration_thread.startCalibrationWhenIdle = True
            while (
                lens_calibration_thread.startCalibrationWhenIdle
                or not lens_calibration_thread.idle
            ):
                time.sleep(0.1)

            assert (
                lens_calibration_thread.state.lensCalibration["state"]
                == lens.STATE_SUCCESS
            )

        # Hacky - when adding the chessboard, instantly check if the state is pending
        lens_calibration_thread.add(_images[-1])
        assert (
            lens_calibration_thread.state.lensCalibration["state"] == lens.STATE_PENDING
        )
    except Exception as e:
        logging.error(e)
        lens_calibration_thread.stop()
        lens_calibration_thread.join(1.0)
        raise

    lens_calibration_thread.stop()

    try:
        lens_calibration_thread.join(1.0)
    except TimeoutError:
        logging.error("Termination of the calibration Daemon should have been sooner")
        raise
    except RuntimeError:
        logging.error(
            "Runtimeerror Termination of the calibration Daemon should have been sooner"
        )
        # raise


CAM_DIR = join(path, "rsc")
# file: path to img file     MARKER_POS:False for markers which should not be detected
MARKER_FILES = [
    {
        "file": join(CAM_DIR, "markers", "corner_detection_missing_SE.jpg"),
        "SE": False,
    },
    {
        "file": join(CAM_DIR, "markers", "corner_detection_missing_SW.jpg"),
        "SW": False,
    },
    {
        "file": join(CAM_DIR, "markers", "corner_detection_missing_NW.jpg"),
        "NW": False,
    },
    {
        "file": join(CAM_DIR, "markers", "corner_detection_missing_NE.jpg"),
        "NE": False,
    },
    {
        "file": join(CAM_DIR, "markers", "corner_detection_missing_SE_partly.jpg"),
        "SE": False,
    },
    {
        "file": join(CAM_DIR, "markers", "corner_detection_missing_SE_partly2.jpg"),
    },
]

# tests the images if all markers except the given are found
def test_marker_detection():
    for file in MARKER_FILES:

        positions = _getColoredMarkerPositions(
            cv2.imread(file["file"]),
            join(CAM_DIR, "debug/test.jpg"),
        )

        logging.info(positions)
        for key, value in positions.items():
            if key in file:
                assert value is None, "Marker found but should not be detected"
            else:
                assert not value is None, "Marker should be detected at given position"
