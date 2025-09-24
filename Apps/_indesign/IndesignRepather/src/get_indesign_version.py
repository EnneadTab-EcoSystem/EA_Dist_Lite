#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
InDesign Version Detection Module
Standalone module to detect available InDesign versions on the machine.
"""

import os
import sys
import logging
from typing import List, Dict

# Add current directory to Python path for imports
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

# Import InDesign COM objects
import win32com.client
INDESIGN_AVAILABLE = True

class InDesignVersionDetector:
    """Class for detecting InDesign versions on the machine."""
    
    def __init__(self):
        self.setup_logging()
        
    def setup_logging(self):
        """Setup logging configuration."""
        # Only setup logging once
        if not logging.getLogger().handlers:
            logging.basicConfig(
                level=logging.INFO,
                format='%(asctime)s - %(levelname)s - %(message)s',
                handlers=[
                    logging.StreamHandler()
                ]
            )
        self.logger = logging.getLogger(__name__)
        
    def get_available_indesign_versions(self) -> Dict:
        """Get all available InDesign versions on the machine."""
        versions = []
        errors = []
        
        try:
            import winreg
            
            # First, try to detect running instances
            try:
                if INDESIGN_AVAILABLE:
                    app = win32com.client.GetActiveObject("InDesign.Application")
                    versions.append({
                        'version': 'Currently Running Instance',
                        'path': 'Active Instance',
                        'registry_path': 'active'
                    })
                    self.logger.info("Found running InDesign instance")
                else:
                    errors.append("pywin32 not available - cannot detect running instances")
            except Exception as e:
                error_msg = f"No running InDesign instance found"
                if "Operation unavailable" in str(e):
                    error_msg += " (InDesign is not currently running)"
                elif "Class not registered" in str(e):
                    error_msg += " (InDesign COM registration issue)"
                else:
                    error_msg += f" ({str(e)})"
                errors.append(error_msg)
                self.logger.info(error_msg)
            
            # Check registry for installed versions
            try:
                with winreg.OpenKey(winreg.HKEY_LOCAL_MACHINE, r"SOFTWARE\Adobe\InDesign") as key:
                    i = 0
                    while True:
                        try:
                            version_key = winreg.EnumKey(key, i)
                            version_path = f"SOFTWARE\\Adobe\\InDesign\\{version_key}"
                            
                            try:
                                with winreg.OpenKey(winreg.HKEY_LOCAL_MACHINE, version_path) as version_reg:
                                    # Try to get version info
                                    version_name = f"InDesign {version_key}"
                                    install_path = "Unknown"
                                    
                                    # Try to get install path from common registry values
                                    for value_name in ["InstallPath", "InstallLocation", "Path"]:
                                        try:
                                            install_path = winreg.QueryValueEx(version_reg, value_name)[0]
                                            break
                                        except FileNotFoundError:
                                            continue
                                    
                                    versions.append({
                                        'version': version_name,
                                        'path': install_path,
                                        'registry_path': version_path
                                    })
                                    self.logger.info(f"Found InDesign {version_key}")
                            except Exception as e:
                                error_msg = f"Error reading version {version_key}: {str(e)}"
                                errors.append(error_msg)
                                self.logger.warning(error_msg)
                                
                            i += 1
                        except:
                            break
            except FileNotFoundError:
                error_msg = "InDesign not found in registry - InDesign may not be installed"
                errors.append(error_msg)
                self.logger.warning(error_msg)
            except PermissionError:
                error_msg = "Permission denied accessing registry - try running as administrator"
                errors.append(error_msg)
                self.logger.warning(error_msg)
            except Exception as e:
                error_msg = f"Error accessing InDesign registry: {str(e)}"
                errors.append(error_msg)
                self.logger.warning(error_msg)
            
            # If no versions found, try to create a new instance
            if not versions and INDESIGN_AVAILABLE:
                try:
                    app = win32com.client.Dispatch("InDesign.Application")
                    versions.append({
                        'version': 'Available for Launch',
                        'path': 'Will create new instance',
                        'registry_path': 'new'
                    })
                    self.logger.info("InDesign available for new instance creation")
                except Exception as e:
                    error_msg = f"Cannot create new InDesign instance: {str(e)}"
                    if "Class not registered" in str(e):
                        error_msg = "InDesign COM not registered - InDesign may not be properly installed"
                    elif "Access is denied" in str(e):
                        error_msg = "Access denied - try running as administrator"
                    errors.append(error_msg)
                    self.logger.warning(error_msg)
            
            # Store errors in the return data for better user feedback
            result = {
                'versions': versions,
                'errors': errors,
                'total_found': len(versions)
            }
            
            self.logger.info(f"Found {len(versions)} InDesign versions")
            return result
            
        except Exception as e:
            error_msg = f"Critical error getting InDesign versions: {str(e)}"
            self.logger.error(error_msg)
            return {
                'versions': [],
                'errors': [error_msg],
                'total_found': 0
            }

def test_version_detection():
    """Test function for version detection."""
    print("=== Testing InDesign Version Detection ===")
    
    detector = InDesignVersionDetector()
    result = detector.get_available_indesign_versions()
    
    print(f"\nFound {result['total_found']} InDesign version(s):")
    for i, version in enumerate(result['versions'], 1):
        print(f"{i}. {version['version']}")
        print(f"   Path: {version['path']}")
        print(f"   Registry: {version['registry_path']}")
        print()
    
    if result['errors']:
        print("Errors encountered:")
        for error in result['errors']:
            print(f"  - {error}")
        print()
    
    return result

if __name__ == "__main__":
    test_version_detection()
