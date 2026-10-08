#!/usr/bin/python
# -*- coding: utf-8 -*-
"""Shared authentication module for EnneadTab desktop tools.

Provides lazy browser-based sign-in with enneadtab.com.
Tokens are cached locally and only requested when an AI tool is used.

Non-blocking design for WPF/XAML forms:
- get_token() returns instantly (cached token or None)
- request_auth() opens browser + starts a background poller (non-blocking)
- Next call to get_token() finds the cached token after user signs in

Sign-in uses the EnneadTab-Home device flow (TODO-7915). The token never
travels in a URL:
  1. POST {ENNEADTAB_URL}/api/desktop-auth/start {"app": "revit"|"rhino"}
     -> {"sessionId", "authUrl"}
  2. The authUrl opens in the browser; the user approves there.
  3. Poll GET {ENNEADTAB_URL}/api/desktop-auth/poll?session=<id> every 2 s
     until {"status": "ready", "token": ...} (HTTP 202 while pending).
The old localhost HttpListener callback (/callback?token=) is gone.

Python 2 / IronPython compatible (Revit, Rhino 7) and CPython 3.
"""

import os
import json
import time
import webbrowser
import threading

try:
    # Python 3
    import urllib.request as _request
    import urllib.error as _error
    from urllib.parse import quote as _quote
except ImportError:
    # Python 2 / IronPython
    import urllib2 as _request
    _error = _request
    from urllib import quote as _quote

import NOTIFICATION

ENNEADTAB_URL = "https://enneadtab.com"
TOKEN_CACHE_FILE = "desktop_auth_token.sexyDuck"
_cached_token = None  # in-memory cache for current session
_auth_in_progress = False  # prevent multiple browser opens

# 2026-05-14 -- auth-complete listeners. Caller dialogs (Rhino/Revit AI Render,
# QAQC AI, AI Translate, etc.) register a zero-arg callback so they can
# refresh their stale UI state the moment the OAuth callback writes a token.
# Without this, the user sees "Sign-in complete" in the browser but the
# dialog still shows the un-authed empty state until they click again.
#
# Callbacks fire on the AUTH worker thread (.NET or Python) immediately
# after _save_token() persists the token. Listeners MUST marshal any UI
# work back to the main/UI thread themselves (Dispatcher.BeginInvoke for
# WPF, Eto.Application.AsyncInvoke for Eto/Rhino). Exceptions in listeners
# are swallowed so one bad listener cannot block the next.
_auth_complete_listeners = []

# Detect .NET availability (IronPython in Revit/Rhino)
_HAS_DOTNET = False
try:
    import clr
    clr.AddReference("System")
    from System.Threading import Thread as DotNetThread, ThreadStart
    _HAS_DOTNET = True
except Exception:
    pass


def get_token():
    """Get a valid auth token for enneadtab.com API calls.

    Returns instantly -- never blocks the UI thread.
    Returns cached token, or None if not authenticated yet.
    Call request_auth() to start the browser login flow.

    Returns:
        str: A valid auth token, or None if not yet authenticated.
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

    return None


def get_token_blocking():
    """Get a valid auth token, blocking until auth completes if needed.

    Use this ONLY from CPython scripts (Rhino 8, standalone tools) where
    blocking is acceptable. NEVER call from Revit IronPython UI threads.

    Returns:
        str: A valid auth token, or None if authentication failed.
    """
    token = get_token()
    if token:
        return token

    # Start auth and wait
    request_auth()

    # Block until token arrives or timeout
    deadline = time.time() + 120
    while time.time() < deadline:
        time.sleep(0.5)
        token = _load_cached_token()
        if token:
            global _cached_token
            _cached_token = token
            return token

    NOTIFICATION.messenger(
        main_text="Login timed out. Please try again."
    )
    return None


def request_auth():
    """Start browser auth flow in the background. Non-blocking.

    Starts a device-flow session, opens the browser for SSO, and polls for
    the approved token in a background thread.
    Call get_token() after the user completes sign-in.
    """
    global _auth_in_progress

    if _auth_in_progress:
        return

    _auth_in_progress = True

    if _HAS_DOTNET:
        # Use .NET Thread for IronPython (more reliable in Revit)
        def _run_dotnet():
            try:
                _do_auth_flow()
            except Exception as e:
                print("AUTH .NET flow error: {}".format(e))
            finally:
                global _auth_in_progress
                _auth_in_progress = False

        t = DotNetThread(ThreadStart(_run_dotnet))
        t.IsBackground = True
        t.Start()
    else:
        # Use Python threading for CPython
        def _run():
            try:
                _do_auth_flow()
            except Exception as e:
                print("AUTH Python flow error: {}".format(e))
            finally:
                global _auth_in_progress
                _auth_in_progress = False

        t = threading.Thread(target=_run)
        t.daemon = True
        t.start()


def is_auth_in_progress():
    """Check if a browser auth flow is currently running."""
    return _auth_in_progress


def register_auth_complete_listener(callback):
    """Register a zero-arg callable to fire when a token lands successfully.

    Use this from any AI gate dialog that was opened BEFORE the user signed
    in. When the OAuth callback writes the token, every registered listener
    is invoked exactly once so the dialog can refresh its stale UI state
    (presets, gallery, quota, "Sign in required" labels, etc.).

    The callback fires on the AUTH worker thread (.NET or Python). Listeners
    are responsible for marshaling UI work to the proper UI thread:
      - WPF / Revit: self.Dispatcher.BeginInvoke(System.Action(fn))
      - Eto / Rhino: Eto.Forms.Application.Instance.AsyncInvoke(fn)

    Exceptions raised inside a listener are swallowed and printed so one
    misbehaving dialog cannot block other listeners or crash the auth
    worker thread.

    Args:
        callback: zero-arg callable. Adding the same callable twice is a
            no-op (idempotent).

    Returns:
        The callback itself, so this can be used as a decorator pattern
        or chained: ``handler = AUTH.register_auth_complete_listener(fn)``.
    """
    if callback is None:
        return callback
    if callback not in _auth_complete_listeners:
        _auth_complete_listeners.append(callback)
    return callback


def unregister_auth_complete_listener(callback):
    """Remove a previously registered listener. No-op if not present.

    Dialogs MUST call this from their close/dispose handler so closed
    dialogs do not receive callbacks against disposed widgets (that would
    raise inside the listener and surface as a CLR unhandled exception in
    IronPython / Revit). See ``register_auth_complete_listener`` for the
    full contract.
    """
    try:
        _auth_complete_listeners.remove(callback)
    except ValueError:
        pass


def _fire_auth_complete_listeners():
    """Invoke every registered listener. Called from the auth worker thread
    after a token has been persisted. Exceptions are isolated per-listener."""
    snapshot = list(_auth_complete_listeners)  # avoid mutation during iteration
    for cb in snapshot:
        try:
            cb()
        except Exception as e:
            print("AUTH listener error: {}".format(e))


def _notify_user_signed_in():
    """Pop a toast telling the user auth succeeded and to retry the action.

    Best-effort: NOTIFICATION.messenger spawns an external EXE which may be
    rate-limited or unavailable on a fresh install. Any failure here is
    silent -- the listener-driven UI refresh is the primary signal; the
    toast is a secondary cue for dialogs that did not register a listener.
    """
    try:
        NOTIFICATION.messenger(
            main_text=(
                "Sign-in complete! You can return to EnneadTab.\n"
                "If a dialog still looks empty, click the action button "
                "again to refresh."
            )
        )
    except Exception as e:
        print("AUTH notify error: {}".format(e))


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
            try:
                os.remove(path)
            except Exception:
                pass
            return None

        return data.get("token")
    except Exception:
        return None


def _save_token(token, exp):
    """Save token to file cache.

    On success also fires:
      1. A user-facing toast (NOTIFICATION.messenger) so the user knows the
         browser hand-off succeeded and that they can retry whatever action
         opened the auth flow.
      2. Every registered auth-complete listener so dialogs that opened
         before the user signed in can refresh their stale UI without
         requiring a click.

    Steps 1 + 2 run AFTER the token is persisted so listeners that call
    ``get_token()`` see the new token immediately. Both steps are wrapped
    individually so a failure in one cannot block the other.
    """
    global _cached_token
    path = _get_cache_path()
    saved = False
    try:
        with open(path, "w") as f:
            json.dump({"token": token, "exp": exp}, f)
        _cached_token = token
        saved = True
    except Exception:
        pass

    if not saved:
        return

    _notify_user_signed_in()
    _fire_auth_complete_listeners()


def _decode_token_expiry(token):
    """Decode expiry from token payload (base64url JSON)."""
    exp = time.time() + 30 * 24 * 3600  # default 30 days
    try:
        import base64
        payload_b64 = token.split(".")[0]
        # Add padding
        padding = 4 - len(payload_b64) % 4
        if padding != 4:
            payload_b64 += "=" * padding
        payload_str = base64.urlsafe_b64decode(payload_b64).decode("utf-8")
        payload = json.loads(payload_str)
        exp = payload.get("exp", exp)
    except Exception:
        pass
    return exp


# ============================================================
# Device flow: POST /start -> open browser -> poll /poll
# ============================================================

_AUTH_START_URL = ENNEADTAB_URL + "/api/desktop-auth/start"
_AUTH_POLL_URL = ENNEADTAB_URL + "/api/desktop-auth/poll"
_POLL_INTERVAL_SECONDS = 2
_POLL_TIMEOUT_SECONDS = 120


def _desktop_host_app():
    """Host app key Home shows on its sign-in pages ("rhino"/"revit"), or None."""
    try:
        import ENVIRONMENT
        if ENVIRONMENT.IS_RHINO_ENVIRONMENT:
            return "rhino"
        if ENVIRONMENT.IS_REVIT_ENVIRONMENT:
            return "revit"
    except Exception:
        pass
    return None


def _to_text(raw):
    if isinstance(raw, bytes):
        return raw.decode("utf-8")
    return raw


def _http_post_json(url, payload, timeout=30):
    """POST JSON and return the decoded JSON body. Raises on any failure."""
    req = _request.Request(url, data=json.dumps(payload).encode("utf-8"))
    req.add_header("Content-Type", "application/json")
    resp = _request.urlopen(req, timeout=timeout)
    return json.loads(_to_text(resp.read()))


def _http_get_json(url, timeout=30):
    """GET JSON. Returns (http_status, decoded_body_or_None).

    HTTP error statuses (404 session gone, ...) are returned, not raised.
    Network failures raise.
    """
    req = _request.Request(url)
    req.add_header("Accept", "application/json")
    try:
        resp = _request.urlopen(req, timeout=timeout)
        status = resp.getcode()
        raw = resp.read()
    except _error.HTTPError as e:
        status = e.code
        try:
            raw = e.read()
        except Exception:
            raw = b""
        try:
            e.close()
        except Exception:
            pass
    try:
        body = json.loads(_to_text(raw)) if raw else None
    except ValueError:
        body = None
    return status, body


def _poll_for_token(session_id):
    """Poll until the user approves the sign-in. Returns the token string."""
    url = _AUTH_POLL_URL + "?session=" + _quote(session_id)
    deadline = time.time() + _POLL_TIMEOUT_SECONDS
    while time.time() < deadline:
        status, body = _http_get_json(url)
        if status == 404:
            raise Exception("sign-in session expired before approval")
        if status >= 400:
            raise Exception("sign-in poll failed (HTTP {})".format(status))
        if isinstance(body, dict) and body.get("status") == "ready" and body.get("token"):
            return body["token"]
        time.sleep(_POLL_INTERVAL_SECONDS)  # pending (HTTP 202)
    raise Exception("sign-in timed out after {} s".format(_POLL_TIMEOUT_SECONDS))


def _do_auth_flow(app=None):
    """Run the browser device flow and cache the token. Raises on failure.

    The caller (request_auth) prints the error, so a failed sign-in is
    visible, and always clears _auth_in_progress.
    """
    app = app or _desktop_host_app()
    started = _http_post_json(_AUTH_START_URL, {"app": app} if app else {})
    session_id = started.get("sessionId") if isinstance(started, dict) else None
    auth_url = started.get("authUrl") if isinstance(started, dict) else None
    if not session_id or not auth_url:
        raise Exception("sign-in start returned no session")
    # The server picks what the browser opens; only follow our own origin.
    if not auth_url.startswith(ENNEADTAB_URL + "/"):
        raise Exception("sign-in start returned an unexpected URL")

    webbrowser.open(auth_url)

    token = _poll_for_token(session_id)
    _save_token(token, _decode_token_expiry(token))


def unit_test():
    """Unit test for the AUTH module."""
    print("Using .NET listener: {}".format(_HAS_DOTNET))
    print("Token cache path: {}".format(_get_cache_path()))
    print("Cached token: {}".format(_load_cached_token()))
    token = get_token()
    print("Got token: {}".format("Yes" if token else "No"))


if __name__ == "__main__":
    unit_test()
