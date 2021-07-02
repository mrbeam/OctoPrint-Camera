##prepare the test
clone repository `git@github.com:mrbeam/test_rsc.git`, this contains the files needed for the test

##run the test
`pytest tests/test_camera.py` will run the camera tests
double check the path to the rsc folder in code RSC_PATH

##run one of the tests of a testfile
to run only one of the tests of a testfile you add the name with the k parameter `-k'test_lens_calibration'` 

###test_lens_calibration Testcase
in order to run the test on a Mac you have to enable the multiprocessing for the terminal
this can be done by a ENV var `OBJC_DISABLE_INITIALIZE_FORK_SAFETY=YES`

###debug a test
to enable the logs while running the test you can add `--log-cli-level=DEBUG`