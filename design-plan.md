# Camera Plugin

##TODO Josef:
- binding to disable plugin (Mrbeam plugin) to test for watterot (_disabled init.py file) maybe in config.yaml
- add new classes to plugin - ui to take over ui, iobeam/iobeamhandler for button press
- make lock when save image to save for write read error
- save only processed images to sd card (.octoprint/uploads/cam/.....)
- for watterorr to calibrate, laser markings already done, just calibration steps

- restapi to get image
- call to get images as soon as new image avaiable
- Camera thread to take pictures, save and serve


## Objective

- Reduce buggy behaviour (camera not sending images, not starting etc...)
- Compartimentalise the factory/assembly tools
- Provide a separate UI for calibration of the camera (like the current factory_mode)

## Design plan

- Create a separate plugin
- Simplify the software design with a new approach

## Side benefits of the design choice

- Separation of concern
  - Un-burden the MrBeamPlugin
  - With a new design, we can make the camera plugin flexible for multiple simultaneous uses.
- As an optional plugin, the camera plugin doesn't need to be installed in local environments.
- The image input can be swapped away from the camera plugin
  E.g. an experimental video feed
- Split up the work towards py3 compatibility

## Rollout plan

The creation of the plugin can be staged in 3 phases

### 1. "MVP" - Camera calibration tool (1~2 days)

The separate plugin provides:

- A simple UI (copy pasta of the watterott assembly UI)
  - Start/stop camera button
  - _Hack_ : Will keep the buttons to print out the device labels
- A simple camera system
  - No movement detection
  - Always running (even when lid closed)
- Image distortion / processing
  - Import from the `octoprint_mrbeam.camera` package
  - Same save/load functions -> Config file Compatibility

Requirements:

- Can run without the MrBeamPlugin running
  > MrBeamPlugin blacklisted during the watterott assembly

Shortcomings:

- No possibility to laser something when the plugin is disabled
  > Not necessary when in watterott mode

### 2. Plugin compatible bahaviour (1~2 weeks)

The plugin can take on the full role of the camera

- Can run alongside the MrBeamPlugin
- MrBeamPlugin dictates when the camera plugin __can__ run
  > It does not __explicitely__ tell the camera to run, rather green lights the time when it may run
  e.g. The camera plugin can tell by itself if the user is connected
- Optimisation:
  - Movement detection
  - Only run when user is connected
- Image processing has been migrated to the camera plugin

### 3. Full separation of concerns (1 day)

Basically, we only remove the label rinting hack from the Camera Plugin

- New plugin for the watterott Assembly line should be available
  - Uses both the camera plugin and `mrb_check` to complete the device assembly
  - Requires OctoPrint/MrBeamPlugin to run??
- Migrate Label printing to the Assembly program / interface

## Technical details

Most of the communication with the camera plugin could be done with a RESTish (!=RESTful :D ) API

### REST API & I/O

Each request can yield an error message `{error: <error message>, errcode: <error code>}`

`[GET] /image`
`{which: "available"/"next", pic_type: "plain"/corners/lens/both}`

Returns the latest available image to diplay on the interface

Picture Type:
`plain` : No corrections, just the picture taken by the camera
`corners` : Adjust the image such that it corresponds to real-world coordinates (mapping the corner areas)
`lens`: Adjust the lens distortion
`both`: Do both the corners and lens corretcion

Should return err msg if the picture cannot be processed ...

`[GET] /available_corrections`

Return the list of possible images:
possible returns: `[ plain, corners, lens, both ]`

`[GET] /timestamp` or `[GET] /ts`
`{pic_type: "plain"/corners/lens/both}`

Returns the timestamp of the latest available image

`[GET] /running`

Whether the camera is running or not


> TODO Phase 2
> `[GET] /available`
> Whether the camera can run now
> For now : True all the time

TODO : Websocket communication : `/picture_available`

### OctoPrint Events

We don't want to spam the Event manager of OctoPrint,
therefore there won't be a message for every single picture taken.

`EVENT_IMAGE_READY` - A processed image is available

__payload__ :

```
{
  ts: <timestamp>,
  size: <img size>,
  path: <tmp path of the image>,
}
```

`EVENT_STARTING` - The camera is starting up


`EVENT_STOPPING` - The camera is stopping


### OctoPrint helper functions

A `HelperPlugin` can have public functions that other plugins can use to interact with.

`take_picture(path=None)`

Take a picture to the default or given path

`wait(timeout=0)`

Blocks until the camera is idle or finished taking a picture.
> Returns immediatly if the camera is idle.

`process(image, *args, **kwargs)`

Process an image with the parameters given.
Each parameter should have a default value.
After calibration, the relevant paramters should be written to a config file. (Like `.octoprint/cam/pic_settings.yaml`)

### Configuration files

As a plugin, all of the calibration values can be written into the octoprint `config.yaml` file, but it could burden the size of that config and cause performance issues.

It is best to keep the calibration configuration separate, as that one shouldn't change much over time. Therefore we can keep the current files in `.octoprint/cam/`
