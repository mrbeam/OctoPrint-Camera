#!/usr/bin/env python
from __future__ import absolute_import, print_function, unicode_literals, division
import base64
import time

import flask
import sys
PY3 = sys.version_info >= (3,)
_basestring = str if PY3 else basestring

def send_file_b64(item, **kw):
    """
    Return the item as a base 64 encoded binary in a flask response
    The item should either be a file path or an item which implements
    a 1`read()` function
    """
    if isinstance(item, _basestring):
        with open(item, "rb",) as fh:
            buf = base64.b64encode(fh.read())
    else:
        buf = base64.b64encode(item.read())
    response = flask.make_response(buf)
    response.headers["Content-Transfer-Encoding"] = "base64"
    response.headers["Cache-Control"] = "no-cache, no-store, must-revalidate"
    return response

def send_image(image, **kw):
    """
    Send the image as a base 64 encoded binary with it's timestamp in a flask response
    The item should either be a file path or an item which implements
    a 1`read()` function
    """
    if isinstance(image, _basestring):
        with open(image, "rb",) as fh:
            buf = base64.b64encode(fh.read())
    else:
        buf = base64.b64encode(image.read())
    response = flask.make_response(flask.jsonify(dict(
        image=buf,
        **kw,
    )))

    response.headers["Content-Transfer-Encoding"] = "base64"
    response.headers["Cache-Control"] = "no-cache, no-store, must-revalidate"
    return response