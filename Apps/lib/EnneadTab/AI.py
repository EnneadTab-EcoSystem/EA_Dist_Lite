#!/usr/bin/python
# -*- coding: utf-8 -*-
"""AI services via EnneadTab proxy.

All AI calls are proxied through enneadtab.com, which handles
the actual LLM API keys server-side. Desktop authentication
is handled lazily via AUTH module.

Supports both CPython 3.x (urllib) and IronPython 2.7 (.NET HttpWebRequest).
IronPython's urllib2 has broken SSL, so .NET is used automatically when available.
"""

import json
import AUTH

# --- Runtime detection and HTTP backend ---
_USE_DOTNET = False
try:
    from System.Net import WebRequest, ServicePointManager, SecurityProtocolType
    from System.IO import StreamReader
    from System.Text import Encoding
    _USE_DOTNET = True
except ImportError:
    pass

if not _USE_DOTNET:
    try:
        from urllib.request import urlopen, Request
        from urllib.error import URLError, HTTPError
    except ImportError:
        from urllib2 import urlopen, Request, URLError, HTTPError

ENNEADTAB_URL = "https://enneadtab.com"


class AIRequestError(Exception):
    """Raised when an AI proxy request fails."""
    def __init__(self, message, status_code=None):
        self.status_code = status_code
        Exception.__init__(self, message)


def _post_json(url, payload_str, token, timeout_ms=120000):
    """Low-level HTTP POST to EnneadTab AI proxy.

    Uses .NET HttpWebRequest when running in IronPython (reliable HTTPS),
    falls back to urllib for CPython.

    Args:
        url: Full API URL.
        payload_str: JSON string body.
        token: Bearer auth token.
        timeout_ms: Timeout in milliseconds (default 120s).

    Returns:
        dict: Parsed JSON response.

    Raises:
        AIRequestError: On HTTP or network errors (status_code set for HTTP errors).
    """
    if _USE_DOTNET:
        return _post_json_dotnet(url, payload_str, token, timeout_ms)
    else:
        return _post_json_urllib(url, payload_str, token, timeout_ms)


def _post_json_dotnet(url, payload_str, token, timeout_ms):
    """HTTP POST via .NET HttpWebRequest (IronPython)."""
    try:
        ServicePointManager.SecurityProtocol = SecurityProtocolType.Tls12
        request = WebRequest.Create(url)
        request.Method = "POST"
        request.ContentType = "application/json"
        request.Headers.Add("Authorization", "Bearer {}".format(token))
        request.Timeout = timeout_ms

        body_bytes = Encoding.UTF8.GetBytes(payload_str)
        request.ContentLength = body_bytes.Length
        req_stream = request.GetRequestStream()
        req_stream.Write(body_bytes, 0, body_bytes.Length)
        req_stream.Close()

        response = request.GetResponse()
        reader = StreamReader(response.GetResponseStream())
        result_text = reader.ReadToEnd()
        reader.Close()
        response.Close()

        return json.loads(result_text)
    except Exception as e:
        error_msg = str(e)
        status = None
        if "401" in error_msg or "Unauthorized" in error_msg:
            status = 401
        elif "403" in error_msg:
            status = 403
        elif "429" in error_msg:
            status = 429
        raise AIRequestError(error_msg, status_code=status)


def _post_json_urllib(url, payload_str, token, timeout_ms):
    """HTTP POST via urllib (CPython)."""
    try:
        req = Request(url)
        req.add_header("Content-Type", "application/json")
        req.add_header("Authorization", "Bearer {}".format(token))

        response = urlopen(req, payload_str.encode("utf-8"), timeout=timeout_ms // 1000)
        resp_body = response.read()
        if isinstance(resp_body, bytes):
            resp_body = resp_body.decode("utf-8")
        return json.loads(resp_body)
    except HTTPError as e:
        raise AIRequestError(str(e), status_code=e.code)
    except Exception as e:
        raise AIRequestError(str(e))


def translate(input_text,
              target_language="cn",
              personality="professional architect, precise, concise, and creative"):
    """Translates input text to target language using EnneadTab AI proxy.

    Uses blocking auth (opens browser if needed, waits for token).

    Args:
        input_text: Text to be translated.
        target_language: Target language code (default: "cn").
        personality: Translation style guidance.

    Returns:
        Translated text, or empty string if translation fails.
    """
    token = AUTH.get_token_blocking()
    if not token:
        return ""

    url = "{}/api/ai/translate".format(ENNEADTAB_URL)
    payload = json.dumps({
        "text": input_text,
        "targetLanguage": target_language,
        "personality": personality
    })

    try:
        data = _post_json(url, payload, token)
        return data.get("translation", "")
    except AIRequestError as e:
        if e.status_code == 401:
            AUTH.clear_token()
            token = AUTH.get_token_blocking()
            if not token:
                return ""
            return translate(input_text, target_language, personality)
        print("Translation API error: {}".format(e))
        return ""


def translate_multiple(input_texts,
              target_language="cn",
              personality="professional architect, precise, concise, and creative, \
                  i will give you a list of item to translate, \
                  please translate them all in the same style and tone, \
                  you will return a list of translated words only, no marker formating, \
                  if the input contain both English and Chinese, \
                  please just focus on translating the English part and ignore Chinese part"):
    """Translate multiple texts at once.

    Args:
        input_texts: List of texts to translate.
        target_language: Target language code.
        personality: Translation style guidance.

    Returns:
        dict: Mapping of original text to translated text.
    """
    input_joined = "\n".join([str(x).strip() for x in input_texts if len(str(x).strip()) != 0])

    result = translate(input_joined, target_language, personality)
    if not result or result == "":
        return {}

    result_list = result.split("\n")
    while len(result_list) < len(input_texts):
        result_list.append("")

    return {k: v.strip() or k for k, v in zip(input_texts, result_list)}


def chat_with_token(token, messages, temperature=None, json_mode=False):
    """Send a chat request using a pre-obtained auth token.

    Use this from IronPython scripts (Revit/Rhino) that manage their own
    auth UI (e.g. showing "Waiting for browser sign-in..." in a WPF textbox).
    The caller is responsible for obtaining the token via AUTH.get_token()
    and handling the auth waiting loop.

    Args:
        token: Bearer auth token from AUTH.get_token().
        messages: List of dicts with 'role' and 'content' keys.
        temperature: Optional temperature (0.0-1.0).
        json_mode: If True, request structured JSON output from Gemini.

    Returns:
        str: AI response content (JSON string if json_mode=True).

    Raises:
        AIRequestError: On failure. Check status_code == 401 for expired token.
    """
    url = "{}/api/ai/desktop-chat".format(ENNEADTAB_URL)
    body = {"messages": messages}
    if temperature is not None:
        body["temperature"] = temperature
    if json_mode:
        body["jsonMode"] = True
    payload = json.dumps(body, ensure_ascii=True)
    data = _post_json(url, payload, token)
    return data.get("content", "")


def chat(messages, system_prompt=None, temperature=None):
    """Send a chat completion request via EnneadTab AI proxy.

    Uses blocking auth (opens browser if needed, waits for token).
    For IronPython scripts with custom auth UI, use chat_with_token() instead.

    Args:
        messages: List of dicts with 'role' and 'content' keys.
        system_prompt: Optional system prompt (prepended to messages).
        temperature: Optional temperature (0.0-1.0).

    Returns:
        str: AI response content, or empty string on failure.
    """
    token = AUTH.get_token_blocking()
    if not token:
        return ""

    if system_prompt:
        messages = [{"role": "system", "content": system_prompt}] + messages

    try:
        return chat_with_token(token, messages, temperature)
    except AIRequestError as e:
        if e.status_code == 401:
            AUTH.clear_token()
            token = AUTH.get_token_blocking()
            if not token:
                return ""
            return chat_with_token(token, messages, temperature)
        print("Chat API error: {}".format(e))
        return ""


RENDER_URL = "https://ennead-ai.com"


def _post_multipart(url, fields, files, token, timeout_ms=120000):
    """HTTP POST multipart/form-data. Works in both .NET and CPython.

    Args:
        url: Full API URL.
        fields: dict of form fields {name: value}.
        files: list of (field_name, filename, file_bytes, content_type).
        token: Bearer auth token.
        timeout_ms: Timeout in milliseconds.

    Returns:
        dict: Parsed JSON response.

    Raises:
        AIRequestError: On HTTP or network errors.
    """
    import os
    try:
        rand_hex = os.urandom(8).hex()
    except AttributeError:
        # IronPython 2.7: os.urandom returns str, no .hex() method
        rand_hex = ''.join('{:02x}'.format(b) for b in bytearray(os.urandom(8)))
    boundary = "----EnneadTabBoundary{}".format(rand_hex)

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
    else:
        return _post_multipart_urllib(url, body, content_type, token, timeout_ms)


def _post_multipart_dotnet(url, body, content_type, token, timeout_ms):
    """Multipart POST via .NET HttpWebRequest."""
    try:
        ServicePointManager.SecurityProtocol = SecurityProtocolType.Tls12
        request = WebRequest.Create(url)
        request.Method = "POST"
        request.ContentType = content_type
        request.Headers.Add("Authorization", "Bearer {}".format(token))
        request.Timeout = timeout_ms

        # Convert Python bytes to .NET Array[Byte] for IronPython interop
        import System # pyright: ignore
        dotnet_bytes = System.Array[System.Byte](bytearray(body))
        request.ContentLength = dotnet_bytes.Length
        req_stream = request.GetRequestStream()
        req_stream.Write(dotnet_bytes, 0, dotnet_bytes.Length)
        req_stream.Close()

        response = request.GetResponse()
        reader = StreamReader(response.GetResponseStream())
        result_text = reader.ReadToEnd()
        reader.Close()
        response.Close()
        return json.loads(result_text)
    except Exception as e:
        error_msg = str(e)
        status = None
        if "401" in error_msg or "Unauthorized" in error_msg:
            status = 401
        raise AIRequestError(error_msg, status_code=status)


def _post_multipart_urllib(url, body, content_type, token, timeout_ms):
    """Multipart POST via urllib."""
    try:
        req = Request(url)
        req.add_header("Content-Type", content_type)
        req.add_header("Authorization", "Bearer {}".format(token))
        response = urlopen(req, body, timeout=timeout_ms // 1000)
        resp_body = response.read()
        if isinstance(resp_body, bytes):
            resp_body = resp_body.decode("utf-8")
        return json.loads(resp_body)
    except HTTPError as e:
        raise AIRequestError(str(e), status_code=e.code)
    except Exception as e:
        raise AIRequestError(str(e))


def _post_multipart_raw(url, fields, files, token, timeout_ms=180000, progress_callback=None):
    """HTTP POST multipart/form-data, returns raw response text (for SSE parsing).

    Args:
        url: Full API URL.
        fields: dict of form fields.
        files: list of (field_name, filename, file_bytes, content_type).
        token: Bearer auth token.
        timeout_ms: Timeout in milliseconds.
        progress_callback: Optional callable(str) for progress updates.

    Returns:
        str: Raw response body text.

    Raises:
        AIRequestError: On HTTP or network errors.
    """
    import os
    try:
        rand_hex = os.urandom(8).hex()
    except AttributeError:
        rand_hex = ''.join('{:02x}'.format(b) for b in bytearray(os.urandom(8)))
    boundary = "----EnneadTabBoundary{}".format(rand_hex)

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
            request.Headers.Add("Authorization", "Bearer {}".format(token))
            request.Timeout = timeout_ms

            dotnet_bytes = System.Array[System.Byte](bytearray(body))
            request.ContentLength = dotnet_bytes.Length
            req_stream = request.GetRequestStream()
            req_stream.Write(dotnet_bytes, 0, dotnet_bytes.Length)
            req_stream.Close()

            if progress_callback:
                progress_callback("AI is generating your image...")

            response = request.GetResponse()
            reader = StreamReader(response.GetResponseStream())
            result_text = reader.ReadToEnd()
            reader.Close()
            response.Close()
            return result_text
        except Exception as e:
            error_msg = str(e)
            status = 401 if ("401" in error_msg or "Unauthorized" in error_msg) else None
            raise AIRequestError(error_msg, status_code=status)
    else:
        try:
            req = Request(url)
            req.add_header("Content-Type", content_type_header)
            req.add_header("Authorization", "Bearer {}".format(token))
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


def render_image_with_token(token, image_path, prompt, aspect_ratio="16:9", progress_callback=None):
    """Render an architectural image using Gemini via ennead-ai.com.

    Sends a viewport capture + text prompt to RenderPolisher's image
    generation API via SSE streaming. Returns a list of base64-encoded result images.

    Args:
        token: Bearer auth token from AUTH.get_token().
        image_path: Path to JPEG/PNG file (viewport capture).
        prompt: Description of desired rendering style/mood.
        aspect_ratio: Output aspect ratio (default "16:9").
        progress_callback: Optional callable(status_text) for UI progress updates.

    Returns:
        list: List of dicts with 'b64' (base64 image data) and 'mime' keys.

    Raises:
        AIRequestError: On failure. Check status_code == 401 for expired token.
    """
    import os
    with open(image_path, "rb") as f:
        image_bytes = f.read()

    ext = os.path.splitext(image_path)[1].lower()
    mime = "image/png" if ext == ".png" else "image/jpeg"
    filename = os.path.basename(image_path)

    url = "{}/api/create/image?mode=edit&countFactor=1&aspectRatio={}&temperature=1.0".format(
        RENDER_URL, aspect_ratio)

    fields = {
        "inSessionPrompt": prompt,
    }
    files = [
        ("mainImages", filename, image_bytes, mime),
    ]

    # Use SSE streaming mode - non-streaming times out on Vercel
    raw = _post_multipart_raw(url + "&stream=true", fields, files, token, timeout_ms=180000,
                              progress_callback=progress_callback)

    if progress_callback:
        progress_callback("Processing response...")

    # Parse SSE events: each event is "data: {json}\n\n"
    # Split by double-newline to get complete events
    images = []
    for chunk in raw.split("\n\n"):
        chunk = chunk.strip()
        if not chunk.startswith("data: "):
            continue
        json_str = chunk[6:]  # strip "data: " prefix
        try:
            event = json.loads(json_str)
            if event.get("type") == "image":
                result = event.get("result", {})
                if result.get("b64"):
                    images.append(result)
            elif event.get("type") == "error":
                raise AIRequestError(event.get("error", "Generation failed"))
            elif event.get("type") == "progress" and progress_callback:
                progress_callback("AI is generating... {}%".format(
                    int(100 * event.get("current", 0) / max(event.get("total", 1), 1))))
        except (ValueError, KeyError):
            continue
    return images


def render_image(image_path, prompt, aspect_ratio="16:9"):
    """Render an architectural image using Gemini (blocking auth).

    Convenience wrapper that handles auth automatically.

    Args:
        image_path: Path to JPEG/PNG file (viewport capture).
        prompt: Description of desired rendering style/mood.
        aspect_ratio: Output aspect ratio (default "16:9").

    Returns:
        list: List of dicts with 'b64' and 'mime' keys. Empty on failure.
    """
    token = AUTH.get_token_blocking()
    if not token:
        return []

    try:
        return render_image_with_token(token, image_path, prompt, aspect_ratio)
    except AIRequestError as e:
        if e.status_code == 401:
            AUTH.clear_token()
            token = AUTH.get_token_blocking()
            if not token:
                return []
            return render_image_with_token(token, image_path, prompt, aspect_ratio)
        print("Render failed: {}".format(e))
        return []


if __name__ == "__main__":
    sample_sentences = ["Hello world", "The building is beautiful"]
    print(translate_multiple(sample_sentences))
