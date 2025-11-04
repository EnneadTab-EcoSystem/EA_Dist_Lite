# -*- coding: utf-8 -*-
"""
Export Helper Functions - Validation and Utilities
"""

import os
import time
import traceback


def validate_export(file_path, min_size_kb=10):
    """
    Validate exported file exists and has reasonable size.
    
    Args:
        file_path: Path to exported file
        min_size_kb: Minimum file size in KB (default 10KB)
    
    Returns:
        (is_valid, error_message) tuple
    """
    try:
        if not os.path.exists(file_path):
            return False, "File not created"
        
        size_bytes = os.path.getsize(file_path)
        size_kb = size_bytes / 1024.0
        
        if size_kb < min_size_kb:
            return False, "File too small ({:.1f}KB)".format(size_kb)
        
        return True, None
        
    except Exception as e:
        return False, "Validation error: {}".format(str(e))


def ensure_export_directory(base_path, export_type):
    """
    Create export directory if it doesn't exist.
    
    Args:
        base_path: Base output directory
        export_type: Type of export ("images", "pdfs", "dwgs")
    
    Returns:
        Full path to export directory
    """
    export_dir = os.path.join(base_path, export_type)
    if not os.path.exists(export_dir):
        os.makedirs(export_dir)
    return export_dir


def cleanup_failed_export(file_path):
    """
    Remove corrupt/partial files after export failure.
    Best-effort cleanup - never raises exceptions.
    
    Args:
        file_path: Path to file to remove
    """
    try:
        if os.path.exists(file_path):
            os.remove(file_path)
            print("Cleaned up failed export: {}".format(file_path))
    except Exception:
        pass  # Best effort cleanup


def safe_filename(sheet_number, sheet_name):
    """
    Create a safe filename from sheet number and name.
    Removes invalid characters for file systems.
    
    Args:
        sheet_number: Sheet number
        sheet_name: Sheet name
    
    Returns:
        Safe filename string (without extension)
    """
    # Combine sheet number and name
    combined = "{}_{}".format(sheet_number, sheet_name)
    
    # Replace invalid characters
    invalid_chars = ['<', '>', ':', '"', '/', '\\', '|', '?', '*']
    for char in invalid_chars:
        combined = combined.replace(char, '_')
    
    # Remove multiple consecutive underscores
    while '__' in combined:
        combined = combined.replace('__', '_')
    
    # Trim to reasonable length (max 200 chars)
    if len(combined) > 200:
        combined = combined[:200]
    
    return combined


def format_duration(seconds):
    """Format duration in readable format"""
    if seconds < 60:
        return "{:.1f}s".format(seconds)
    elif seconds < 3600:
        minutes = int(seconds // 60)
        secs = int(seconds % 60)
        return "{}m {}s".format(minutes, secs)
    else:
        hours = int(seconds // 3600)
        minutes = int((seconds % 3600) // 60)
        return "{}h {}m".format(hours, minutes)


def format_file_size(bytes_size):
    """Format file size in readable format"""
    if bytes_size < 1024:
        return "{} bytes".format(bytes_size)
    elif bytes_size < 1024 * 1024:
        kb = bytes_size / 1024.0
        return "{:.2f} KB".format(kb)
    elif bytes_size < 1024 * 1024 * 1024:
        mb = bytes_size / (1024.0 * 1024.0)
        return "{:.2f} MB".format(mb)
    else:
        gb = bytes_size / (1024.0 * 1024.0 * 1024.0)
        return "{:.2f} GB".format(gb)


def track_export_timing(func):
    """
    Decorator to track execution time of export functions.
    Returns (result, duration) tuple.
    
    Usage:
        @track_export_timing
        def export_func():
            # ... export logic
            return result
        
        result, duration = export_func()
    """
    def wrapper(*args, **kwargs):
        start_time = time.time()
        result = func(*args, **kwargs)
        duration = time.time() - start_time
        return result, duration
    return wrapper

