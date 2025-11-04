#!/usr/bin/python
# -*- coding: utf-8 -*-

"""
Config Loader for SparcHealth

Loads configuration from config.json and provides helper functions
to access configuration data for both orchestrator and Revit scripts.
"""

import os
import json

# Global config cache
_config_cache = None
_script_dir = os.path.dirname(os.path.abspath(__file__))


def load_config(force_reload=False):
    """Load configuration from config.json
    
    Args:
        force_reload: If True, reload config from disk even if cached
        
    Returns:
        dict: Configuration dictionary
    """
    global _config_cache
    
    if _config_cache is not None and not force_reload:
        return _config_cache
    
    config_file = os.path.join(_script_dir, "config.json")
    
    if not os.path.exists(config_file):
        raise RuntimeError("Config file not found: {}".format(config_file))
    
    with open(config_file, 'r') as f:
        _config_cache = json.load(f)
    
    # Expand {username} placeholders
    username = os.environ.get('USERNAME', os.environ.get('USER', ''))
    _expand_placeholders(_config_cache, username)
    
    return _config_cache


def _expand_placeholders(obj, username):
    """Recursively expand {username} placeholders in config"""
    if isinstance(obj, dict):
        for key, value in obj.items():
            if isinstance(value, str):
                obj[key] = value.replace('{username}', username)
            else:
                _expand_placeholders(value, username)
    elif isinstance(obj, list):
        for i, item in enumerate(obj):
            if isinstance(item, str):
                obj[i] = item.replace('{username}', username)
            else:
                _expand_placeholders(item, username)


def get_models():
    """Get list of models from config
    
    Returns:
        list: List of model dictionaries
    """
    config = load_config()
    return config.get('models', [])


def get_project_info():
    """Get project information from config
    
    Returns:
        dict: Project info dictionary
    """
    config = load_config()
    return config.get('project', {})


def get_output_settings():
    """Get output settings from config
    
    Returns:
        dict: Output settings dictionary
    """
    config = load_config()
    return config.get('output', {})


def get_orchestrator_settings():
    """Get orchestrator settings from config
    
    Returns:
        dict: Orchestrator settings dictionary
    """
    config = load_config()
    return config.get('orchestrator', {})


def get_path_settings():
    """Get path settings from config
    
    Returns:
        dict: Path settings dictionary
    """
    config = load_config()
    return config.get('paths', {})


def get_heartbeat_settings():
    """Get heartbeat settings from config
    
    Returns:
        dict: Heartbeat settings dictionary
    """
    config = load_config()
    return config.get('heartbeat', {})


def get_current_job_payload():
    """Read current job payload file
    
    Returns:
        dict: Payload data or None if file doesn't exist
    """
    payload_file = os.path.join(_script_dir, "current_job_payload.json")
    
    if not os.path.exists(payload_file):
        return None
    
    try:
        with open(payload_file, 'r') as f:
            return json.load(f)
    except Exception as e:
        print("Failed to read payload file: {}".format(e))
        return None


def get_current_model_data():
    """Get current model data from payload file
    
    Returns:
        dict: Model data dictionary or None
    """
    payload = get_current_job_payload()
    if not payload:
        return None
    
    return payload.get('model_data')


def get_current_job_id():
    """Get current job ID from payload file
    
    Returns:
        str: Job ID or None
    """
    payload = get_current_job_payload()
    if not payload:
        return None
    
    return payload.get('job_id')


def get_current_model_name():
    """Get current model name from payload file
    
    Returns:
        str: Model name or None
    """
    payload = get_current_job_payload()
    if not payload:
        return None
    
    model_data = payload.get('model_data', {})
    return model_data.get('name')

