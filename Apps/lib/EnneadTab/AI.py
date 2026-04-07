#!/usr/bin/python
# -*- coding: utf-8 -*-
"""AI translation services via EnneadTab proxy.

All AI calls are proxied through enneadtab.com, which handles
the actual LLM API keys server-side. Desktop authentication
is handled lazily via AUTH module.
"""

import json
import AUTH

try:
    # CPython 3.x
    from urllib.request import urlopen, Request
    from urllib.error import URLError, HTTPError
except ImportError:
    # IronPython 2.7
    from urllib2 import urlopen, Request, URLError, HTTPError

ENNEADTAB_URL = "https://enneadtab.com"


def translate(input_text,
              target_language="cn",
              personality="professional architect, precise, concise, and creative"):
    """Translates input text to target language using EnneadTab AI proxy.

    Args:
        input_text: Text to be translated.
        target_language: Target language code (default: "cn").
        personality: Translation style guidance.

    Returns:
        Translated text, or empty string if translation fails.
    """
    token = AUTH.get_token()
    if not token:
        return ""

    url = "{}/api/ai/translate".format(ENNEADTAB_URL)
    payload = json.dumps({
        "text": input_text,
        "targetLanguage": target_language,
        "personality": personality
    })

    try:
        req = Request(url)
        req.add_header("Content-Type", "application/json")
        req.add_header("Authorization", "Bearer {}".format(token))

        response = urlopen(req, payload.encode("utf-8"), timeout=120)
        body = response.read()
        if isinstance(body, bytes):
            body = body.decode("utf-8")
        data = json.loads(body)
        return data.get("translation", "")
    except HTTPError as e:
        if e.code == 401:
            # Token expired, clear and retry once
            AUTH.clear_token()
            token = AUTH.get_token()
            if not token:
                return ""
            return translate(input_text, target_language, personality)
        print("Translation API error: {}".format(e))
        return ""
    except Exception as e:
        print("Translation failed: {}".format(e))
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


def chat(messages, system_prompt=None, temperature=None):
    """Send a chat completion request via EnneadTab AI proxy.

    Args:
        messages: List of dicts with 'role' and 'content' keys.
        system_prompt: Optional system prompt.
        temperature: Optional temperature (0.0-1.0).

    Returns:
        str: AI response content, or empty string on failure.
    """
    token = AUTH.get_token()
    if not token:
        return ""

    url = "{}/api/ai/desktop-chat".format(ENNEADTAB_URL)
    body = {"messages": messages}
    if system_prompt:
        body["systemPrompt"] = system_prompt
    if temperature is not None:
        body["temperature"] = temperature

    payload = json.dumps(body)

    try:
        req = Request(url)
        req.add_header("Content-Type", "application/json")
        req.add_header("Authorization", "Bearer {}".format(token))

        response = urlopen(req, payload.encode("utf-8"), timeout=120)
        resp_body = response.read()
        if isinstance(resp_body, bytes):
            resp_body = resp_body.decode("utf-8")
        data = json.loads(resp_body)
        return data.get("content", "")
    except HTTPError as e:
        if e.code == 401:
            AUTH.clear_token()
            token = AUTH.get_token()
            if not token:
                return ""
            return chat(messages, system_prompt, temperature)
        print("Chat API error: {}".format(e))
        return ""
    except Exception as e:
        print("Chat failed: {}".format(e))
        return ""


if __name__ == "__main__":
    sample_sentences = ["Hello world", "The building is beautiful"]
    print(translate_multiple(sample_sentences))
