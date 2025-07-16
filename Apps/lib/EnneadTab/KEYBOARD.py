#!/usr/bin/python
# -*- coding: utf-8 -*-

"""Keyboard utilities for EnneadTab.

This module provides keyboard input simulation and control functionality
for the EnneadTab ecosystem.

Key Features:
- Send keyboard shortcuts and key combinations
- Cross-platform keyboard input simulation
- Support for common keyboard operations

Compatible with Python 2.7 and Python 3.x
"""

import os
import sys

try:
    import pyautogui
    PYAUTOGUI_AVAILABLE = True
except ImportError:
    PYAUTOGUI_AVAILABLE = False

try:
    import win32api
    import win32con
    WIN32_AVAILABLE = True
except ImportError:
    WIN32_AVAILABLE = False


def send_control_D():
    """Send Ctrl+D keyboard shortcut.
    
    This function sends the Ctrl+D key combination which is commonly used
    for various operations in different applications.
    """
    try:
        if PYAUTOGUI_AVAILABLE:
            pyautogui.hotkey('ctrl', 'd')
        elif WIN32_AVAILABLE:
            # Alternative implementation using win32api
            win32api.keybd_event(win32con.VK_CONTROL, 0, 0, 0)
            win32api.keybd_event(ord('D'), 0, 0, 0)
            win32api.keybd_event(ord('D'), 0, win32con.KEYEVENTF_KEYUP, 0)
            win32api.keybd_event(win32con.VK_CONTROL, 0, win32con.KEYEVENTF_KEYUP, 0)
        else:
            # Fallback - do nothing if no keyboard libraries available
            pass
    except Exception as e:
        # Silently fail if keyboard operation fails
        pass


def send_key(key):
    """Send a single key press.
    
    Args:
        key (str): The key to send (e.g., 'enter', 'tab', 'space')
    """
    try:
        if PYAUTOGUI_AVAILABLE:
            pyautogui.press(key)
        elif WIN32_AVAILABLE:
            # Map common keys to virtual key codes
            key_map = {
                'enter': win32con.VK_RETURN,
                'tab': win32con.VK_TAB,
                'space': win32con.VK_SPACE,
                'escape': win32con.VK_ESCAPE,
                'backspace': win32con.VK_BACK,
                'delete': win32con.VK_DELETE,
                'home': win32con.VK_HOME,
                'end': win32con.VK_END,
                'pageup': win32con.VK_PRIOR,
                'pagedown': win32con.VK_NEXT,
            }
            
            vk_code = key_map.get(key.lower(), ord(key.upper()))
            win32api.keybd_event(vk_code, 0, 0, 0)
            win32api.keybd_event(vk_code, 0, win32con.KEYEVENTF_KEYUP, 0)
        else:
            # Fallback - do nothing if no keyboard libraries available
            pass
    except Exception as e:
        # Silently fail if keyboard operation fails
        pass


def send_hotkey(*keys):
    """Send a combination of keys.
    
    Args:
        *keys: Variable number of keys to send together
    """
    try:
        if PYAUTOGUI_AVAILABLE:
            pyautogui.hotkey(*keys)
        elif WIN32_AVAILABLE:
            # For win32api, we need to handle this differently
            # This is a simplified implementation
            for key in keys:
                send_key(key)
        else:
            # Fallback - do nothing if no keyboard libraries available
            pass
    except Exception as e:
        # Silently fail if keyboard operation fails
        pass


def type_text(text):
    """Type text by sending individual characters.
    
    Args:
        text (str): The text to type
    """
    try:
        if PYAUTOGUI_AVAILABLE:
            pyautogui.typewrite(text)
        elif WIN32_AVAILABLE:
            # Type each character individually
            for char in text:
                if char.isupper():
                    win32api.keybd_event(win32con.VK_SHIFT, 0, 0, 0)
                    win32api.keybd_event(ord(char), 0, 0, 0)
                    win32api.keybd_event(ord(char), 0, win32con.KEYEVENTF_KEYUP, 0)
                    win32api.keybd_event(win32con.VK_SHIFT, 0, win32con.KEYEVENTF_KEYUP, 0)
                else:
                    win32api.keybd_event(ord(char.upper()), 0, 0, 0)
                    win32api.keybd_event(ord(char.upper()), 0, win32con.KEYEVENTF_KEYUP, 0)
        else:
            # Fallback - do nothing if no keyboard libraries available
            pass
    except Exception as e:
        # Silently fail if keyboard operation fails
        pass


# Unit test function
def unit_test():
    """Run unit tests for keyboard functionality."""
    print("Testing keyboard module...")
    
    # Test basic functionality
    print("Testing send_control_D...")
    send_control_D()
    
    print("Testing send_key...")
    send_key('enter')
    
    print("Testing send_hotkey...")
    send_hotkey('ctrl', 'c')
    
    print("Testing type_text...")
    type_text("Hello World")
    
    print("Keyboard module tests completed.")


if __name__ == "__main__":
    unit_test() 