# OctoPrint-Camera

This plugin connects and manages the Raspberri Pi camera, allowing other plugins or external processes to query for an image without having to connect directly to the camera.

This can prevent connection locks with a camera if multiple services are in need of a picture.

It uses the `picamera` package to manage the connection and configuration of the camera.

## Setup

Install via the bundled [Plugin Manager](https://github.com/foosel/OctoPrint/wiki/Plugin:-Plugin-Manager)
or manually using this URL:

    https://github.com/mrbeam/OctoPrint-Camera/archive/master.zip


## Configuration

TODO : describe the `.octoprint/config.yaml` config
NOTE : Can wait for the end of phase 2

----------------------------------
`.octoprint/cam/pic_settings.yaml`

This file holds the necessary info to perform a corner correction when the pink circles are detected.

Note: This should be migrated to the plugin settings instead of a separate `yaml` file.

```yaml
## Position of the pink circles, as found during calibration
# [User]
raw_calibMarkers:
  NE: [NEx, NEy]
  NW: [NWx, NWy]
  SE: [SEx, SEy]
  SW: [SWx, SWy]
# [Factory]
factory_raw_calibMarkers:
  NE: [NEx, NEy]
  NW: [NWx, NWy]
  SE: [SEx, SEy]
  SW: [SWx, SWy]

## Position of the corners (arrow tips), as found during the calibration 
# [User]
raw_cornersFromImage:
  NE: [NEx, NEy]
  NW: [NWx, NWy]
  SE: [SEx, SEy]
  SW: [SWx, SWy]
# [Factory]
factory_raw_cornersFromImage:
  NE: [NEx, NEy]
  NW: [NWx, NWy]
  SE: [SEx, SEy]
  SW: [SWx, SWy]

# Hostname - allows to sanity check in case of bad backup
hostname_KEY: MrBeam-DB78
# version of the OctoPrint-MrBeam plugin
version: 0.1.16 

### LEGACY ###
# Only created from legacy factory mode and older user corner calibration #

# Pink circle position on the lens corrected image
calibMarkers:
  NE: [NEx, NEy]
  NW: [NWx, NWy]
  SE: [SEx, SEy]
  SW: [SWx, SWy]
# Position of the arrow tips on the lens corrected image
cornersFromImage:
  NE: [NEx, NEy]
  NW: [NWx, NWy]
  SE: [SEx, SEy]
  SW: [SWx, SWy]

### UNUSED ### 
# Could be used - but is not because it's a bad idea

# Position of the pink circles on the lens corrected image [User]
user_undist_calibMarkers:
  NE: [NEx, NEy]
  NW: [NWx, NWy]
  SE: [SEx, SEy]
  SW: [SWx, SWy]

# Position of the arrow tips on the lens corrected image [User]
user_undist_cornersFromImage:
  NE: [NEx, NEy]
  NW: [NWx, NWy]
  SE: [SEx, SEy]
  SW: [SWx, SWy]

### DEPRECATED ###

calibration_updated: false
# Delta between cornersFromImage and calibMarkers
marker2cornerVecs:
  NE: [NEx, NEy]
  NW: [NWx, NWy]
  SE: [SEx, SEy]
  SW: [SWx, SWy]
markerSettings:
  hueMax: [...]
  hueMin: [...]
  hue_lb_min: 100
  pixels_expected: 800
  radMax: 23
  radMin: 3
  ratioH: 4
  ratioW: 4
  saturationMax: [...]
  saturationMin: [...]
  valueMax: [...]
  valueMin: [...]
blur_factor_threshold: 20
```
----------------------------------
`.octoprint/cam/last_session.yaml`

Keeps updated info between each picture taken. It is separated from the other config files to reduce the yaml parsing load.

```yaml
# Last position the pink circles were found on the plain picture
calibMarkers:
  NE: [NEx, NEy]
  NW: [NWx, NWy]
  SE: [SEx, SEy]
  SW: [SWx, SWy]
# Last used shutter speed for brightness adjustment;  
shutter_speed: 133018
# MrBeamPlugin version (makes it easier for migrations)
version: 0.9.4.0
```

----------------------------------------------
`.octoprint/cam/lens_correction_.npz`
`.octoprint/cam/lens_correction_2048x1536.npz`

Stores lens correction settings for a given resolution.

```yaml
# Lens calibration parameters (numpy.array)
tvecs: [...]
mtx: [...]
dist: [...]
rvecs: [...]
# returncode of ``cv2.calibrateCamera``
err: <int>
# descriptive state string
state: success | fail | processing
```

This file has to be read using the `numpy.load` method:
```python
>>> config = numpy.load("lens_correction_2048x1536.npz")
>>> config.keys()
['tvecs', 'mtx', 'dist', 'err', 'state', 'rvecs']
```