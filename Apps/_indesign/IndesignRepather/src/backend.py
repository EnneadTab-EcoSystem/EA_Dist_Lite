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
from typing import List, Dict, Optional, Tuple
from concurrent.futures import ThreadPoolExecutor, as_completed

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
        """Get all links in the current document with page information and optimized file checking.

        Optimizations:
        - Collect basic link metadata in a single COM pass (name, path, status)
        - Perform filesystem existence checks in parallel outside COM using a thread pool
        - Cache results per path to avoid duplicate checks
        - Prefer real filesystem existence over InDesign's status when they disagree
        """
        links: List[Dict] = []
        try:
            if not self.app:
                raise Exception("Not connected to InDesign. Please connect first.")
                
            # Get all links in the document
            assert self.doc is not None  # Type guard for linter
            all_links = self.doc.Links
            link_count = all_links.Count
            self.logger.info(f"Links collection has {link_count} items")
            
            # Get page information for links (best-effort)
            page_info = self._get_link_page_info()

            # -------------------------------
            # First pass: collect raw link data via COM
            # -------------------------------
            raw_links: List[Dict] = []
            unique_paths: Dict[str, str] = {}
            
            if link_count > 0:
                for i in range(link_count):
                    try:
                        link = all_links.Item(i)
                        if not link:
                            continue
                        link_name = link.Name
                        file_path = getattr(link, 'FilePath', '')
                        link_status = getattr(link, 'LinkStatus', 1)
                        # Detect embedded via URI if available
                        is_embedded = False
                        try:
                            uri = getattr(link, 'LinkResourceURI', '')
                            if isinstance(uri, str) and uri.lower().startswith('embedded:'):
                                is_embedded = True
                        except Exception:
                            pass

                        # Try to get page directly from this link's parent chain
                        page_text = None
                        try:
                            page_text = self._get_page_for_link(link)
                        except Exception:
                            page_text = None

                        normalized_path = ''
                        if file_path and file_path != 'unknown':
                            normalized_path = file_path.replace('/', '\\')
                            unique_paths[normalized_path] = normalized_path

                        raw_links.append({
                            'index': i,
                            'name': link_name,
                            'file_path': file_path,
                            'normalized_path': normalized_path,
                            'link_status': link_status,
                            'is_embedded': is_embedded,
                            'page_text': page_text,
                        })
                    except Exception as link_error:
                        self.logger.warning(f"Could not access link at index {i}: {link_error}")
                        continue

            # -------------------------------
            # Second pass: check file existence in parallel
            # -------------------------------
            def fast_exists(path: str) -> Tuple[str, bool, Optional[str]]:
                try:
                    if not path:
                        return (path, False, None)
                    # Quick check
                    if os.path.exists(path):
                        return (path, True, None)
                    # Network/alternate check
                    if path.startswith('\\\\'):
                        try:
                            import win32file
                            return (path, win32file.GetFileAttributes(path) != -1, None)
                        except Exception as e:
                            return (path, False, str(e))
                    # Pathlib check
                    try:
                        return (path, Path(path).exists(), None)
                    except Exception as e:
                        return (path, False, str(e))
                except Exception as e:
                    return (path, False, str(e))

            path_results: Dict[str, Tuple[bool, Optional[str]]] = {}
            if unique_paths:
                max_workers = min(16, max(1, os.cpu_count() or 4))
                with ThreadPoolExecutor(max_workers=max_workers) as pool:
                    futures = [pool.submit(fast_exists, p) for p in unique_paths.values()]
                    for fut in as_completed(futures):
                        path, exists, err = fut.result()
                        path_results[path] = (exists, err)

            # -------------------------------
            # Final pass: assemble link info
            # -------------------------------
            for item in raw_links:
                normalized_path = item['normalized_path']
                exists, err = (False, None)
                if normalized_path:
                    exists, err = path_results.get(normalized_path, (False, None))

                # Determine final status: prefer actual existence
                if item.get('is_embedded'):
                    actual_status = 4  # LinkStatus.LINK_EMBEDDED
                elif not exists and item['link_status'] != 4:
                    actual_status = 2  # LinkStatus.LINK_MISSING
                else:
                    # 1=OK, 3=OUT_OF_DATE, others pass through
                    actual_status = 1 if item['link_status'] == 1 else item['link_status']

                links.append({
                    'name': item['name'],
                    'file_path': item['file_path'],
                    'status': actual_status,
                    'file_exists': exists,
                    'file_error': err,
                    'index': item['index'],
                    'page_info': item.get('page_text') or page_info.get(item['name'], 'Unknown page'),
                    'needs_attention': not exists,
                })
                        
            # Method 2: If Method 1 (indexing) failed to produce any, try enumerating collection
            if not links and link_count > 0:
                self.logger.info("Trying alternative method to access links...")
                try:
                    for link in all_links:
                        try:
                            link_name = link.Name
                            file_path = link.FilePath
                            
                            # Enhanced status checking
                            link_status = getattr(link, 'LinkStatus', 1)
                            
                            # Additional file existence check
                            file_exists = False
                            file_error = None
                            try:
                                if file_path and file_path != 'unknown':
                                    # Normalize path for Windows
                                    normalized_path = file_path.replace('/', '\\')
                                    
                                    # Try multiple methods to check file existence
                                    file_exists = os.path.exists(normalized_path)
                                    
                                    # If not found with os.path.exists, try other methods
                                    if not file_exists:
                                        # Method 1: Try with win32file for network paths
                                        if normalized_path.startswith('\\\\'):
                                            try:
                                                import win32file
                                                file_exists = win32file.GetFileAttributes(normalized_path) != -1
                                            except:
                                                pass
                                        
                                        # Method 2: Try with pathlib for better Unicode support
                                        if not file_exists:
                                            try:
                                                from pathlib import Path
                                                path_obj = Path(normalized_path)
                                                file_exists = path_obj.exists()
                                            except:
                                                pass
                                        
                                        # Method 3: Try to open the file to check if it's accessible
                                        if not file_exists:
                                            try:
                                                with open(normalized_path, 'rb') as f:
                                                    # Just try to read the first byte to check if file is accessible
                                                    f.read(1)
                                                    file_exists = True
                                            except:
                                                pass
                                        
                                        # Method 4: For image files, try to check if it's a valid image
                                        if not file_exists and any(ext in normalized_path.lower() for ext in ['.jpg', '.jpeg', '.png', '.gif', '.bmp', '.webp', '.svg', '.ico', '.tiff', '.tif']):
                                            try:
                                                import win32file
                                                # Try to get file attributes without opening
                                                attrs = win32file.GetFileAttributes(normalized_path)
                                                if attrs != -1:
                                                    file_exists = True
                                            except:
                                                pass
                                    
                                    # If still not found, but InDesign thinks it's linked, 
                                    # trust InDesign's status more than our file check
                                    if not file_exists and link_status == 1:
                                        # InDesign thinks it's linked, so the file probably exists
                                        # but our file system check failed (could be network, permissions, etc.)
                                        file_exists = True
                                        self.logger.info(f"Trusting InDesign status for '{link_name}' - file check failed but InDesign reports linked")
                                        
                            except Exception as e:
                                file_error = str(e)
                                # If there's an error checking file existence, but InDesign thinks it's linked,
                                # trust InDesign's status
                                if link_status == 1:
                                    file_exists = True
                                    self.logger.info(f"Trusting InDesign status for '{link_name}' - file check error but InDesign reports linked")
                                else:
                                    file_exists = False
                            
                            # Determine the actual status
                            actual_status = link_status
                            # Only mark as missing if we're confident the file doesn't exist AND InDesign also thinks it's missing
                            if not file_exists and link_status != 1:
                                actual_status = 2
                                self.logger.warning(f"Link '{link_name}' marked as missing: {file_path}")
                            elif file_exists and link_status == 1:
                                # File exists and InDesign thinks it's linked - this is the correct state
                                actual_status = 1
                                self.logger.info(f"Link '{link_name}' confirmed as linked: {file_path}")
                            
                            link_info = {
                                'name': link_name,
                                'file_path': file_path,
                                'status': actual_status,
                                'file_exists': file_exists,
                                'file_error': file_error,
                                'index': len(links),
                                'page_info': page_info.get(link_name, 'Unknown page'),
                                'needs_attention': not file_exists and actual_status == 2
                            }
                            links.append(link_info)
                        except Exception as link_error:
                            self.logger.warning(f"Could not access link in iteration: {link_error}")
                            continue
                except Exception as iter_error:
                    self.logger.warning(f"Could not iterate through links: {iter_error}")
                    
            # Method 3: Try using _NewEnum if available
            if not links and link_count > 0:
                self.logger.info("Trying _NewEnum method to access links...")
                try:
                    enum = all_links._NewEnum()
                    i = 0
                    while i < link_count:
                        try:
                            link = enum.Next()
                            link_name = link.Name
                            file_path = link.FilePath
                            
                            # Enhanced status checking
                            link_status = getattr(link, 'LinkStatus', 1)
                            
                            # Additional file existence check
                            file_exists = False
                            file_error = None
                            try:
                                if file_path and file_path != 'unknown':
                                    # Normalize path for Windows
                                    normalized_path = file_path.replace('/', '\\')
                                    
                                    # Try multiple methods to check file existence
                                    file_exists = os.path.exists(normalized_path)
                                    
                                    # If not found with os.path.exists, try other methods
                                    if not file_exists:
                                        # Method 1: Try with win32file for network paths
                                        if normalized_path.startswith('\\\\'):
                                            try:
                                                import win32file
                                                file_exists = win32file.GetFileAttributes(normalized_path) != -1
                                            except:
                                                pass
                                        
                                        # Method 2: Try with pathlib for better Unicode support
                                        if not file_exists:
                                            try:
                                                from pathlib import Path
                                                path_obj = Path(normalized_path)
                                                file_exists = path_obj.exists()
                                            except:
                                                pass
                                        
                                        # Method 3: Try to open the file to check if it's accessible
                                        if not file_exists:
                                            try:
                                                with open(normalized_path, 'rb') as f:
                                                    # Just try to read the first byte to check if file is accessible
                                                    f.read(1)
                                                    file_exists = True
                                            except:
                                                pass
                                        
                                        # Method 4: For image files, try to check if it's a valid image
                                        if not file_exists and any(ext in normalized_path.lower() for ext in ['.jpg', '.jpeg', '.png', '.gif', '.bmp', '.webp', '.svg', '.ico', '.tiff', '.tif']):
                                            try:
                                                import win32file
                                                # Try to get file attributes without opening
                                                attrs = win32file.GetFileAttributes(normalized_path)
                                                if attrs != -1:
                                                    file_exists = True
                                            except:
                                                pass
                                    
                                    # If still not found, but InDesign thinks it's linked, 
                                    # trust InDesign's status more than our file check
                                    if not file_exists and link_status == 1:
                                        # InDesign thinks it's linked, so the file probably exists
                                        # but our file system check failed (could be network, permissions, etc.)
                                        file_exists = True
                                        self.logger.info(f"Trusting InDesign status for '{link_name}' - file check failed but InDesign reports linked")
                                        
                            except Exception as e:
                                file_error = str(e)
                                # If there's an error checking file existence, but InDesign thinks it's linked,
                                # trust InDesign's status
                                if link_status == 1:
                                    file_exists = True
                                    self.logger.info(f"Trusting InDesign status for '{link_name}' - file check error but InDesign reports linked")
                                else:
                                    file_exists = False
                            
                            # Determine the actual status
                            actual_status = link_status
                            # Only mark as missing if we're confident the file doesn't exist AND InDesign also thinks it's missing
                            if not file_exists and link_status != 1:
                                actual_status = 2
                                self.logger.warning(f"Link '{link_name}' marked as missing: {file_path}")
                            elif file_exists and link_status == 1:
                                # File exists and InDesign thinks it's linked - this is the correct state
                                actual_status = 1
                                self.logger.info(f"Link '{link_name}' confirmed as linked: {file_path}")
                            
                            link_info = {
                                'name': link_name,
                                'file_path': file_path,
                                'status': actual_status,
                                'file_exists': file_exists,
                                'file_error': file_error,
                                'index': i,
                                'page_info': page_info.get(link_name, 'Unknown page'),
                                'needs_attention': not file_exists and actual_status == 2
                            }
                            links.append(link_info)
                            i += 1
                        except Exception:
                            break
                except Exception as enum_error:
                    self.logger.warning(f"Could not use _NewEnum: {enum_error}")
                    
            # Sort links to prioritize missing files
            links.sort(key=lambda x: (not x['needs_attention'], x['name'].lower()))
            
            # Log summary of missing files
            missing_count = sum(1 for link in links if not link['file_exists'])
            if missing_count > 0:
                self.logger.warning(f"Found {missing_count} links with missing files that need attention")
            
            self.logger.info(f"Successfully found {len(links)} links in document ({missing_count} missing)")
            return links
            
        except Exception as e:
            error_msg = str(e)
            if "Object reference not set" in error_msg:
                raise Exception("Document connection lost. Please reconnect to InDesign and open the document again.")
            elif "Access is denied" in error_msg:
                raise Exception("Access denied to document links. Please ensure the document is not locked.")
            else:
                raise Exception(f"Failed to get links: {error_msg}")
    
    def _get_link_page_info(self) -> Dict[str, str]:
        """Get page information for links in the document."""
        page_info = {}
        try:
            if not self.doc:
                return page_info
                
            # Method 1: Try to get page information by iterating through all graphics
            try:
                if hasattr(self.doc, 'AllGraphics'):
                    all_graphics = self.doc.AllGraphics
                    self.logger.info(f"Found {all_graphics.Count} graphics in document")
                    
                    for i in range(all_graphics.Count):
                        try:
                            graphic = all_graphics.Item(i)
                            
                            # Check if this graphic has a link
                            if hasattr(graphic, 'ItemLink') and graphic.ItemLink:
                                link = graphic.ItemLink
                                link_name = link.Name
                                
                                # Try to get the page number from the graphic's parent
                                page_number = self._get_page_number_for_graphic(graphic)
                                if page_number:
                                    page_info[link_name] = f"Page {page_number}"
                                else:
                                    page_info[link_name] = "Unknown page"
                                    
                        except Exception as e:
                            self.logger.debug(f"Error processing graphic {i}: {e}")
                            continue
                            
            except Exception as e:
                self.logger.warning(f"Could not get graphics: {e}")
                
            # Method 2: If Method 1 didn't work, try iterating through pages
            if not page_info:
                try:
                    pages = self.doc.Pages
                    self.logger.info(f"Found {pages.Count} pages in document")
                    
                    for i in range(pages.Count):
                        try:
                            page = pages.Item(i)
                            page_name = f"Page {i + 1}"
                            
                            # Try to get all items on the page
                            if hasattr(page, 'AllPageItems'):
                                items = page.AllPageItems
                                for j in range(items.Count):
                                    try:
                                        item = items.Item(j)
                                        # Check if this item has graphics
                                        if hasattr(item, 'Graphics') and item.Graphics:
                                            for k in range(item.Graphics.Count):
                                                try:
                                                    graphic = item.Graphics.Item(k)
                                                    if hasattr(graphic, 'ItemLink') and graphic.ItemLink:
                                                        link_name = graphic.ItemLink.Name
                                                        page_info[link_name] = page_name
                                                except Exception:
                                                    continue
                                    except Exception:
                                        continue
                        except Exception as e:
                            self.logger.debug(f"Error processing page {i}: {e}")
                            continue
                            
                except Exception as e:
                    self.logger.warning(f"Could not get page information: {e}")
                    
            # Method 3: Fallback - assign all links to a general page range
            if not page_info:
                try:
                    if hasattr(self.doc, 'Pages') and self.doc.Pages.Count > 0:
                        total_pages = self.doc.Pages.Count
                        # Get all links first
                        links_result = self.get_all_links()
                        if isinstance(links_result, dict) and links_result.get('success'):
                            links = links_result.get('links', [])
                            if isinstance(links, list):
                                for link in links:
                                    if isinstance(link, dict) and 'name' in link:
                                        page_info[link['name']] = f"Page 1-{total_pages}"
                except Exception as e:
                    self.logger.warning(f"Could not assign fallback page info: {e}")
                    
            self.logger.info(f"Page info collected for {len(page_info)} links")
            return page_info
            
        except Exception as e:
            self.logger.warning(f"Failed to get page information: {e}")
            return page_info
            
    def _get_page_number_for_graphic(self, graphic) -> Optional[int]:
        """Try to get the page number for a specific graphic."""
        try:
            # Method 1: Try to get page from graphic's parent chain
            current = graphic
            for _ in range(10):  # Limit depth to avoid infinite loops
                if hasattr(current, 'Parent'):
                    parent = current.Parent
                    if hasattr(parent, 'Name') and 'Page' in parent.Name:
                        # Extract page number from name
                        import re
                        match = re.search(r'Page\s*(\d+)', parent.Name)
                        if match:
                            return int(match.group(1))
                    elif hasattr(parent, 'Parent'):
                        current = parent.Parent
                    else:
                        break
                else:
                    break
                    
            # Method 2: Try to get page from graphic's geometric bounds
            if hasattr(graphic, 'GeometricBounds'):
                bounds = graphic.GeometricBounds
                if bounds and len(bounds) >= 4:
                    # Use Y coordinate to estimate page (this is approximate)
                    y_coord = bounds[1]  # Top coordinate
                    # This would need calibration based on page size
                    # For now, return a default
                    return 1
                    
            return None
    def _get_page_for_link(self, link) -> Optional[str]:
        """Attempt to resolve the page label for a given Link by traversing its parents."""
        try:
            current = getattr(link, 'Parent', None)
            for _ in range(10):
                if current is None:
                    break
                # If the parent has a ParentPage, use it
                if hasattr(current, 'ParentPage') and current.ParentPage is not None:
                    try:
                        page = current.ParentPage
                        # Use page.Name if available, else build 'Page N'
                        if hasattr(page, 'Name') and page.Name:
                            return str(page.Name)
                        if hasattr(page, 'DocumentOffset'):
                            return f"Page {int(page.DocumentOffset) + 1}"
                    except Exception:
                        pass
                # Direct Name may contain 'Page N'
                if hasattr(current, 'Name') and isinstance(current.Name, str) and 'Page' in current.Name:
                    import re
                    match = re.search(r'Page\s*(\d+)', current.Name)
                    if match:
                        return f"Page {int(match.group(1))}"
                # Walk up
                current = getattr(current, 'Parent', None)
        except Exception:
            return None
        return None
            
        except Exception as e:
            self.logger.debug(f"Error getting page number for graphic: {e}")
            return None
            
    def repath_links(self, old_folder: str, new_folder: str) -> Dict:
        """Repath all links by replacing old folder with new folder."""
        results = {
            'success': 0,
            'failed': 0,
            'skipped': 0,
            'details': []
        }
        
        try:
            if not self.doc:
                raise Exception("No document is open")
                
            links = self.get_all_links()
            self.logger.info(f"Processing {len(links)} links for repathing")
            
            for link_info in links:
                current_path = None
                try:
                    # Get the link object using the index
                    link_index = link_info.get('index', 0)
                    link = self.doc.Links.Item(link_index)
                    current_path = link.FilePath
                    
                    self.logger.info(f"Processing link: {link_info['name']} at path: {current_path}")
                    
                    # Check if the link path contains the old folder (case-insensitive)
                    if old_folder.lower() in current_path.lower():
                        # Create new path by replacing old folder with new folder
                        # Use case-insensitive replacement to handle different case scenarios
                        import re
                        pattern = re.compile(re.escape(old_folder), re.IGNORECASE)
                        # Use a lambda function to avoid regex group reference issues
                        new_path = pattern.sub(lambda m: new_folder, current_path)
                        
                        # Ensure proper path formatting
                        new_path = new_path.replace('/', '\\')  # Normalize slashes
                        # Remove any double backslashes except for network paths
                        if not new_path.startswith('\\\\'):
                            new_path = new_path.replace('\\\\', '\\')
                        
                        self.logger.info(f"Attempting to relink from: {current_path} to: {new_path}")
                        
                        # Check if old and new paths are the same
                        if current_path.lower() == new_path.lower():
                            results['skipped'] += 1
                            results['details'].append({
                                'name': link_info['name'],
                                'old_path': current_path,
                                'new_path': new_path,
                                'status': 'unchanged'
                            })
                            self.logger.info(f"Path unchanged, skipping: {link_info['name']}")
                        # Check if new file exists
                        elif os.path.exists(new_path):
                            # Try to update the link using Relink method
                            try:
                                # First, try to get the file object
                                import win32com.client
                                fso = win32com.client.Dispatch("Scripting.FileSystemObject")
                                file_obj = fso.GetFile(new_path)
                                
                                # Update the link using Relink with the file object
                                self.logger.info(f"Attempting to relink {link_info['name']} using file object")
                                link.Relink(file_obj)
                                
                                results['success'] += 1
                                results['details'].append({
                                    'name': link_info['name'],
                                    'old_path': current_path,
                                    'new_path': new_path,
                                    'status': 'success'
                                })
                                self.logger.info(f"Successfully repathed: {link_info['name']}")
                                
                            except Exception as relink_error:
                                self.logger.warning(f"Relink with file object failed, trying with path string: {relink_error}")
                                
                                # Fallback: try with path string
                                try:
                                    link.Relink(new_path)
                                    
                                    results['success'] += 1
                                    results['details'].append({
                                        'name': link_info['name'],
                                        'old_path': current_path,
                                        'new_path': new_path,
                                        'status': 'success'
                                    })
                                    self.logger.info(f"Successfully repathed: {link_info['name']}")
                                    
                                except Exception as path_error:
                                    self.logger.error(f"Both relink methods failed for {link_info['name']}: {path_error}")
                                    results['failed'] += 1
                                    results['details'].append({
                                        'name': link_info['name'],
                                        'old_path': current_path,
                                        'new_path': new_path,
                                        'status': f'error: {str(path_error)}'
                                    })
                        else:
                            results['skipped'] += 1
                            results['details'].append({
                                'name': link_info['name'],
                                'old_path': current_path,
                                'new_path': new_path,
                                'status': 'file_not_found'
                            })
                            self.logger.warning(f"New file not found, skipping: {new_path}")
                    else:
                        results['skipped'] += 1
                        results['details'].append({
                            'name': link_info['name'],
                            'old_path': current_path,
                            'new_path': None,
                            'status': 'skipped'
                        })
                        self.logger.info(f"Skipped link {link_info['name']} - old folder not in path")
                        
                except Exception as e:
                    results['failed'] += 1
                    results['details'].append({
                        'name': link_info['name'],
                        'old_path': current_path if current_path else 'unknown',
                        'new_path': None,
                        'status': f'error: {str(e)}'
                    })
                    self.logger.error(f"Failed to repath link {link_info['name']}: {e}")
                    
            self.logger.info(f"Repathing complete: {results['success']} success, {results['failed']} failed, {results['skipped']} skipped")
            return results
            
        except Exception as e:
            self.logger.error(f"Failed to repath links: {e}")
            raise
            
    def preview_repath(self, old_folder: str, new_folder: str) -> Dict:
        """Preview the repathing operation without actually changing links."""
        if not self.doc:
            raise Exception("No document is open")
            
        preview = {
            'found': 0,
            'missing': 0,
            'unchanged': 0,
            'total': 0,
            'details': []
        }
        
        try:
            # Use the enhanced get_all_links method to get proper link data
            links = self.get_all_links()
            preview['total'] = len(links)
            
            for link_info in links:
                try:
                    current_path = link_info['file_path']
                    
                    # Check if the link contains the old folder path
                    if old_folder.lower() in current_path.lower():
                        # Create regex pattern to replace the old folder with new folder
                        import re
                        # Escape special regex characters in the old folder path
                        escaped_old_folder = re.escape(old_folder)
                        pattern = re.compile(escaped_old_folder, re.IGNORECASE)
                        
                        # Use a lambda function to avoid regex group reference issues
                        new_path = pattern.sub(lambda m: new_folder, current_path)
                        
                        # Ensure proper path formatting
                        new_path = new_path.replace('/', '\\')  # Normalize slashes
                        # Remove any double backslashes except for network paths
                        if not new_path.startswith('\\\\'):
                            new_path = new_path.replace('\\\\', '\\')
                        
                        # Check if old and new paths are the same
                        if current_path.lower() == new_path.lower():
                            preview['unchanged'] += 1
                            preview['details'].append({
                                'name': link_info['name'],
                                'old_path': current_path,
                                'new_path': current_path,  # Keep same path for unchanged
                                'found': True,
                                'unchanged': True,
                                'status': 'unchanged'
                            })
                        # Check if new file exists
                        elif os.path.exists(new_path):
                            preview['found'] += 1
                            preview['details'].append({
                                'name': link_info['name'],
                                'old_path': current_path,
                                'new_path': new_path,
                                'found': True,
                                'unchanged': False,
                                'status': 'found'
                            })
                        else:
                            preview['missing'] += 1
                            preview['details'].append({
                                'name': link_info['name'],
                                'old_path': current_path,
                                'new_path': new_path,
                                'found': False,
                                'unchanged': False,
                                'status': 'missing'
                            })
                    else:
                        # Link doesn't contain the old folder path, so it won't be changed
                        # Check if old and new folders are the same (for unchanged status)
                        if old_folder.lower() == new_folder.lower():
                            preview['unchanged'] += 1
                            preview['details'].append({
                                'name': link_info['name'],
                                'old_path': current_path,
                                'new_path': current_path,  # Same path
                                'found': True,
                                'unchanged': True,
                                'status': 'unchanged'
                            })
                        else:
                            preview['found'] += 1
                            preview['details'].append({
                                'name': link_info['name'],
                                'old_path': current_path,
                                'new_path': current_path,  # Keep same path since it's not affected
                                'found': True,
                                'unchanged': False,
                                'status': 'found'
                            })
                        
                except Exception as e:
                    preview['missing'] += 1
                    preview['details'].append({
                        'name': link_info['name'] if 'link_info' in locals() else 'Unknown',
                        'old_path': current_path if 'current_path' in locals() else 'unknown',
                        'new_path': 'unknown',
                        'found': False,
                        'unchanged': False,
                        'status': 'error'
                    })
                    self.logger.error(f"Failed to preview link {link_info['name'] if 'link_info' in locals() else 'Unknown'}: {e}")
                    
            self.logger.info(f"Preview complete: {preview['found']} found, {preview['missing']} missing, {preview['unchanged']} unchanged, {preview['total']} total")
            return preview
            
        except Exception as e:
            self.logger.error(f"Failed to preview repath: {e}")
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

    def auto_connect_to_active_document(self):
        """Automatically connect to InDesign and detect active documents."""
        try:
            # First connect to InDesign
            self.connect_to_indesign()
            
            if not self.app:
                raise Exception("Failed to connect to InDesign")
            
            # Check for active documents
            active_docs = []
            doc_count = 0
            
            try:
                # Try to get the active document first
                try:
                    active_doc = self.app.ActiveDocument
                    if active_doc:
                        doc_info = {
                            'name': active_doc.Name,
                            'index': 0,
                            'file_path': active_doc.FilePath if hasattr(active_doc, 'FilePath') else 'Unknown',
                            'is_active': True
                        }
                        active_docs.append(doc_info)
                        self.doc = active_doc
                        doc_count = 1
                        self.logger.info(f"Auto-connected to active document: {active_doc.Name}")
                except Exception as active_error:
                    self.logger.warning(f"Could not access active document: {active_error}")
                
                # If no active document, try to enumerate all documents
                if doc_count == 0:
                    try:
                        doc_count = self.app.Documents.Count
                        if doc_count > 0:
                            for i in range(doc_count):
                                try:
                                    doc = self.app.Documents.Item(i)
                                    if doc:
                                        doc_info = {
                                            'name': doc.Name,
                                            'index': i,
                                            'file_path': doc.FilePath if hasattr(doc, 'FilePath') else 'Unknown',
                                            'is_active': i == 0  # First document is usually active
                                        }
                                        active_docs.append(doc_info)
                                        
                                        # Set the first document as current
                                        if i == 0:
                                            self.doc = doc
                                            self.logger.info(f"Auto-connected to document: {doc.Name}")
                                except Exception as doc_error:
                                    self.logger.warning(f"Could not access document at index {i}: {doc_error}")
                                    continue
                    except Exception as docs_error:
                        self.logger.warning(f"Could not access Documents collection: {docs_error}")
                        doc_count = 0
                        
            except Exception as docs_error:
                self.logger.warning(f"Could not access Documents collection: {docs_error}")
                doc_count = 0
            
            # Get the full document path
            current_document_path = None
            if self.doc:
                try:
                    if hasattr(self.doc, 'FilePath') and self.doc.FilePath:
                        current_document_path = self.doc.FilePath
                    elif hasattr(self.doc, 'Name') and self.doc.Name:
                        # If no FilePath, try to construct from Name
                        current_document_path = self.doc.Name
                    else:
                        current_document_path = "Unknown document"
                except Exception as e:
                    self.logger.warning(f"Could not get document path: {e}")
                    current_document_path = "Unknown document"
            
            return {
                'success': True,
                'connected': True,
                'app_name': self.app.Name,
                'app_version': self.app.Version,
                'active_documents': active_docs,
                'document_count': doc_count,
                'current_document': current_document_path
            }
            
        except Exception as e:
            return {
                'success': False,
                'error': str(e),
                'connected': False,
                'active_documents': [],
                'document_count': 0
            }
            
    def refresh_all_links(self) -> Dict:
        """Refresh all links in the current document."""
        if not self.doc:
            raise Exception("No document is open")
            
        results = {
            'refreshed': 0,
            'failed': 0,
            'total': 0,
            'details': []
        }
        
        try:
            links = self.get_all_links()
            results['total'] = len(links)
            
            for link_info in links:
                try:
                    # Get the link object using the index
                    link_index = link_info.get('index', 0)
                    link = self.doc.Links.Item(link_index)
                    
                    # Try to refresh the link
                    link.Update()
                    
                    results['refreshed'] += 1
                    results['details'].append({
                        'name': link_info['name'],
                        'status': 'refreshed'
                    })
                    self.logger.info(f"Successfully refreshed link: {link_info['name']}")
                    
                except Exception as e:
                    results['failed'] += 1
                    results['details'].append({
                        'name': link_info['name'],
                        'status': f'error: {str(e)}'
                    })
                    self.logger.error(f"Failed to refresh link {link_info['name']}: {e}")
                    
            self.logger.info(f"Link refresh complete: {results['refreshed']} refreshed, {results['failed']} failed, {results['total']} total")
            return results
            
        except Exception as e:
            self.logger.error(f"Failed to refresh links: {e}")
            raise



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
