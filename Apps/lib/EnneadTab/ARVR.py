# -*- coding: utf-8 -*-
"""ARVR client module for EnneadTab.

Provides model uploading and room pairing to EnneadTab-ARVR (https://enneadtab.com/arvr).
Supports IronPython 2.7 (.NET WebRequest) and CPython 3.x (urllib).
"""

import os
import random
import webbrowser
from EnneadTab import NOTIFICATION

ARVR_URL_BASE = "https://enneadtab.com/arvr"

def generate_room_id():
    """Generate a friendly 6-char alphanumeric room code."""
    chars = "23456789ABCDEFGHJKLMNPQRSTUVWXYZ"
    return "".join(random.choice(chars) for _ in range(6))

def upload_model_file(filepath, room_id=None, timeout_ms=60000):
    """Upload a 3D model (.glb / .gltf / .usdz) to the ARVR room session.
    
    Args:
        filepath (str): Absolute path to model file.
        room_id (str, optional): Target room id. If None, a new one is generated.
        timeout_ms (int): Network timeout in milliseconds.
        
    Returns:
        tuple: (success, room_id, web_url, error_message)
    """
    if not os.path.exists(filepath):
        return False, None, None, "File does not exist: " + str(filepath)
        
    if not room_id:
        room_id = generate_room_id()
    else:
        room_id = room_id.upper().strip()
        
    url = "{}/api/room/{}".format(ARVR_URL_BASE, room_id)
    
    try:
        with open(filepath, "rb") as f:
            file_bytes = f.read()
    except Exception as e:
        return False, room_id, None, "Failed to read file: " + str(e)
        
    filename = os.path.basename(filepath)
    ext = os.path.splitext(filename)[1].lower()
    content_type = "model/vnd.usdz+zip" if ext == ".usdz" else "model/gltf-binary"
    
    # Send request using .NET if in IronPython, or urllib in CPython
    try:
        from System.Net import WebRequest, ServicePointManager, SecurityProtocolType # pyright: ignore
        import System # pyright: ignore
        ServicePointManager.SecurityProtocol = SecurityProtocolType.Tls12
        request = WebRequest.Create(url)
        request.Method = "POST"
        request.ContentType = content_type
        request.Timeout = timeout_ms
        
        dotnet_bytes = System.Array[System.Byte](bytearray(file_bytes))
        request.ContentLength = dotnet_bytes.Length
        stream = request.GetRequestStream()
        stream.Write(dotnet_bytes, 0, dotnet_bytes.Length)
        stream.Close()
        
        response = request.GetResponse()
        response.Close()
    except ImportError:
        import urllib.request
        req = urllib.request.Request(url, data=file_bytes, headers={"Content-Type": content_type})
        with urllib.request.urlopen(req, timeout=timeout_ms // 1000) as resp:
            pass
    except Exception as e:
        return False, room_id, None, "Upload failed: " + str(e)
        
    web_url = "{}?room={}".format(ARVR_URL_BASE, room_id)
    return True, room_id, web_url, None

def open_web_hub(room_id=None):
    """Open the ARVR web app in default browser."""
    if room_id:
        url = "{}?room={}".format(ARVR_URL_BASE, room_id.upper().strip())
    else:
        url = ARVR_URL_BASE
    webbrowser.open(url)
    return url
