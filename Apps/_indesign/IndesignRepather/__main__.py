#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
InDesign Repather - Main Entry Point
This module allows the IndesignRepather to be run as a Python package.

Usage:
    python -m IndesignRepather
    or
    python IndesignRepather
"""

import sys
import logging
from pathlib import Path

# Add the src directory to Python path
current_dir = Path(__file__).parent
src_dir = current_dir / "src"
sys.path.insert(0, str(src_dir))

def setup_logging():
    """Setup logging configuration."""
    # Create log file in the parent directory (user-facing)
    log_path = current_dir / "indesign_repath.log"
    logging.basicConfig(
        level=logging.INFO,
        format='%(asctime)s - %(levelname)s - %(message)s',
        handlers=[
            logging.FileHandler(log_path),
            logging.StreamHandler()
        ]
    )
    return logging.getLogger(__name__)

def install_dependency(package_name):
    """Install a Python package using pip."""
    import subprocess
    import sys
    
    print(f"📦 Installing {package_name}...")
    try:
        result = subprocess.run([
            sys.executable, "-m", "pip", "install", package_name, "--quiet"
        ], check=True, capture_output=True, text=True)
        print(f"✅ Successfully installed {package_name}")
        return True
    except subprocess.CalledProcessError as e:
        print(f"❌ Failed to install {package_name}: {e}")
        return False

def check_and_install_dependencies():
    """Check if required dependencies are available and install if missing."""
    missing_deps = []
    
    # Check pywin32
    try:
        import win32com.client  # noqa: F401
    except ImportError:
        missing_deps.append("pywin32")
    
    # Check standard library modules (these shouldn't need installation)
    try:
        import http.server  # noqa: F401
        import json  # noqa: F401
        import webbrowser  # noqa: F401
        import threading  # noqa: F401
        import time  # noqa: F401
    except ImportError:
        print("❌ Standard library modules not available. This might indicate a Python installation issue.")
        return False
    
    # Install missing dependencies
    if missing_deps:
        print("🔍 Checking dependencies...")
        for dep in missing_deps:
            if not install_dependency(dep):
                print(f"\n❌ Failed to install {dep}")
                print("🔧 Please try installing manually:")
                print(f"   pip install {dep}")
                return False
        
        # Verify installation (pywin32 may need a restart to work properly)
        print("🔍 Verifying installation...")
        try:
            import win32com.client  # noqa: F401
            print("✅ All dependencies verified successfully!")
        except ImportError:
            print("⚠️  pywin32 was installed but may need a Python restart to work properly.")
            print("✅ Installation completed - please restart the application if you encounter issues.")
            # Don't fail here, as pywin32 installation might work after restart
    
    return True

def main():
    """Main entry point for the IndesignRepather application."""
    print("=" * 60)
    print("🔍 EnneadTab InDesign Repather")
    print("   Professional Link Management Tool")
    print("=" * 60)
    print()
    
    # Setup logging
    logger = setup_logging()
    
    # Check and install dependencies
    if not check_and_install_dependencies():
        print("\n❌ Dependency check/installation failed.")
        input("\nPress Enter to exit...")
        return 1
    
    print("✅ All dependencies ready!")
    print()
    
    # Import and start the web application
    try:
        print("🚀 Starting InDesign Repather...")
        from generate_web_app import start_server  # type: ignore
        start_server()
    except ImportError as e:
        print(f"❌ Failed to import web application: {e}")
        print("Make sure all required files are present in the src/ directory.")
        input("\nPress Enter to exit...")
        return 1
    except Exception as e:
        print(f"❌ Failed to start application: {e}")
        logger.error(f"Application startup failed: {e}")
        input("\nPress Enter to exit...")
        return 1
    
    return 0

if __name__ == "__main__":
    sys.exit(main())
