#!/usr/bin/python
# -*- coding: utf-8 -*-
"""Shared HTTP transport for the EnneadTab.AI submodules.

IronPython 2.7 (Revit/Rhino) — uses .NET HttpWebRequest because urllib2's SSL
is broken inside the host process. CPython 3.x — uses urllib.

All AI calls are proxied through enneadtab.com or ennead-ai.com. The desktop
Bearer token (issued by EnneadTabHome / .desktop_auth_token.sexyDuck) is
injected via the Authorization header. Trust boundary lives in middleware on
the Vercel side.
"""

import binascii
import json
import os


# Public service URLs.
ENNEADTAB_URL = "https://enneadtab.com"   # Chat, translate, auth.
RENDER_URL = "https://ennead-ai.com"       # Image/video render, gallery, prompts, demo-images, quota.


# --- Runtime detection ---
_USE_DOTNET = False
try:
    from System.Net import WebRequest, WebException, ServicePointManager, SecurityProtocolType # pyright: ignore
    from System.IO import StreamReader # pyright: ignore
    from System.Text import Encoding # pyright: ignore
    _USE_DOTNET = True
except ImportError:
    WebException = None  # sentinel for CPython branches

if not _USE_DOTNET:
    try:
        from urllib.request import urlopen, Request
        from urllib.error import HTTPError
    except ImportError:
        from urllib2 import urlopen, Request, HTTPError


class AIRequestError(Exception):
    """Raised when an AI proxy request fails."""
    def __init__(self, message, status_code=None):
        self.status_code = status_code
        Exception.__init__(self, message)


# --- Helpers ---

def _rand_hex(n=8):
    """Return 2n-char ASCII hex. IronPython 2.7 + CPython safe.

    os.urandom returns str on IP27 (no .hex() method); binascii.hexlify works
    on both runtimes regardless of bytes-vs-str semantics.
    """
    return binascii.hexlify(os.urandom(n)).decode("ascii")


def _safe_token(token):
    """Strip whitespace/newlines off a Bearer token before .NET header injection.

    .NET WebHeaderCollection raises ArgumentException on \\r or \\n in values.
    Defensive against the env-var-trailing-newline class of bug.
    """
    return (token or "").strip()


def _status_from_exception(e):
    """Extract a typed HTTP status code from a .NET WebException or urllib HTTPError.

    Locale- and substring-safe (do not match str(e) for "401" — see the
    bug-finder report and feedback_error_signature_matching memory).
    """
    if WebException is not None and isinstance(e, WebException):
        try:
            resp = e.Response
            if resp is not None:
                return int(resp.StatusCode)
        except Exception:
            pass
    code = getattr(e, "code", None)
    if isinstance(code, int):
        return code
    return None


# --- HTTP POST: JSON body ---

def post_json(url, payload_str, token, timeout_ms=120000):
    if _USE_DOTNET:
        return _post_json_dotnet(url, payload_str, token, timeout_ms)
    return _post_json_urllib(url, payload_str, token, timeout_ms)


def _post_json_dotnet(url, payload_str, token, timeout_ms):
    try:
        ServicePointManager.SecurityProtocol = SecurityProtocolType.Tls12
        request = WebRequest.Create(url)
        request.Method = "POST"
        request.ContentType = "application/json"
        request.Headers.Add("Authorization", "Bearer {}".format(_safe_token(token)))
        request.Timeout = timeout_ms

        body_bytes = Encoding.UTF8.GetBytes(payload_str)
        request.ContentLength = body_bytes.Length
        req_stream = request.GetRequestStream()
        req_stream.Write(body_bytes, 0, body_bytes.Length)
        req_stream.Close()

        response = request.GetResponse()
        # StreamReader without an explicit encoding uses Encoding.Default, which
        # on .NET Framework (IronPython's host) is the Windows ANSI code page —
        # any non-Latin-1 byte (UTF-8 multibyte sequences for é, ç, Chinese, …)
        # then triggers IronPython's "'unknown' codec can't decode byte 0xNN".
        # Always pass Encoding.UTF8 explicitly. (2026-04-21 Shorten failure.)
        reader = StreamReader(response.GetResponseStream(), Encoding.UTF8)
        result_text = reader.ReadToEnd()
        reader.Close()
        response.Close()

        return json.loads(result_text)
    except Exception as e:
        raise AIRequestError(str(e), status_code=_status_from_exception(e))


def _post_json_urllib(url, payload_str, token, timeout_ms):
    try:
        req = Request(url)
        req.add_header("Content-Type", "application/json")
        req.add_header("Authorization", "Bearer {}".format(_safe_token(token)))
        response = urlopen(req, payload_str.encode("utf-8"), timeout=timeout_ms // 1000)
        resp_body = response.read()
        if isinstance(resp_body, bytes):
            resp_body = resp_body.decode("utf-8")
        return json.loads(resp_body)
    except HTTPError as e:
        raise AIRequestError(str(e), status_code=e.code)
    except Exception as e:
        raise AIRequestError(str(e))


# --- HTTP GET: JSON body ---

def get_json(url, token=None, timeout_ms=15000):
    if _USE_DOTNET:
        try:
            ServicePointManager.SecurityProtocol = SecurityProtocolType.Tls12
            request = WebRequest.Create(url)
            request.Method = "GET"
            request.Timeout = timeout_ms
            if token:
                request.Headers.Add("Authorization", "Bearer {}".format(_safe_token(token)))
            response = request.GetResponse()
            reader = StreamReader(response.GetResponseStream(), Encoding.UTF8)
            try:
                text = reader.ReadToEnd()
            finally:
                reader.Close()
                response.Close()
            return json.loads(text)
        except Exception as e:
            raise AIRequestError(str(e), status_code=_status_from_exception(e))
    else:
        try:
            req = Request(url)
            if token:
                req.add_header("Authorization", "Bearer {}".format(_safe_token(token)))
            resp = urlopen(req, timeout=timeout_ms // 1000)
            try:
                text = resp.read()
                if isinstance(text, bytes):
                    text = text.decode("utf-8")
            finally:
                resp.close()
            return json.loads(text)
        except HTTPError as e:
            raise AIRequestError(str(e), status_code=e.code)
        except Exception as e:
            raise AIRequestError(str(e))


# --- HTTP POST: multipart/form-data, JSON response ---

def post_multipart(url, fields, files, token, timeout_ms=120000):
    """fields: dict of {name: value}.
       files: list of (field_name, filename, file_bytes, content_type).
    """
    boundary = "----EnneadTabBoundary{}".format(_rand_hex(16))
    body_parts = []
    for name, value in fields.items():
        body_parts.append("--{}".format(boundary).encode("utf-8"))
        body_parts.append('Content-Disposition: form-data; name="{}"'.format(name).encode("utf-8"))
        body_parts.append(b"")
        if isinstance(value, bytes):
            body_parts.append(value)
        else:
            body_parts.append(str(value).encode("utf-8"))
    for field_name, filename, file_bytes, content_type in files:
        body_parts.append("--{}".format(boundary).encode("utf-8"))
        body_parts.append('Content-Disposition: form-data; name="{}"; filename="{}"'.format(field_name, filename).encode("utf-8"))
        body_parts.append("Content-Type: {}".format(content_type).encode("utf-8"))
        body_parts.append(b"")
        body_parts.append(file_bytes)
    body_parts.append("--{}--".format(boundary).encode("utf-8"))
    body_parts.append(b"")
    body = b"\r\n".join(body_parts)
    content_type = "multipart/form-data; boundary={}".format(boundary)

    if _USE_DOTNET:
        return _post_multipart_dotnet(url, body, content_type, token, timeout_ms)
    return _post_multipart_urllib(url, body, content_type, token, timeout_ms)


def _post_multipart_dotnet(url, body, content_type, token, timeout_ms):
    try:
        import System # pyright: ignore
        ServicePointManager.SecurityProtocol = SecurityProtocolType.Tls12
        request = WebRequest.Create(url)
        request.Method = "POST"
        request.ContentType = content_type
        request.Headers.Add("Authorization", "Bearer {}".format(_safe_token(token)))
        request.Timeout = timeout_ms
        dotnet_bytes = System.Array[System.Byte](bytearray(body))
        request.ContentLength = dotnet_bytes.Length
        req_stream = request.GetRequestStream()
        req_stream.Write(dotnet_bytes, 0, dotnet_bytes.Length)
        req_stream.Close()
        response = request.GetResponse()
        reader = StreamReader(response.GetResponseStream(), Encoding.UTF8)
        result_text = reader.ReadToEnd()
        reader.Close()
        response.Close()
        return json.loads(result_text)
    except Exception as e:
        raise AIRequestError(str(e), status_code=_status_from_exception(e))


def _post_multipart_urllib(url, body, content_type, token, timeout_ms):
    try:
        req = Request(url)
        req.add_header("Content-Type", content_type)
        req.add_header("Authorization", "Bearer {}".format(_safe_token(token)))
        response = urlopen(req, body, timeout=timeout_ms // 1000)
        resp_body = response.read()
        if isinstance(resp_body, bytes):
            resp_body = resp_body.decode("utf-8")
        return json.loads(resp_body)
    except HTTPError as e:
        raise AIRequestError(str(e), status_code=e.code)
    except Exception as e:
        raise AIRequestError(str(e))


# --- HTTP POST: multipart/form-data, raw text response (for SSE streams) ---

def post_multipart_raw(url, fields, files, token, timeout_ms=180000, progress_callback=None):
    """Returns the raw response text. Used for SSE streaming endpoints
    (image render). 3xx redirects are mapped to status_code=401 so the
    caller's auth-recovery path fires.
    """
    boundary = "----EnneadTabBoundary{}".format(_rand_hex(16))
    body_parts = []
    for name, value in fields.items():
        body_parts.append("--{}".format(boundary).encode("utf-8"))
        body_parts.append('Content-Disposition: form-data; name="{}"'.format(name).encode("utf-8"))
        body_parts.append(b"")
        body_parts.append(str(value).encode("utf-8") if not isinstance(value, bytes) else value)
    for field_name, filename, file_bytes, ct in files:
        body_parts.append("--{}".format(boundary).encode("utf-8"))
        body_parts.append('Content-Disposition: form-data; name="{}"; filename="{}"'.format(field_name, filename).encode("utf-8"))
        body_parts.append("Content-Type: {}".format(ct).encode("utf-8"))
        body_parts.append(b"")
        body_parts.append(file_bytes)
    body_parts.append("--{}--".format(boundary).encode("utf-8"))
    body_parts.append(b"")
    body = b"\r\n".join(body_parts)
    content_type_header = "multipart/form-data; boundary={}".format(boundary)

    if progress_callback:
        progress_callback("Uploading image...")

    if _USE_DOTNET:
        try:
            import System # pyright: ignore
            ServicePointManager.SecurityProtocol = SecurityProtocolType.Tls12
            request = WebRequest.Create(url)
            request.Method = "POST"
            request.ContentType = content_type_header
            request.Headers.Add("Authorization", "Bearer {}".format(_safe_token(token)))
            request.Timeout = timeout_ms
            request.ReadWriteTimeout = timeout_ms
            request.AllowAutoRedirect = False  # 307 to login page would mask 401

            dotnet_bytes = System.Array[System.Byte](bytearray(body))
            request.ContentLength = dotnet_bytes.Length
            req_stream = request.GetRequestStream()
            req_stream.Write(dotnet_bytes, 0, dotnet_bytes.Length)
            req_stream.Close()

            if progress_callback:
                progress_callback("AI is generating your image...")

            response = request.GetResponse()
            try:
                status_code = int(response.StatusCode)
            except Exception:
                status_code = 200
            if 300 <= status_code < 400:
                try:
                    response.Close()
                except Exception:
                    pass
                raise AIRequestError(
                    "Auth redirect ({}) — token likely expired".format(status_code),
                    status_code=401)

            reader = StreamReader(response.GetResponseStream(), Encoding.UTF8)
            try:
                result_text = reader.ReadToEnd()
            finally:
                reader.Close()
                response.Close()

            if not result_text or len(result_text) < 10:
                raise AIRequestError(
                    "Empty response from server (got {} bytes). Check auth token and server logs.".format(
                        len(result_text or "")))
            return result_text
        except AIRequestError:
            raise
        except Exception as e:
            raise AIRequestError(str(e), status_code=_status_from_exception(e))
    else:
        try:
            req = Request(url)
            req.add_header("Content-Type", content_type_header)
            req.add_header("Authorization", "Bearer {}".format(_safe_token(token)))
            if progress_callback:
                progress_callback("AI is generating your image...")
            response = urlopen(req, body, timeout=timeout_ms // 1000)
            resp_body = response.read()
            if isinstance(resp_body, bytes):
                resp_body = resp_body.decode("utf-8")
            return resp_body
        except HTTPError as e:
            raise AIRequestError(str(e), status_code=e.code)
        except Exception as e:
            raise AIRequestError(str(e))


# --- File downloader ---

def download_url_to_file(url, dest_path, timeout_ms=30000):
    """Download a URL to a local file. No auth header (used for public assets
    like the Ennead style-reference library). Returns dest_path on success.
    """
    if _USE_DOTNET:
        try:
            import System # pyright: ignore
            ServicePointManager.SecurityProtocol = SecurityProtocolType.Tls12
            request = WebRequest.Create(url)
            request.Method = "GET"
            request.Timeout = timeout_ms
            response = request.GetResponse()
            try:
                stream = response.GetResponseStream()
                fs = System.IO.FileStream(dest_path, System.IO.FileMode.Create)
                try:
                    buf = System.Array[System.Byte](bytearray(8192))
                    while True:
                        n = stream.Read(buf, 0, buf.Length)
                        if n <= 0:
                            break
                        fs.Write(buf, 0, n)
                finally:
                    fs.Close()
                    stream.Close()
            finally:
                response.Close()
            return dest_path
        except Exception as e:
            raise AIRequestError(str(e), status_code=_status_from_exception(e))
    else:
        try:
            resp = urlopen(url, timeout=timeout_ms // 1000)
            try:
                with open(dest_path, "wb") as f:
                    while True:
                        chunk = resp.read(8192)
                        if not chunk:
                            break
                        f.write(chunk)
            finally:
                resp.close()
            return dest_path
        except HTTPError as e:
            raise AIRequestError(str(e), status_code=e.code)
        except Exception as e:
            raise AIRequestError(str(e))
