#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
InDesign Backend Module
Handles InDesign operations and link repathing functionality.
"""

import os
import sys
import logging
from pathlib import Path
from typing import List, Dict, Optional

# Add current directory to Python path for imports
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

# Import version detection
from get_indesign_version import INDESIGN_AVAILABLE
import win32com.client

class InDesignLinkRepather:
    """Main class for handling InDesign link repathing operations."""
    
    def __init__(self):
        self.app = None
        self.doc = None
        self.setup_logging()
        
    def setup_logging(self):
        """Setup logging configuration."""
        # Only setup logging once
        if not logging.getLogger().handlers:
            # Create log file in parent directory (user-facing)
            log_path = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), 'indesign_repath.log')
            logging.basicConfig(
                level=logging.INFO,
                format='%(asctime)s - %(levelname)s - %(message)s',
                handlers=[
                    logging.FileHandler(log_path),
                    logging.StreamHandler()
                ]
            )
        self.logger = logging.getLogger(__name__)
        
    def connect_to_indesign(self, version_path=None):
        """Connect to InDesign application."""
        if not INDESIGN_AVAILABLE:
            raise Exception("InDesign COM integration not available. Please install pywin32: pip install pywin32")
            
        try:
            if version_path and version_path != 'active':
                # Try to connect to specific version
                self.app = win32com.client.Dispatch("InDesign.Application")
                # Note: COM doesn't allow direct version selection, but we can try
                # to ensure we're connecting to the right instance
            else:
                # Try to get active instance first, then create new
                try:
                    self.app = win32com.client.GetActiveObject("InDesign.Application")
                    self.logger.info("Connected to active InDesign instance")
                except Exception as e:
                    if "Operation unavailable" in str(e):
                        # No active instance, create new one
                        self.app = win32com.client.Dispatch("InDesign.Application")
                        self.logger.info("Created new InDesign instance")
                    else:
                        raise Exception(f"Failed to connect to InDesign: {str(e)}")
                    
            self.logger.info("Successfully connected to InDesign")
            return True
        except Exception as e:
            error_msg = str(e)
            if "Class not registered" in error_msg:
                raise Exception("InDesign COM not registered. Please ensure InDesign is properly installed and try running as administrator.")
            elif "Access is denied" in error_msg:
                raise Exception("Access denied. Please try running the application as administrator.")
            elif "The system cannot find the file specified" in error_msg:
                raise Exception("InDesign executable not found. Please ensure InDesign is properly installed.")
            else:
                raise Exception(f"Failed to connect to InDesign: {error_msg}")
            
    def open_document(self, file_path: str):
        """Open an InDesign document."""
        try:
            if not self.app:
                raise Exception("Not connected to InDesign. Please connect first.")
                
            if not os.path.exists(file_path):
                raise FileNotFoundError(f"Document not found: {file_path}")
                
            if not file_path.lower().endswith('.indd'):
                raise ValueError("File must be an InDesign document (.indd)")
                
            self.doc = self.app.Open(file_path)
            self.logger.info(f"Opened document: {file_path}")
            return True
        except FileNotFoundError:
            raise Exception(f"Document not found: {file_path}")
        except ValueError as e:
            raise Exception(str(e))
        except Exception as e:
            error_msg = str(e)
            if "Access is denied" in error_msg:
                raise Exception("Access denied to document. Please ensure the file is not open in another application.")
            elif "The file is corrupted" in error_msg:
                raise Exception("The InDesign document appears to be corrupted.")
            elif "The file format is not supported" in error_msg:
                raise Exception("File format not supported. Please ensure it's a valid InDesign document.")
            else:
                raise Exception(f"Failed to open document: {error_msg}")
            
    def get_all_links(self) -> List[Dict]:
        """Get all links in the current document."""
        links = []
        try:
            if not self.app:
                raise Exception("Not connected to InDesign. Please connect first.")
                
            if not self.doc:
                raise Exception("No document is open. Please open a document first.")
                
            # Get all links in the document
            all_links = self.doc.Links
            
            for i in range(all_links.Count):
                link = all_links.Item(i)
                link_info = {
                    'name': link.Name,
                    'file_path': link.FilePath,
                    'status': link.LinkStatus,
                    'index': i
                }
                links.append(link_info)
                
            self.logger.info(f"Found {len(links)} links in document")
            return links
            
        except Exception as e:
            error_msg = str(e)
            if "Object reference not set" in error_msg:
                raise Exception("Document connection lost. Please reconnect to InDesign and open the document again.")
            elif "Access is denied" in error_msg:
                raise Exception("Access denied to document links. Please ensure the document is not locked.")
            else:
                raise Exception(f"Failed to get links: {error_msg}")
            
    def repath_links(self, old_folder: str, new_folder: str) -> Dict:
        """Repath all links by replacing old folder with new folder."""
        results = {
            'success': 0,
            'failed': 0,
            'skipped': 0,
            'details': []
        }
        
        try:
            links = self.get_all_links()
            
            for link_info in links:
                try:
                    link = self.doc.Links.Item(link_info['index'])
                    current_path = link.FilePath
                    
                    # Check if the link path contains the old folder
                    if old_folder.lower() in current_path.lower():
                        # Create new path by replacing old folder with new folder
                        new_path = current_path.replace(old_folder, new_folder)
                        new_path = new_path.replace(old_folder.lower(), new_folder)
                        
                        # Check if new file exists
                        if os.path.exists(new_path):
                            # Update the link
                            link.Relink(new_path)
                            results['success'] += 1
                            results['details'].append({
                                'name': link_info['name'],
                                'old_path': current_path,
                                'new_path': new_path,
                                'status': 'success'
                            })
                            self.logger.info(f"Successfully repathed: {link_info['name']}")
                        else:
                            results['failed'] += 1
                            results['details'].append({
                                'name': link_info['name'],
                                'old_path': current_path,
                                'new_path': new_path,
                                'status': 'file_not_found'
                            })
                            self.logger.warning(f"New file not found: {new_path}")
                    else:
                        results['skipped'] += 1
                        results['details'].append({
                            'name': link_info['name'],
                            'old_path': current_path,
                            'new_path': None,
                            'status': 'skipped'
                        })
                        
                except Exception as e:
                    results['failed'] += 1
                    results['details'].append({
                        'name': link_info['name'],
                        'old_path': current_path if 'current_path' in locals() else 'unknown',
                        'new_path': None,
                        'status': f'error: {str(e)}'
                    })
                    self.logger.error(f"Failed to repath link {link_info['name']}: {e}")
                    
            self.logger.info(f"Repathing complete: {results['success']} success, {results['failed']} failed, {results['skipped']} skipped")
            return results
            
        except Exception as e:
            self.logger.error(f"Failed to repath links: {e}")
            raise
            
    def close_document(self):
        """Close the current document."""
        try:
            if self.doc:
                self.doc.Close()
                self.doc = None
                self.logger.info("Document closed")
        except Exception as e:
            self.logger.error(f"Failed to close document: {e}")
            
    def get_document_info(self) -> Dict:
        """Get information about the current document."""
        if not self.doc:
            return {'error': 'No document is open'}
            
        try:
            return {
                'name': self.doc.Name,
                'file_path': self.doc.FilePath,
                'modified': self.doc.Modified,
                'saved': self.doc.Saved
            }
        except Exception as e:
            return {'error': str(e)}

def test_backend_operations():
    """Test function for backend operations."""
    print("=== Testing InDesign Backend Operations ===")
    
    repather = InDesignLinkRepather()
    
    # Test connection
    try:
        print("Testing InDesign connection...")
        repather.connect_to_indesign()
        print("✓ Successfully connected to InDesign")
    except Exception as e:
        print(f"✗ Failed to connect to InDesign: {e}")
        return
    
    # Test document info (should fail if no document open)
    try:
        info = repather.get_document_info()
        print(f"Document info: {info}")
    except Exception as e:
        print(f"Document info (expected error): {e}")
    
    print("Backend test completed.")

if __name__ == "__main__":
    test_backend_operations()
