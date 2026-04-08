#!/usr/bin/python
# -*- coding: utf-8 -*-
"""Shared authentication module for EnneadTab desktop tools.

Provides lazy browser-based OAuth authentication with enneadtab.com.
Tokens are cached locally and only requested when an AI tool is used.

Non-blocking design for WPF/XAML forms:
- get_token() returns instantly (cached token or None)
- request_auth() opens browser + starts background listener (non-blocking)
- Next call to get_token() finds the cached token after user signs in

Uses .NET HttpListener for the localhost callback (Python's BaseHTTPServer
is unreliable in IronPython inside Revit). Falls back to Python HTTPServer
for CPython environments.
"""

import os
import json
import time
import webbrowser
import threading

import NOTIFICATION

ENNEADTAB_URL = "https://enneadtab.com"
TOKEN_CACHE_FILE = "desktop_auth_token.sexyDuck"
_cached_token = None  # in-memory cache for current session
_auth_in_progress = False  # prevent multiple browser opens

# Detect .NET availability (IronPython in Revit/Rhino)
_HAS_DOTNET = False
try:
    import clr
    clr.AddReference("System")
    from System.Net import HttpListener
    from System.IO import StreamReader as DotNetStreamReader
    from System.Text import Encoding as DotNetEncoding
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

    Opens the browser for SSO and starts a local HTTP listener
    in a background thread to receive the token callback.
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
                _do_auth_flow_dotnet()
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
                _do_auth_flow_python()
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
    """Save token to file cache."""
    global _cached_token
    path = _get_cache_path()
    try:
        with open(path, "w") as f:
            json.dump({"token": token, "exp": exp}, f)
        _cached_token = token
    except Exception:
        pass


def _extract_token_from_query(query_string):
    """Extract token from URL query string like '/callback?token=xxx'."""
    # Manual parse since we might not have urlparse in .NET path
    if "token=" not in query_string:
        return None
    for part in query_string.split("&"):
        if part.startswith("token="):
            return part[6:]
        # Handle case where it's after ?
        if "?token=" in part:
            return part.split("?token=")[1]
    return None


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
# .NET HttpListener flow (IronPython in Revit/Rhino)
# ============================================================

def _do_auth_flow_dotnet():
    """Auth flow using .NET HttpListener. Runs in .NET background thread."""
    import random
    port = random.randint(49152, 65535)

    listener = HttpListener()
    prefix = "http://localhost:{}/".format(port)
    listener.Prefixes.Add(prefix)

    try:
        listener.Start()
    except Exception as e:
        print("AUTH: Failed to start listener on port {}: {}".format(port, e))
        return

    url = "{}/api/desktop-auth?port={}".format(ENNEADTAB_URL, port)
    webbrowser.open(url)

    # Wait for one request (the callback from enneadtab.com)
    token = None
    deadline = time.time() + 120

    while time.time() < deadline:
        # Non-blocking check with short timeout
        result = listener.BeginGetContext(None, None)
        got_request = result.AsyncWaitHandle.WaitOne(2000)  # 2 sec timeout

        if got_request:
            try:
                context = listener.EndGetContext(result)
                raw_url = context.Request.RawUrl  # e.g. /callback?token=xxx

                # Send success page
                response_body = "<html><body style='font-family:sans-serif;text-align:center;padding:60px;background:#050505;color:#fff'><h2>Authentication successful</h2><p style='color:#a1a1aa'>You can close this window and return to Revit.</p><script>setTimeout(function(){window.close()},2000)</script></body></html>"
                buf = DotNetEncoding.UTF8.GetBytes(response_body)
                context.Response.ContentType = "text/html"
                context.Response.ContentLength64 = buf.Length
                context.Response.OutputStream.Write(buf, 0, buf.Length)
                context.Response.OutputStream.Close()

                # Extract token
                token = _extract_token_from_query(raw_url)
                if token:
                    # URL-decode the token (% encoding from redirect)
                    try:
                        from System.Net import WebUtility
                        token = WebUtility.UrlDecode(token)
                    except Exception:
                        token = token.replace("%2B", "+").replace("%2F", "/").replace("%3D", "=").replace("%2E", ".")
                    break
            except Exception as e:
                print("AUTH: Error handling callback: {}".format(e))
                break

    try:
        listener.Stop()
        listener.Close()
    except Exception:
        pass

    if token:
        exp = _decode_token_expiry(token)
        _save_token(token, exp)


# ============================================================
# Python HTTPServer flow (CPython fallback)
# ============================================================

def _do_auth_flow_python():
    """Auth flow using Python HTTPServer. Runs in Python background thread."""
    try:
        from http.server import HTTPServer, BaseHTTPRequestHandler
        from urllib.parse import urlparse, parse_qs
    except ImportError:
        from BaseHTTPServer import HTTPServer, BaseHTTPRequestHandler
        from urlparse import urlparse, parse_qs

    received_token = [None]  # mutable container for closure

    class CallbackHandler(BaseHTTPRequestHandler):
        def do_GET(self):
            parsed = urlparse(self.path)
            params = parse_qs(parsed.query)
            if parsed.path == "/callback" and "token" in params:
                received_token[0] = params["token"][0]
                body = b"<html><body style='font-family:sans-serif;text-align:center;padding:60px;background:#050505;color:#fff'><h2>Authentication successful</h2><p style='color:#a1a1aa'>You can close this window.</p><script>setTimeout(function(){window.close()},2000)</script></body></html>"
                self.send_response(200)
                self.send_header("Content-Type", "text/html")
                self.end_headers()
                self.wfile.write(body)
            else:
                self.send_response(404)
                self.end_headers()

        def log_message(self, format, *args):
            pass

    server = HTTPServer(("127.0.0.1", 0), CallbackHandler)
    port = server.server_address[1]

    server_thread = threading.Thread(target=server.serve_forever)
    server_thread.daemon = True
    server_thread.start()

    url = "{}/api/desktop-auth?port={}".format(ENNEADTAB_URL, port)
    webbrowser.open(url)

    deadline = time.time() + 120
    while time.time() < deadline:
        if received_token[0]:
            break
        time.sleep(0.5)

    server.shutdown()

    token = received_token[0]
    if token:
        exp = _decode_token_expiry(token)
        _save_token(token, exp)


def unit_test():
    """Unit test for the AUTH module."""
    print("Using .NET listener: {}".format(_HAS_DOTNET))
    print("Token cache path: {}".format(_get_cache_path()))
    print("Cached token: {}".format(_load_cached_token()))
    token = get_token()
    print("Got token: {}".format("Yes" if token else "No"))


if __name__ == "__main__":
    unit_test()
