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

def get_requirements():
    """Get list of required packages from requirements.txt or fallback list."""
    requirements = []
    requirements_file = current_dir / "src" / "requirements.txt"
    
    # Try to read from requirements.txt
    if requirements_file.exists():
        try:
            with open(requirements_file, 'r') as f:
                for line in f:
                    line = line.strip()
                    # Skip empty lines and comments
                    if line and not line.startswith('#'):
                        # Extract package name (remove version specifiers)
                        pkg = line.split('>=')[0].split('==')[0].split('<')[0].split('>')[0].strip()
                        if pkg:
                            requirements.append((pkg, line))  # (import_name, pip_name)
        except Exception as e:
            print(f"⚠️  Could not read requirements.txt: {e}")
    
    # Fallback to hardcoded list if no requirements found
    if not requirements:
        requirements = [("pywin32", "pywin32>=306")]
    
    return requirements

def install_dependency(package_spec):
    """Install a Python package using pip.
    
    Args:
        package_spec: Package specification (e.g., "pywin32>=306" or "pywin32")
    """
    import subprocess
    import sys
    
    package_name = package_spec.split('>=')[0].split('==')[0].split('<')[0].split('>')[0].strip()
    print(f"📦 Installing {package_name}...")
    try:
        # Use --upgrade to ensure we get the right version
        result = subprocess.run([
            sys.executable, "-m", "pip", "install", package_spec, "--upgrade"
        ], check=True, capture_output=True, text=True)
        print(f"✅ Successfully installed {package_name}")
        return True
    except subprocess.CalledProcessError as e:
        print(f"❌ Failed to install {package_name}")
        if e.stderr:
            print(f"   Error: {e.stderr.strip()}")
        return False

def check_and_install_dependencies():
    """Check if required dependencies are available and install if missing."""
    import importlib
    
    print("🔍 Checking dependencies...")
    
    # Get requirements
    requirements = get_requirements()
    missing_deps = []
    
    # Map of package names to their import names (if different)
    import_names = {
        'pywin32': 'win32com.client'
    }
    
    # Check each dependency
    for pkg_name, pkg_spec in requirements:
        import_name = import_names.get(pkg_name, pkg_name)
        try:
            # Try to import the module
            if '.' in import_name:
                # For nested imports like win32com.client
                parts = import_name.split('.')
                module = importlib.import_module(parts[0])
                for part in parts[1:]:
                    module = getattr(module, part)
            else:
                importlib.import_module(import_name)
            print(f"   ✓ {pkg_name} is installed")
        except (ImportError, AttributeError):
            print(f"   ✗ {pkg_name} is missing")
            missing_deps.append(pkg_spec)
    
    # Check standard library modules (these shouldn't need installation)
    try:
        import http.server  # noqa: F401
        import json  # noqa: F401
        import webbrowser  # noqa: F401
        import threading  # noqa: F401
        import time  # noqa: F401
    except ImportError:
        print("\n❌ Standard library modules not available.")
        print("   This might indicate a Python installation issue.")
        return False
    
    # Install missing dependencies
    if missing_deps:
        print(f"\n📥 Installing {len(missing_deps)} missing package(s)...")
        failed_deps = []
        
        for dep in missing_deps:
            if not install_dependency(dep):
                failed_deps.append(dep)
        
        if failed_deps:
            print(f"\n❌ Failed to install {len(failed_deps)} package(s):")
            for dep in failed_deps:
                print(f"   - {dep}")
            print("\n🔧 Please try installing manually:")
            print(f"   {sys.executable} -m pip install {' '.join(failed_deps)}")
            return False
        
        # Verify installation
        print("\n🔍 Verifying installation...")
        verification_failed = []
        
        for pkg_name, pkg_spec in requirements:
            import_name = import_names.get(pkg_name, pkg_name)
            try:
                if '.' in import_name:
                    parts = import_name.split('.')
                    module = importlib.import_module(parts[0])
                    for part in parts[1:]:
                        module = getattr(module, part)
                else:
                    importlib.import_module(import_name)
                print(f"   ✓ {pkg_name} verified")
            except (ImportError, AttributeError):
                verification_failed.append(pkg_name)
        
        if verification_failed:
            print(f"\n⚠️  Some packages were installed but couldn't be verified:")
            for pkg in verification_failed:
                print(f"   - {pkg}")
            print("\n💡 This is normal for some packages (like pywin32).")
            print("   If you encounter issues, please restart the application.")
    else:
        print("✅ All dependencies are already installed!")
    
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
