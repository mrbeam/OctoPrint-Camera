#!/usr/bin/env python

def send_file_b64(item):
    if isinstance(item, str):
        with open(item, "rb",) as fh:
            buf = base64.b64encode(fh.read())
        response = flask.make_response(buf)
        response.headers["Content-Transfer-Encoding"] = "base64"
        response.headers["Cache-Control"] = "no-cache, no-store, must-revalidate"
        return response
