#!/usr/bin/python
# -*- coding: utf-8 -*-

"""
Minimal NYU HQ webapp API client.

The NYU HQ website repo holds ZERO data: Postgres is the system of record and
the webapp's /api/* endpoints are the only gateway. Revit syncs through them:

  - GET  /api/targets    clean program targets (Revit READS)
  - POST /api/report     matched area report (Revit PUBLISHES)
  - POST /api/geometry   extracted model geometry (Revit PUBLISHES)

Auth is a service token sent as ``Authorization: Bearer <token>``. The token
lives in the NYU_HQ_SERVICE_TOKEN environment variable on the machine running
Revit -- it is never written to git, and the webapp never exposes GitHub
writes.

Python 2 / IronPython compatible (Revit).
"""

import json

import config

try:
    # Python 3
    import urllib.request as _request
    import urllib.error as _error
except ImportError:
    # Python 2 / IronPython
    import urllib2 as _request
    _error = _request


class NyuHqApiError(Exception):
    """Raised when the NYU HQ API cannot be reached or rejects a request."""
    pass


def _api_origin():
    origin = (config.NYU_HQ_API_URL or "").strip().rstrip("/")
    if not origin:
        raise NyuHqApiError(
            "NYU_HQ_API_URL is not set.\n"
            "Set the NYU_HQ_API_URL environment variable to the NYU HQ "
            "webapp origin (e.g. https://enneadtab.com) and run again.")
    return origin


def _service_token():
    token = (config.NYU_HQ_SERVICE_TOKEN or "").strip()
    if not token:
        raise NyuHqApiError(
            "NYU_HQ_SERVICE_TOKEN is not set.\n"
            "Set the NYU_HQ_SERVICE_TOKEN environment variable to the "
            "service token provisioned for the NYU HQ webapp and run again.")
    return token


def _actor():
    return (config.NYU_HQ_ACTOR or "").strip() or "revit-monitor-area"


def _call(path, payload=None, timeout=90):
    """GET (payload None) or POST (payload given) a JSON API path.

    Returns the decoded JSON body. Raises NyuHqApiError on any failure.
    """
    url = _api_origin() + path
    data = None
    if payload is not None:
        data = json.dumps(payload).encode("utf-8")
    req = _request.Request(url, data=data)
    req.add_header("Content-Type", "application/json")
    req.add_header("Authorization", "Bearer " + _service_token())
    req.add_header("X-Actor", _actor())
    try:
        resp = _request.urlopen(req, timeout=timeout)
        status = resp.getcode()
        raw = resp.read()
    except _error.HTTPError as e:
        status = e.code
        try:
            raw = e.read()
        except Exception:
            raw = ""
    except Exception as e:
        raise NyuHqApiError(
            "NYU HQ API request failed ({} {}): {}".format(
                "POST" if payload is not None else "GET", path, e))
    if isinstance(raw, bytes):
        raw = raw.decode("utf-8")
    try:
        body = json.loads(raw) if raw else None
    except ValueError:
        body = None
    if status >= 400:
        detail = ""
        if isinstance(body, dict) and body.get("error"):
            detail = ": {}".format(body["error"])
        raise NyuHqApiError(
            "NYU HQ API {} {} returned HTTP {}{}".format(
                "POST" if payload is not None else "GET",
                path, status, detail))
    return body


def get_targets():
    """Fetch the clean target program document (GET /api/targets)."""
    return _call("/api/targets")


def post_report(report_data):
    """Publish the matched area report (POST /api/report)."""
    return _call("/api/report", payload=report_data)


def post_geometry(geometry_data):
    """Publish the extracted model geometry (POST /api/geometry)."""
    return _call("/api/geometry", payload=geometry_data)
