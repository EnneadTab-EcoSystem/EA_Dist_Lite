# -*- coding: utf-8 -*-
"""Depot server contract -- endpoint constants and URL builders.

This is the ONE place the enneadtab.com depot HTTP contract is encoded. The
transport, cache, asset, and state layers all build their URLs through here so
the contract lives in a single file (plan 5.2 / 6 in
docs/plans/2026-07-29-network-drive-retirement-epic.md).

IronPython 2.7 safe (this module loads inside Revit/Rhino): no f-strings, no
type hints, no pathlib. Fully-qualified imports only (never bare "import
ENVIRONMENT") -- the bare form resolves in an editor and raises "No module
named" at runtime under the package path.

Commit 1 ships URL building only; the transport that consumes these URLs lands
in Commit 2. Nothing in the client raises when the server does not exist yet:
the transport treats connection-refused / DNS failure / a 404 on the manifest
or asset route identically to "offline" (plan C15).
"""

import os

# Py2 (IronPython 2.7) vs Py3 quoting. Keep "/" unescaped so a slash-bearing
# asset key ("revit/library/EA_SharedParam.txt") stays a path, not %2F.
try:
    from urllib import quote as _quote          # Py2 / IronPython 2.7
except ImportError:
    from urllib.parse import quote as _quote     # Py3 / Rhino 8 CPython

# Fully-qualified sibling import (repo rule: never bare "import ENVIRONMENT").
from EnneadTab import ENVIRONMENT


# --- Base URL ---------------------------------------------------------------

# The production depot. Overridable per machine via the EA_DEPOT_URL env var
# (plan R10 escape hatch) -- point at a local stub or a different host without
# a code change. Also how the ship gate forces "offline": set it to a
# guaranteed-refused address (e.g. http://127.0.0.1:9).
DEPOT_BASE_URL_DEFAULT = "https://enneadtab.com/depot"


def get_base_url():
    """Resolve the depot base URL: EA_DEPOT_URL override, else the default."""
    override = os.environ.get(ENVIRONMENT.EA_DEPOT_URL_ENV_VAR)
    if override:
        return override.rstrip("/")
    return DEPOT_BASE_URL_DEFAULT


# --- Common headers ---------------------------------------------------------

HEADER_AUTH = "Authorization"                     # "Bearer <token>"
HEADER_CLIENT_VERSION = "X-Depot-Client-Version"  # contract version the client speaks
HEADER_CLIENT = "X-Depot-Client"                  # "EnneadTab-OS/<app version>"
HEADER_ETAG = "ETag"
HEADER_IF_NONE_MATCH = "If-None-Match"
HEADER_SHA256 = "X-Depot-Sha256"

# Contract version this client speaks. Bump only on a breaking contract change;
# the server answers "client_too_old" when it can no longer serve this version.
CLIENT_VERSION = "1"


def client_headers(app_version):
    """Static (non-auth) headers every request carries. Auth is injected by the
    transport from AUTH.get_token(), not here."""
    return {
        HEADER_CLIENT_VERSION: CLIENT_VERSION,
        HEADER_CLIENT: "EnneadTab-OS/{0}".format(app_version),
    }


# --- Error envelope codes (plan 6) ------------------------------------------
# Every non-2xx body is {"ok": false, "error": "<code>", "message": ..,
# "request_id": ..}. These are the "error" values.

ERR_UNAUTHORIZED = "unauthorized"
ERR_FORBIDDEN = "forbidden"
ERR_ASSET_NOT_FOUND = "asset_not_found"
ERR_STATE_NOT_FOUND = "state_not_found"
ERR_REV_CONFLICT = "rev_conflict"
ERR_PAYLOAD_TOO_LARGE = "payload_too_large"
ERR_CLIENT_TOO_OLD = "client_too_old"
ERR_RATE_LIMITED = "rate_limited"
ERR_INTERNAL = "internal"


# --- URL builders -----------------------------------------------------------

def _key(path_key):
    """Quote an asset/state/blob key for use as a URL path, preserving '/'."""
    return _quote(path_key, safe="/")


def manifest_url(channel="prod"):
    """Asset index. If-None-Match -> 304. Carries sha256/etag/size per asset
    and folders[].total_size so the client can refuse an unbounded fetch."""
    return "{0}/api/manifest?channel={1}".format(get_base_url(), _quote(channel))


def asset_url(key, redirect=False):
    """Asset bytes. redirect=True asks for a 302 to a signed blob URL -- REQUIRED
    for the multi-GB Rhino library (Vercel functions must not proxy those)."""
    url = "{0}/api/asset/{1}".format(get_base_url(), _key(key))
    if redirect:
        url += "?redirect=1"
    return url


def state_url(key):
    """GET one state doc {ok, key, rev, updated_at, updated_by, data}; PUT to
    write with a rev check. If-None-Match: "<rev>" -> 304."""
    return "{0}/api/state/{1}".format(get_base_url(), _key(key))


def state_list_url(prefix):
    """List state keys under a prefix. Replaces os.listdir(SHARED_DUMP_FOLDER)."""
    return "{0}/api/state?prefix={1}".format(get_base_url(), _quote(prefix))


def blob_url(key):
    """Large binary. Over 4 MB, request an upload URL first (blob_upload_url)."""
    return "{0}/api/blob/{1}".format(get_base_url(), _key(key))


def blob_upload_url(key):
    """Ask for a signed URL to PUT a large blob directly (over the 4 MB body cap)."""
    return "{0}/api/blob/{1}/upload-url".format(get_base_url(), _key(key))
