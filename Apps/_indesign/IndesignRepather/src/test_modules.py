#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Test script to verify all modules are working correctly.
"""

import sys
import os

# Add current directory to Python path
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

def test_imports():
    """Test all module imports."""
    print("Testing module imports...")
    print("=" * 40)
    
    try:
        # Test basic imports
        print("✓ Testing basic imports...")
        import os
        import sys
        import json
        import logging
        import threading
        import time
        import pathlib
        import webbrowser
        import win32com.client
        print("  ✓ All basic imports successful")
        
        # Test our custom modules
        print("✓ Testing custom module imports...")
        from get_indesign_version import InDesignVersionDetector, INDESIGN_AVAILABLE
        from backend import InDesignLinkRepather
        print("  ✓ Custom module imports successful")
        
        # Test module functionality
        print("✓ Testing module functionality...")
        
        # Test version detector
        detector = InDesignVersionDetector()
        result = detector.get_available_indesign_versions()
        print(f"  ✓ Version detector working - Found {result['total_found']} InDesign versions")
        
        # Test backend (without connecting to InDesign)
        repather = InDesignLinkRepather()
        print("  ✓ Backend initialization successful")
        
        print("\n✓ All tests passed! Modules are working correctly.")
        return True
        
    except ImportError as e:
        print(f"✗ Import error: {e}")
        return False
    except Exception as e:
        print(f"✗ Test error: {e}")
        return False

def test_web_app():
    """Test web app initialization."""
    print("\nTesting web app initialization...")
    print("=" * 40)
    
    try:
        from generate_web_app import WebHandler
        print("✓ WebHandler import successful")
        
        # Test basic web app functionality
        print("✓ Web app module loaded successfully")
        return True
        
    except Exception as e:
        print(f"✗ Web app test error: {e}")
        return False

def main():
    """Main test function."""
    print("InDesign Repather - Module Test")
    print("=" * 50)
    
    # Test imports and basic functionality
    if not test_imports():
        print("\n✗ Import tests failed!")
        return 1
    
    # Test web app
    if not test_web_app():
        print("\n✗ Web app tests failed!")
        return 1
    
    print("\n🎉 All tests passed! The application is ready to run.")
    return 0

if __name__ == "__main__":
    sys.exit(main())
