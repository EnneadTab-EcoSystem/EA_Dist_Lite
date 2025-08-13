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
    
    def __init__(self, *args, **kwargs):
        self.repatcher = InDesignLinkRepather()
        self.version_detector = InDesignVersionDetector()
        super().__init__(*args, **kwargs)
        
    def translate_path(self, path):
        """Override to serve files from the src directory."""
        # Get the src directory path
        src_dir = os.path.dirname(os.path.abspath(__file__))
        
        # Remove leading slash and convert to local path
        if path.startswith('/'):
            path = path[1:]
            
        # If path is empty or just '/', serve index.html
        if not path or path == '':
            path = 'index.html'
            
        # Combine src directory with the requested path
        return os.path.join(src_dir, path)
        
    def do_GET(self):
        """Handle GET requests."""
        if self.path == '/':
            self.path = '/index.html'
        elif self.path == '/api/status':
            self.send_json_response({'status': 'ready'})
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
        elif self.path == '/api/open_document':
            self.handle_open_document()
        elif self.path == '/api/get_links':
            self.handle_get_links()
        elif self.path == '/api/repath_links':
            self.handle_repath_links()
        elif self.path == '/api/document_info':
            self.handle_document_info()
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
            links = self.repatcher.get_all_links()
            self.send_json_response({'success': True, 'links': links})
        except Exception as e:
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
            
    def handle_document_info(self):
        """Handle document info request."""
        try:
            info = self.repatcher.get_document_info()
            self.send_json_response({'success': True, 'info': info})
        except Exception as e:
            self.send_json_response({'success': False, 'error': str(e)})
            
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


def start_server(host='127.0.0.1', port=8000):
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
        print("✓ Backend connection successful")
    except Exception as e:
        print(f"✗ Backend connection failed: {e}")
    
    print("Web server test completed.")


if __name__ == "__main__":
    print("InDesign Link Repather Web Application")
    print("=" * 50)
    
    # Test components first
    test_web_server()
    
    # Start the server
    print("\nStarting web server...")
    start_server()
