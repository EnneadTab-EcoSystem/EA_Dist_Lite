#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
InDesign Web Application Module
Handles the HTTP server and API endpoints for the web interface.
"""

import os
import sys
import json
import logging
import webbrowser
import threading
import time
from http.server import HTTPServer, SimpleHTTPRequestHandler

# Add current directory to Python path for imports
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

# Import our modules
from get_indesign_version import InDesignVersionDetector
from backend import InDesignLinkRepather

class WebHandler(SimpleHTTPRequestHandler):
    """Custom HTTP request handler for the web interface."""
    
    # Class variables to maintain state across requests
    _repather = None
    _version_detector = None
    
    def __init__(self, *args, **kwargs):
        # Initialize shared instances only once
        if WebHandler._repather is None:
            WebHandler._repather = InDesignLinkRepather()
        if WebHandler._version_detector is None:
            WebHandler._version_detector = InDesignVersionDetector()
            
        self.repatcher = WebHandler._repather
        self.version_detector = WebHandler._version_detector
        super().__init__(*args, **kwargs)

    # ---- CORS helpers ----
    def _send_cors_headers(self):
        """Send CORS headers for all responses."""
        self.send_header('Access-Control-Allow-Origin', '*')
        self.send_header('Access-Control-Allow-Methods', 'GET, POST, OPTIONS')
        self.send_header('Access-Control-Allow-Headers', 'Content-Type')

    def end_headers(self):
        # Ensure CORS headers are present on every response, including static files
        try:
            self._send_cors_headers()
        except Exception:
            # Be defensive; never block sending headers
            pass
        super().end_headers()

    def do_OPTIONS(self):
        """Handle CORS preflight requests."""
        self.send_response(204)  # No Content
        self._send_cors_headers()
        self.end_headers()
        
    def translate_path(self, path):
        """Override to serve files from the src directory."""
        # Get the src directory path
        src_dir = os.path.dirname(os.path.abspath(__file__))
        
        # Remove leading slash and convert to local path
        if path.startswith('/'):
            path = path[1:]
            
        # If path is empty or just '/', serve IndesignRepather.html
        if not path or path == '':
            path = 'IndesignRepather.html'
            
        # Combine src directory with the requested path
        return os.path.join(src_dir, path)
        
    def do_GET(self):
        """Handle GET requests."""
        if self.path == '/':
            self.path = '/launcher.html'
        elif self.path == '/api/status':
            self.send_json_response({'status': 'ready'})
            return
        elif self.path.startswith('/api/preview_image/'):
            self.handle_preview_image()
            return
        elif self.path.startswith('/api/'):
            self.send_error(404, "API endpoint not found")
            return
            
        return super().do_GET()
        
    def do_POST(self):
        """Handle POST requests."""
        if self.path == '/api/get_indesign_versions':
            self.handle_get_indesign_versions()
        elif self.path == '/api/connect':
            self.handle_connect()
        elif self.path == '/api/auto_connect':
            self.handle_auto_connect()
        elif self.path == '/api/open_document':
            self.handle_open_document()
        elif self.path == '/api/get_links':
            self.handle_get_links()
        elif self.path == '/api/repath_links':
            self.handle_repath_links()
        elif self.path == '/api/preview_repath':
            self.handle_preview_repath()
        elif self.path == '/api/refresh_links':
            self.handle_refresh_links()
        elif self.path == '/api/document_info':
            self.handle_document_info()
        elif self.path == '/api/batch_preview':
            self.handle_batch_preview()
        elif self.path == '/api/batch_repath':
            self.handle_batch_repath()
        elif self.path == '/api/find_indesign_files':
            self.handle_find_indesign_files()

        elif self.path.startswith('/api/preview_image/'):
            self.handle_preview_image()
        else:
            self.send_error(404, "API endpoint not found")
            
    def handle_get_indesign_versions(self):
        """Handle get InDesign versions request."""
        try:
            print("API: Getting InDesign versions...")
            result = self.version_detector.get_available_indesign_versions()
            print(f"API: Found {result['total_found']} versions")
            
            response_data = {
                'success': True, 
                'versions': result['versions'],
                'total_found': result['total_found']
            }
            
            if result['errors']:
                response_data['warnings'] = result['errors']
                
            self.send_json_response(response_data)
        except Exception as e:
            print(f"API: Error getting versions: {e}")
            self.send_json_response({'success': False, 'error': str(e)})
            
    def handle_connect(self):
        """Handle InDesign connection request."""
        try:
            data = self.get_post_data()
            version_path = data.get('version_path')
            self.repatcher.connect_to_indesign(version_path)
            self.send_json_response({'success': True, 'message': 'Connected to InDesign'})
        except Exception as e:
            self.send_json_response({'success': False, 'error': str(e)})
            
    def handle_auto_connect(self):
        """Handle automatic connection to active InDesign documents."""
        try:
            print("API: Auto-connecting to active InDesign documents...")
            result = self.repatcher.auto_connect_to_active_document()
            
            if result['success']:
                print(f"API: Auto-connected successfully. Found {result['document_count']} documents")
                self.send_json_response(result)
            else:
                print(f"API: Auto-connect failed: {result['error']}")
                self.send_json_response(result)
                
        except Exception as e:
            print(f"API: Error in auto-connect: {e}")
            self.send_json_response({'success': False, 'error': str(e)})
            
    def handle_open_document(self):
        """Handle document opening request."""
        try:
            data = self.get_post_data()
            file_path = data.get('file_path')
            if not file_path:
                raise ValueError("No file path provided")
                
            self.repatcher.open_document(file_path)
            self.send_json_response({'success': True, 'message': 'Document opened'})
        except Exception as e:
            self.send_json_response({'success': False, 'error': str(e)})
            
    def handle_get_links(self):
        """Handle get links request."""
        try:
            print("API: Getting links...")
            print(f"API: repather.app = {self.repatcher.app}")
            print(f"API: repather.doc = {self.repatcher.doc}")
            
            if not self.repatcher.app:
                raise Exception("Not connected to InDesign. Please connect first.")
            if not self.repatcher.doc:
                raise Exception("No document is open. Please open a document first.")
                
            links = self.repatcher.get_all_links()
            print(f"API: Found {len(links)} links")
            self.send_json_response({'success': True, 'links': links})
        except Exception as e:
            print(f"API: Error getting links: {e}")
            self.send_json_response({'success': False, 'error': str(e)})
            
    def handle_repath_links(self):
        """Handle link repathing request."""
        try:
            data = self.get_post_data()
            old_folder = data.get('old_folder')
            new_folder = data.get('new_folder')
            
            if not old_folder or not new_folder:
                raise ValueError("Both old_folder and new_folder are required")
                
            results = self.repatcher.repath_links(old_folder, new_folder)
            self.send_json_response({'success': True, 'results': results})
        except Exception as e:
            self.send_json_response({'success': False, 'error': str(e)})
            
    def handle_preview_repath(self):
        """Handle preview repath request."""
        try:
            data = self.get_post_data()
            old_folder = data.get('old_folder')
            new_folder = data.get('new_folder')
            
            if not old_folder or not new_folder:
                raise ValueError("Both old_folder and new_folder are required")
                
            preview = self.repatcher.preview_repath(old_folder, new_folder)
            self.send_json_response({'success': True, 'preview': preview})
        except Exception as e:
            self.send_json_response({'success': False, 'error': str(e)})
            
    def handle_refresh_links(self):
        """Handle refresh links request."""
        try:
            print("API: Refreshing links...")
            
            if not self.repatcher.app:
                raise Exception("Not connected to InDesign. Please connect first.")
            if not self.repatcher.doc:
                raise Exception("No document is open. Please open a document first.")
                
            # Refresh all links in the document
            result = self.repatcher.refresh_all_links()
            print(f"API: Refreshed {result['refreshed']} links")
            self.send_json_response({'success': True, 'result': result})
        except Exception as e:
            print(f"API: Error refreshing links: {e}")
            self.send_json_response({'success': False, 'error': str(e)})
            
    def handle_document_info(self):
        """Handle document info request."""
        try:
            info = self.repatcher.get_document_info()
            self.send_json_response({'success': True, 'info': info})
        except Exception as e:
            self.send_json_response({'success': False, 'error': str(e)})
            
    def handle_find_indesign_files(self):
        """Handle find InDesign files request."""
        try:
            data = self.get_post_data()
            folder_path = data.get('folder_path')
            
            if not folder_path:
                raise ValueError("folder_path is required")
                
            files = self.repatcher.find_indesign_files(folder_path)
            self.send_json_response({'success': True, 'files': files})
        except Exception as e:
            self.send_json_response({'success': False, 'error': str(e)})
            
    def handle_batch_preview(self):
        """Handle batch preview request."""
        try:
            data = self.get_post_data()
            folder_path = data.get('folder_path')
            old_folder = data.get('old_folder')
            new_folder = data.get('new_folder')
            
            if not folder_path or not old_folder or not new_folder:
                raise ValueError("folder_path, old_folder, and new_folder are required")
                
            preview = self.repatcher.preview_batch_repath(folder_path, old_folder, new_folder)
            self.send_json_response({'success': True, 'preview': preview})
        except Exception as e:
            self.send_json_response({'success': False, 'error': str(e)})
            
    def handle_batch_repath(self):
        """Handle batch repath request."""
        try:
            data = self.get_post_data()
            folder_path = data.get('folder_path')
            old_folder = data.get('old_folder')
            new_folder = data.get('new_folder')
            
            if not folder_path or not old_folder or not new_folder:
                raise ValueError("folder_path, old_folder, and new_folder are required")
                
            # Define progress callback for real-time updates
            def progress_callback(current, total, current_file):
                # For now, we'll just log progress
                # In a real implementation, you might want to use WebSockets or Server-Sent Events
                print(f"Progress: {current + 1}/{total} - {current_file}")
                
            results = self.repatcher.batch_repath_files(folder_path, old_folder, new_folder, progress_callback)
            self.send_json_response({'success': True, 'results': results})
        except Exception as e:
            self.send_json_response({'success': False, 'error': str(e)})
            

            
    def handle_preview_image(self):
        """Handle image preview request."""
        try:
            import urllib.parse
            import os
            
            # Extract the file path from the URL
            encoded_path = self.path.replace('/api/preview_image/', '')
            file_path = urllib.parse.unquote(encoded_path)
            
            print(f"API: Preview image request for: {file_path}")
            
            # Security check: ensure the path is valid and exists
            if not file_path or file_path == 'unknown':
                print(f"API: Invalid file path: {file_path}")
                self.send_error(400, "Invalid file path")
                return
                
            # Handle network paths and normalize
            file_path = file_path.replace('/', '\\')
            if not os.path.exists(file_path):
                print(f"API: File not found: {file_path}")
                self.send_error(404, f"File not found: {os.path.basename(file_path)}")
                return
                
            # Check if it's an image file
            image_extensions = ['.jpg', '.jpeg', '.png', '.gif', '.bmp', '.webp', '.svg', '.ico', '.tiff', '.tif']
            file_ext = os.path.splitext(file_path)[1].lower()
            
            if file_ext not in image_extensions:
                print(f"API: Not an image file: {file_path}")
                self.send_error(400, f"Not an image file: {file_ext}")
                return
            
            print(f"API: Serving image: {file_path}")
            
            # Read and serve the image
            with open(file_path, 'rb') as f:
                image_data = f.read()
                
            self.send_response(200)
            self.send_header('Content-type', self.get_mime_type(file_ext))
            self.send_header('Access-Control-Allow-Origin', '*')
            self.send_header('Cache-Control', 'no-cache, no-store, must-revalidate')
            self.send_header('Pragma', 'no-cache')
            self.send_header('Expires', '0')
            self.end_headers()
            self.wfile.write(image_data)
            
        except Exception as e:
            print(f"API: Error serving image: {e}")
            self.send_error(500, f"Error serving image: {str(e)}")
            
    def get_mime_type(self, extension):
        """Get MIME type for file extension."""
        mime_types = {
            '.jpg': 'image/jpeg',
            '.jpeg': 'image/jpeg',
            '.png': 'image/png',
            '.gif': 'image/gif',
            '.bmp': 'image/bmp',
            '.webp': 'image/webp',
            '.svg': 'image/svg+xml',
            '.ico': 'image/x-icon',
            '.tiff': 'image/tiff',
            '.tif': 'image/tiff'
        }
        return mime_types.get(extension.lower(), 'application/octet-stream')
            
    def get_post_data(self):
        """Parse POST data."""
        content_length = int(self.headers.get('Content-Length', 0))
        post_data = self.rfile.read(content_length)
        return json.loads(post_data.decode('utf-8'))
        
    def send_json_response(self, data):
        """Send JSON response."""
        self.send_response(200)
        self.send_header('Content-type', 'application/json')
        self.send_header('Access-Control-Allow-Origin', '*')
        self.send_header('Access-Control-Allow-Methods', 'GET, POST, OPTIONS')
        self.send_header('Access-Control-Allow-Headers', 'Content-Type')
        self.end_headers()
        self.wfile.write(json.dumps(data).encode('utf-8'))
        
    def log_message(self, format, *args):
        """Override to use our logger."""
        logging.info(f"{self.address_string()} - {format % args}")


def start_server(host='127.0.0.1', port=8080):
    """Start the web server."""
    server_address = (host, port)
    httpd = HTTPServer(server_address, WebHandler)
    print(f"Server started at http://{host}:{port}")
    print("Opening browser...")
    
    # Open browser after a short delay
    def open_browser():
        time.sleep(1)
        webbrowser.open(f'http://{host}:{port}')
        
    threading.Thread(target=open_browser, daemon=True).start()
    
    try:
        httpd.serve_forever()
    except KeyboardInterrupt:
        print("\nShutting down server...")
        httpd.shutdown()


def test_web_server():
    """Test function for web server."""
    print("=== Testing Web Server ===")
    
    # Test version detection
    print("Testing version detection...")
    detector = InDesignVersionDetector()
    versions = detector.get_available_indesign_versions()
    print(f"Found {len(versions)} versions")
    
    # Test backend connection
    print("Testing backend connection...")
    repather = InDesignLinkRepather()
    try:
        repather.connect_to_indesign()
        # Avoid non-ASCII symbols that can break Windows console encodings
        print("Backend connection successful")
    except Exception as e:
        print(f"Backend connection failed: {e}")
    
    print("Web server test completed.")


if __name__ == "__main__":
    print("InDesign Link Repather Web Application")
    print("=" * 50)
    
    # Test components first
    test_web_server()
    
    # Start the server
    print("\nStarting web server...")
    start_server()
