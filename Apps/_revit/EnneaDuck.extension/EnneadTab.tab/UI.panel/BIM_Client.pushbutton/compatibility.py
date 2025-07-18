#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""
Local compatibility module for BIM Client button.

This module provides compatibility fixes for Python 3.9+ issues
specifically for the BIM Client button without affecting the global
EnneadTab package.
"""

import sys
import warnings

def fix_collections_imports():
    """
    Fix collections import issues for Python 3.9+ compatibility.
    
    This function patches the collections module to include Callable
    and other ABCs that were moved to collections.abc in Python 3.9+.
    """
    try:
        import collections
        import collections.abc
        
        # Check if we need to patch collections module
        if not hasattr(collections, 'Callable'):
            # Add missing ABCs to collections module for backward compatibility
            missing_abcs = [
                'Callable', 'Awaitable', 'Coroutine', 'AsyncIterable', 
                'AsyncIterator', 'Iterable', 'Iterator', 'Reversible', 
                'Sized', 'Container', 'Collection', 'Set', 'MutableSet',
                'Mapping', 'MutableMapping', 'Sequence', 'MutableSequence',
                'MappingView', 'KeysView', 'ItemsView', 'ValuesView',
                'Generator', 'AsyncGenerator'
            ]
            
            for abc_name in missing_abcs:
                if hasattr(collections.abc, abc_name) and not hasattr(collections, abc_name):
                    setattr(collections, abc_name, getattr(collections.abc, abc_name))
            
            # Suppress deprecation warnings for collections imports
            warnings.filterwarnings('ignore', category=DeprecationWarning, 
                                  module='collections')
            
            print("✅ BIM Client: Collections compatibility patch applied for Python 3.9+")
            return True
        else:
            print("✅ BIM Client: Collections compatibility patch already applied")
            return True
            
    except Exception as e:
        print(f"❌ BIM Client: Failed to apply collections compatibility patch: {e}")
        return False

def check_python_version():
    """
    Check Python version and provide compatibility information.
    
    Returns:
        dict: Version information and compatibility status
    """
    version_info = {
        'version': sys.version,
        'major': sys.version_info.major,
        'minor': sys.version_info.minor,
        'micro': sys.version_info.micro,
        'is_python_39_plus': sys.version_info >= (3, 9),
        'is_python_310_plus': sys.version_info >= (3, 10),
        'compatibility_issues': []
    }
    
    if version_info['is_python_39_plus']:
        version_info['compatibility_issues'].append(
            'collections.Callable moved to collections.abc in Python 3.9+'
        )
    
    if version_info['is_python_310_plus']:
        version_info['compatibility_issues'].append(
            'collections aliases removed in Python 3.10+'
        )
    
    return version_info

def apply_compatibility_fixes():
    """
    Apply all known compatibility fixes for the current Python version.
    
    Returns:
        bool: True if fixes were applied successfully
    """
    version_info = check_python_version()
    
    print(f"BIM Client - Python version: {version_info['version']}")
    print(f"BIM Client - Compatibility issues detected: {len(version_info['compatibility_issues'])}")
    
    if version_info['compatibility_issues']:
        for issue in version_info['compatibility_issues']:
            print(f"  - {issue}")
    
    # Apply collections compatibility fix if needed
    if version_info['is_python_39_plus']:
        return fix_collections_imports()
    
    return True

# Auto-apply fixes when module is imported
if __name__ != "__main__":
    apply_compatibility_fixes() 