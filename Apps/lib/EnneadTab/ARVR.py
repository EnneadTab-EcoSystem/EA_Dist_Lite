# -*- coding: utf-8 -*-
"""ARVR client module for EnneadTab.

Provides model staging, uploading, and room pairing to EnneadTab-ARVR (https://enneadtab.com/arvr).
Supports IronPython 2.7 (.NET WebRequest) and CPython 3.x (urllib).
"""

import os
import random
import webbrowser
from EnneadTab import NOTIFICATION, FOLDER

ARVR_URL_BASE = "https://enneadtab.com/arvr"
SUBDIR_STAGING = "ARVR_Exports"

def generate_room_id():
    """Generate a friendly 6-char alphanumeric room code."""
    chars = "23456789ABCDEFGHJKLMNPQRSTUVWXYZ"
    return "".join(random.choice(chars) for _ in range(6))

def get_staging_directory():
    """Get or create local temp staging directory for exported 3D assets."""
    staging_dir = FOLDER.get_local_dump_folder_folder(SUBDIR_STAGING)
    if not os.path.exists(staging_dir):
        try:
            os.makedirs(staging_dir)
        except Exception:
            pass
    return staging_dir

def stage_and_upload(filepath, room_id=None, timeout_ms=90000, auto_open_browser=True):
    """Perform complete staging validation, cloud upload, and web pairing.

    Args:
        filepath (str): Local path to .glb, .gltf, or .usdz file.
        room_id (str, optional): Target room code. If None, auto-generates.
        timeout_ms (int): Network timeout in milliseconds.
        auto_open_browser (bool): Automatically open paired desktop hub in browser.

    Returns:
        tuple: (success, room_id, web_url, error_message)
    """
    if not filepath or not os.path.exists(filepath):
        msg = "File does not exist: {}".format(filepath)
        NOTIFICATION.messenger(msg)
        return False, None, None, msg

    file_size = os.path.getsize(filepath)
    if file_size == 0:
        msg = "Exported file is empty (0 bytes): {}".format(os.path.basename(filepath))
        NOTIFICATION.messenger(msg)
        return False, None, None, msg

    if not room_id:
        room_id = generate_room_id()
    else:
        room_id = room_id.upper().strip()

    filename = os.path.basename(filepath)
    NOTIFICATION.messenger("Staging & uploading [{}] ({:.1f} MB) to AR/VR room {}...".format(
        filename, file_size / (1024.0 * 1024.0), room_id))

    ok, final_room, web_url, err = upload_model_file(filepath, room_id=room_id, timeout_ms=timeout_ms)
    if ok:
        NOTIFICATION.messenger(
            "3D Model successfully staged & beamed to Room {}!\nOpening mobile pairing hub...".format(final_room))
        if auto_open_browser:
            webbrowser.open(web_url)
        return True, final_room, web_url, None
    else:
        NOTIFICATION.messenger("Upload failed: {}\nOpening default web hub instead.".format(err))
        if auto_open_browser:
            open_web_hub()
        return False, room_id, None, err

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
    content_type = {
        ".usdz": "model/vnd.usdz+zip",
        ".glb": "model/gltf-binary",
        ".gltf": "model/gltf+json",
    }.get(ext, "application/octet-stream")
    
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
