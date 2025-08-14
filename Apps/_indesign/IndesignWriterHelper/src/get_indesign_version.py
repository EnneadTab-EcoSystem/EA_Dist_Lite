#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
InDesign Version Detector and Connection Module
Handles InDesign version detection and connection management.
"""

import os
import sys
import json
import logging
import win32com.client
from typing import List, Dict, Optional, Tuple

class InDesignVersionDetector:
    """Detects and manages InDesign versions and connections."""
    
    def __init__(self):
        self.logger = self._setup_logging()
        self.versions = []
        self.current_app = None
        
    def _setup_logging(self):
        """Setup logging configuration."""
        logging.basicConfig(
            level=logging.INFO,
            format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
        )
        return logging.getLogger(__name__)
    
    def detect_versions(self) -> List[Dict]:
        """Detect all installed InDesign versions."""
        self.logger.info("Detecting InDesign versions...")
        
        # Common InDesign version registry paths
        version_paths = [
            r"SOFTWARE\Adobe\InDesign\Version 18.0\InstallPath",
            r"SOFTWARE\Adobe\InDesign\Version 17.0\InstallPath", 
            r"SOFTWARE\Adobe\InDesign\Version 16.0\InstallPath",
            r"SOFTWARE\Adobe\InDesign\Version 15.0\InstallPath",
            r"SOFTWARE\Adobe\InDesign\Version 14.0\InstallPath",
            r"SOFTWARE\Adobe\InDesign\Version 13.0\InstallPath",
            r"SOFTWARE\Adobe\InDesign\Version 12.0\InstallPath",
            r"SOFTWARE\Adobe\InDesign\Version 11.0\InstallPath",
            r"SOFTWARE\Adobe\InDesign\Version 10.0\InstallPath",
            r"SOFTWARE\Adobe\InDesign\Version 9.0\InstallPath",
            r"SOFTWARE\Adobe\InDesign\Version 8.0\InstallPath",
            r"SOFTWARE\Adobe\InDesign\Version 7.0\InstallPath",
            r"SOFTWARE\Adobe\InDesign\Version 6.0\InstallPath",
            r"SOFTWARE\Adobe\InDesign\Version 5.0\InstallPath",
            r"SOFTWARE\Adobe\InDesign\Version 4.0\InstallPath",
            r"SOFTWARE\Adobe\InDesign\Version 3.0\InstallPath",
            r"SOFTWARE\Adobe\InDesign\Version 2.0\InstallPath",
            r"SOFTWARE\Adobe\InDesign\Version 1.0\InstallPath",
        ]
        
        detected_versions = []
        
        try:
            import winreg
            
            for path in version_paths:
                try:
                    # Try 64-bit registry first
                    key = winreg.OpenKey(winreg.HKEY_LOCAL_MACHINE, path, 0, winreg.KEY_READ | winreg.KEY_WOW64_64KEY)
                    install_path = winreg.QueryValueEx(key, "")[0]
                    winreg.CloseKey(key)
                    
                    # Extract version from path
                    version = path.split("Version ")[1].split("\\")[0]
                    
                    # Check if executable exists
                    exe_path = os.path.join(install_path, "InDesign.exe")
                    if os.path.exists(exe_path):
                        detected_versions.append({
                            "version": version,
                            "path": install_path,
                            "exe_path": exe_path,
                            "name": f"InDesign {version}"
                        })
                        self.logger.info(f"Found InDesign {version} at {install_path}")
                        
                except (FileNotFoundError, OSError):
                    # Try 32-bit registry
                    try:
                        key = winreg.OpenKey(winreg.HKEY_LOCAL_MACHINE, path, 0, winreg.KEY_READ | winreg.KEY_WOW64_32KEY)
                        install_path = winreg.QueryValueEx(key, "")[0]
                        winreg.CloseKey(key)
                        
                        version = path.split("Version ")[1].split("\\")[0]
                        exe_path = os.path.join(install_path, "InDesign.exe")
                        
                        if os.path.exists(exe_path):
                            detected_versions.append({
                                "version": version,
                                "path": install_path,
                                "exe_path": exe_path,
                                "name": f"InDesign {version}"
                            })
                            self.logger.info(f"Found InDesign {version} at {install_path}")
                            
                    except (FileNotFoundError, OSError):
                        continue
                        
        except ImportError:
            self.logger.warning("winreg module not available, trying COM detection...")
            detected_versions = self._detect_via_com()
        
        self.versions = detected_versions
        return detected_versions
    
    def _detect_via_com(self) -> List[Dict]:
        """Detect InDesign via COM objects."""
        detected_versions = []
        
        # Try different InDesign COM object names
        com_names = [
            "InDesign.Application.18.0",
            "InDesign.Application.17.0", 
            "InDesign.Application.16.0",
            "InDesign.Application.15.0",
            "InDesign.Application.14.0",
            "InDesign.Application.13.0",
            "InDesign.Application.12.0",
            "InDesign.Application.11.0",
            "InDesign.Application.10.0",
            "InDesign.Application.9.0",
            "InDesign.Application.8.0",
            "InDesign.Application.7.0",
            "InDesign.Application.6.0",
            "InDesign.Application.5.0",
            "InDesign.Application.4.0",
            "InDesign.Application.3.0",
            "InDesign.Application.2.0",
            "InDesign.Application.1.0",
        ]
        
        for com_name in com_names:
            try:
                app = win32com.client.Dispatch(com_name)
                version = com_name.split(".")[-1]
                detected_versions.append({
                    "version": version,
                    "path": "Unknown",
                    "exe_path": "Unknown", 
                    "name": f"InDesign {version}",
                    "com_name": com_name
                })
                self.logger.info(f"Found InDesign {version} via COM")
                break  # Use the first working version
            except Exception:
                continue
                
        return detected_versions
    
    def connect_to_indesign(self, version_info: Optional[Dict] = None) -> Optional[object]:
        """Connect to InDesign application."""
        try:
            if version_info and "com_name" in version_info:
                # Use specific COM object
                self.current_app = win32com.client.Dispatch(version_info["com_name"])
            else:
                # Try to connect to running instance first
                try:
                    self.current_app = win32com.client.GetActiveObject("InDesign.Application")
                    self.logger.info("Connected to running InDesign instance")
                except:
                    # Create new instance
                    self.current_app = win32com.client.Dispatch("InDesign.Application")
                    self.logger.info("Created new InDesign instance")
            
            return self.current_app
            
        except Exception as e:
            self.logger.error(f"Failed to connect to InDesign: {e}")
            return None
    
    def get_running_instances(self) -> List[Dict]:
        """Get information about running InDesign instances."""
        running_instances = []
        
        try:
            # Try to get running instances via COM
            app = win32com.client.GetActiveObject("InDesign.Application")
            running_instances.append({
                "version": "Running Instance",
                "path": "Active",
                "exe_path": "Active",
                "name": "Running InDesign",
                "is_running": True
            })
        except:
            pass
            
        return running_instances
    
    def get_document_info(self) -> Optional[Dict]:
        """Get information about the current document."""
        if not self.current_app:
            return None
            
        try:
            doc = self.current_app.ActiveDocument
            if doc:
                return {
                    "name": doc.Name,
                    "path": doc.FilePath,
                    "full_path": os.path.join(doc.FilePath, doc.Name) if doc.FilePath else None,
                    "pages_count": doc.Pages.Count,
                    "text_frames_count": len(doc.TextFrames),
                    "is_saved": doc.Saved
                }
        except Exception as e:
            self.logger.error(f"Failed to get document info: {e}")
            
        return None
