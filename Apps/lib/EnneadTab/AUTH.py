#!/usr/bin/python
# -*- coding: utf-8 -*-
"""Shared authentication module for EnneadTab desktop tools.

Provides lazy browser-based OAuth authentication with enneadtab.com.
Tokens are cached locally and only requested when an AI tool is used.
"""

import os
import json
import time
import webbrowser

try:
    # CPython 3.x
    from urllib.request import urlopen, Request
    from urllib.error import URLError
except ImportError:
    # IronPython 2.7 / CPython 2.7
    from urllib2 import urlopen, Request, URLError

try:
    import uuid
    def _make_uuid():
        return str(uuid.uuid4())
except ImportError:
    # IronPython fallback
    import random
    def _make_uuid():
        hex_chars = "0123456789abcdef"
        parts = []
        for length in [8, 4, 4, 4, 12]:
            parts.append("".join(random.choice(hex_chars) for _ in range(length)))
        return "-".join(parts)

import NOTIFICATION
import ERROR_HANDLE

ENNEADTAB_URL = "https://enneadtab.com"
TOKEN_CACHE_FILE = "desktop_auth_token.sexyDuck"
_POLL_INTERVAL = 2  # seconds
_POLL_TIMEOUT = 120  # seconds
_cached_token = None  # in-memory cache for current session


def get_token():
    """Get a valid auth token for enneadtab.com API calls.

    Checks in-memory cache, then file cache, then initiates browser auth.
    This is the only function external modules need to call.

    Returns:
        str: A valid auth token, or None if authentication failed.
    """
    global _cached_token

    # 1. In-memory cache (fastest)
    if _cached_token:
        return _cached_token

    # 2. File cache
    token = _load_cached_token()
    if token:
        _cached_token = token
        return token

    # 3. Browser auth flow
    token = _request_new_token()
    if token:
        _cached_token = token
    return token


def clear_token():
    """Clear cached token (for logout or token refresh)."""
    global _cached_token
    _cached_token = None
    path = _get_cache_path()
    if os.path.exists(path):
        try:
            os.remove(path)
        except Exception:
            pass


def _get_cache_path():
    """Get the path to the token cache file."""
    appdata = os.environ.get("APPDATA", "")
    if appdata:
        folder = os.path.join(appdata, "EnneadTab")
    else:
        # Fallback to user home
        folder = os.path.join(os.path.expanduser("~"), ".enneadtab")

    if not os.path.exists(folder):
        try:
            os.makedirs(folder)
        except Exception:
            pass

    return os.path.join(folder, TOKEN_CACHE_FILE)


def _load_cached_token():
    """Load and validate token from file cache.

    Returns:
        str: Valid token or None if expired/missing.
    """
    path = _get_cache_path()
    if not os.path.exists(path):
        return None

    try:
        with open(path, "r") as f:
            data = json.load(f)

        exp = data.get("exp", 0)
        if time.time() > exp:
            # Token expired, clean up
            try:
                os.remove(path)
            except Exception:
                pass
            return None

        return data.get("token")
    except Exception:
        return None


def _save_token(token, exp):
    """Save token to file cache."""
    path = _get_cache_path()
    try:
        with open(path, "w") as f:
            json.dump({"token": token, "exp": exp}, f)
    except Exception:
        pass


def _request_new_token():
    """Initiate browser auth flow and poll for token.

    Returns:
        str: Token if auth succeeds, None if timeout or error.
    """
    request_id = _make_uuid()
    url = "{}/auth/desktop-token?request_id={}".format(ENNEADTAB_URL, request_id)

    NOTIFICATION.messenger(
        main_text="Opening browser for EnneadTab login.\nPlease sign in to enable AI features.\n\nThis is a one-time setup that lasts 30 days."
    )

    webbrowser.open(url)

    # Poll for token
    poll_url = "{}/api/auth/desktop-token/poll?request_id={}".format(ENNEADTAB_URL, request_id)
    elapsed = 0

    while elapsed < _POLL_TIMEOUT:
        time.sleep(_POLL_INTERVAL)
        elapsed += _POLL_INTERVAL

        try:
            req = Request(poll_url)
            response = urlopen(req, timeout=10)
            body = response.read()
            if isinstance(body, bytes):
                body = body.decode("utf-8")
            data = json.loads(body)

            status = data.get("status")
            if status == "ready":
                token = data.get("token")
                exp = data.get("exp", time.time() + 30 * 24 * 3600)
                _save_token(token, exp)
                return token
            elif status == "expired":
                NOTIFICATION.messenger(main_text="Login session expired. Please try again.")
                return None
        except Exception:
            # Network error, keep polling
            continue

    NOTIFICATION.messenger(main_text="Login timed out after {} seconds.\nPlease try again.".format(_POLL_TIMEOUT))
    return None


def unit_test():
    """Unit test for the AUTH module."""
    print("Testing token cache path: {}".format(_get_cache_path()))
    print("Testing token load: {}".format(_load_cached_token()))
    token = get_token()
    print("Got token: {}".format("Yes" if token else "No"))


if __name__ == "__main__":
    unit_test()
