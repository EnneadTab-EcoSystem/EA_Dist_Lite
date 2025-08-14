#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Module Checker for InDesign Writer Helper
Checks and installs required modules dynamically.
"""

import sys
import subprocess
import importlib

def check_and_install_module(module_name, pip_name=None, is_builtin=False):
    """Check if a module is available and install if needed."""
    if pip_name is None:
        pip_name = module_name
        
    try:
        importlib.import_module(module_name)
        print(f"✓ {module_name} already available")
        return True
    except ImportError:
        if is_builtin:
            print(f"✗ ERROR: {module_name} is a built-in module but not available")
            print(f"  This indicates a Python installation issue")
            return False
        else:
            print(f"✗ {module_name} not found, installing {pip_name}...")
            try:
                subprocess.check_call([sys.executable, "-m", "pip", "install", pip_name])
                print(f"✓ {pip_name} installed successfully")
                return True
            except subprocess.CalledProcessError as e:
                print(f"✗ Failed to install {pip_name}: {e}")
                return False

def main():
    """Main function to check all required modules."""
    # First check if Python is available
    try:
        import subprocess
        result = subprocess.run(['python', '--version'], capture_output=True, text=True, check=True)
        print(f"Python version: {result.stdout.strip()}")
    except (subprocess.CalledProcessError, FileNotFoundError):
        print("ERROR: Python is not installed on this computer.")
        print("Please install Python 3.13 from the Microsoft Store:")
        print("https://www.microsoft.com/store/apps/9PJPW5LDXLZ5")
        return 1
    
    print("Checking required modules for InDesign Writer Helper...")
    print("=" * 50)
    
    # Define required modules
    modules = [
        # External modules - optional for now
        ("win32com", "pywin32", False),
        
        # Built-in modules (should always be available)
        ("os", None, True),
        ("sys", None, True),
        ("json", None, True),
        ("logging", None, True),
        ("threading", None, True),
        ("time", None, True),
        ("pathlib", None, True),
        ("webbrowser", None, True),
        ("typing", None, True),
    ]
    
    all_ok = True
    
    for module_name, pip_name, is_builtin in modules:
        if not check_and_install_module(module_name, pip_name, is_builtin):
            all_ok = False
        print()
    
    if all_ok:
        print("✓ All required modules are available!")
        return 0
    else:
        print("✗ Some modules could not be installed.")
        print("Please check the errors above and try again.")
        return 1

if __name__ == "__main__":
    sys.exit(main())
