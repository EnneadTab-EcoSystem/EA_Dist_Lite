#!/usr/bin/env python3
"""
EnneadTab InDesign Writer Helper - Module Checker
This script checks and installs required Python modules
"""

import sys
import subprocess
import importlib
import os

def print_status(message, status="INFO"):
    """Print status message with color coding"""
    colors = {
        "ERROR": "\033[91m",    # Red
        "SUCCESS": "\033[92m",  # Green
        "WARNING": "\033[93m",  # Yellow
        "INFO": "\033[94m"      # Blue
    }
    end_color = "\033[0m"
    
    status_symbols = {
        "ERROR": "❌",
        "SUCCESS": "✅",
        "WARNING": "⚠️",
        "INFO": "ℹ️"
    }
    
    color = colors.get(status, colors["INFO"])
    symbol = status_symbols.get(status, "ℹ️")
    print(f"{color}{symbol} {message}{end_color}")

def check_module(module_name, pip_name=None):
    """Check if a module is available, install if missing"""
    if pip_name is None:
        pip_name = module_name
    
    try:
        importlib.import_module(module_name)
        print_status(f"{module_name} is available", "SUCCESS")
        return True
    except ImportError:
        print_status(f"{module_name} not found, attempting to install...", "WARNING")
        
        try:
            # Try to install the module
            subprocess.check_call([
                sys.executable, "-m", "pip", "install", pip_name
            ], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
            
            # Try importing again
            importlib.import_module(module_name)
            print_status(f"{module_name} installed successfully", "SUCCESS")
            return True
            
        except (subprocess.CalledProcessError, ImportError) as e:
            print_status(f"Failed to install {module_name}: {str(e)}", "ERROR")
            return False

def main():
    """Main function to check and install required modules"""
    print("🔍 Checking required Python modules...")
    print()
    
    # List of required modules with their pip names
    required_modules = [
        ("flask", "flask"),
        ("win32com", "pywin32"),
        ("requests", "requests"),
        ("jinja2", "jinja2"),
        ("werkzeug", "werkzeug")
    ]
    
    all_modules_ok = True
    
    for module_name, pip_name in required_modules:
        if not check_module(module_name, pip_name):
            all_modules_ok = False
        print()
    
    if all_modules_ok:
        print_status("All required modules are available!", "SUCCESS")
        return 0
    else:
        print_status("Some modules could not be installed. Please install them manually:", "ERROR")
        print("  pip install flask pywin32 requests jinja2 werkzeug")
        return 1

if __name__ == "__main__":
    try:
        exit_code = main()
        sys.exit(exit_code)
    except KeyboardInterrupt:
        print("\n❌ Installation cancelled by user")
        sys.exit(1)
    except Exception as e:
        print_status(f"Unexpected error: {str(e)}", "ERROR")
        sys.exit(1)
