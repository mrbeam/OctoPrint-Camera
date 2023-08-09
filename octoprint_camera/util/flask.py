#!/usr/bin/env python

import base64
import time

import flask
import sys

from octoprint_mrbeam.util.log import json_serialisor
from octoprint_mrbeam.util import dict_map


def file_to_b64(item):
    if isinstance(item, str):
        with open(
            item,
            "rb",
        ) as fh:
            buf = base64.b64encode(fh.read())
    else:
        buf = base64.b64encode(item.read())
    return buf.decode("utf-8")


def send_file_b64(item, **kw):
    """Return the item as a base 64 encoded binary in a flask response The item
    should either be a file path or an item which implements a 1`read()`
    function."""
    buf = file_to_b64(item)
    response = flask.make_response(buf)
    response.headers["Content-Transfer-Encoding"] = "base64"
    response.headers["Cache-Control"] = "no-cache, no-store, must-revalidate"
    return response


def send_image(image, **kw):
    """Send the image as a base 64 encoded binary with it's timestamp in a
    flask response The item should either be a file path or an item which
    implements a 1`read()` function."""
    buf = file_to_b64(image)
    response = flask.make_response(
        flask.jsonify(dict_map(json_serialisor, dict(image=buf, **kw)))
    )

    response.headers["Content-Transfer-Encoding"] = "base64"
    response.headers["Cache-Control"] = "no-cache, no-store, must-revalidate"
    return response
