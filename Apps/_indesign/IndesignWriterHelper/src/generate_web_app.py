#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
InDesign Writer Helper Web Application Module
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
from backend import InDesignTextManager

class WebHandler(SimpleHTTPRequestHandler):
    """Custom HTTP request handler for the web interface."""
    
    # Class variables to maintain state across requests
    _text_manager = None
    _version_detector = None
    
    def __init__(self, *args, **kwargs):
        # Initialize shared instances only once
        if WebHandler._text_manager is None:
            WebHandler._text_manager = InDesignTextManager()
        if WebHandler._version_detector is None:
            WebHandler._version_detector = InDesignVersionDetector()
            
        self.text_manager = WebHandler._text_manager
        self.version_detector = WebHandler._version_detector
        super().__init__(*args, **kwargs)
        
    def translate_path(self, path):
        """Override to serve files from the src directory."""
        # Get the src directory path
        src_dir = os.path.dirname(os.path.abspath(__file__))
        
        # Remove leading slash and convert to local path
        if path.startswith('/'):
            path = path[1:]
            
        # If path is empty or just '/', serve IndesignWriterHelper.html
        if not path or path == '':
            path = 'IndesignWriterHelper.html'
            
        # Combine src directory with the requested path
        return os.path.join(src_dir, path)
        
    def do_GET(self):
        """Handle GET requests."""
        if self.path == '/':
            self.path = '/launcher.html'
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
        elif self.path == '/api/auto_connect':
            self.handle_auto_connect()
        elif self.path == '/api/get_document_info':
            self.handle_get_document_info()
        elif self.path == '/api/extract_text_frames':
            self.handle_extract_text_frames()
        elif self.path == '/api/get_current_frame':
            self.handle_get_current_frame()
        elif self.path == '/api/navigate_frame':
            self.handle_navigate_frame()
        elif self.path == '/api/next_frame':
            self.handle_next_frame()
        elif self.path == '/api/previous_frame':
            self.handle_previous_frame()
        elif self.path == '/api/get_frames_by_page':
            self.handle_get_frames_by_page()
        elif self.path == '/api/get_page_names':
            self.handle_get_page_names()
        elif self.path == '/api/search_text':
            self.handle_search_text()
        elif self.path == '/api/get_statistics':
            self.handle_get_statistics()
        elif self.path == '/api/update_text':
            self.handle_update_text()
        else:
            self.send_error(404, "API endpoint not found")
    
    def send_json_response(self, data):
        """Send JSON response."""
        self.send_response(200)
        self.send_header('Content-type', 'application/json')
        self.send_header('Access-Control-Allow-Origin', '*')
        self.send_header('Access-Control-Allow-Methods', 'GET, POST, OPTIONS')
        self.send_header('Access-Control-Allow-Headers', 'Content-Type')
        self.end_headers()
        self.wfile.write(json.dumps(data).encode())
    
    def send_error_response(self, message, status_code=400):
        """Send error response."""
        self.send_response(status_code)
        self.send_header('Content-type', 'application/json')
        self.send_header('Access-Control-Allow-Origin', '*')
        self.end_headers()
        self.wfile.write(json.dumps({'error': message}).encode())
    
    def get_request_data(self):
        """Get JSON data from request body."""
        content_length = int(self.headers.get('Content-Length', 0))
        if content_length > 0:
            return json.loads(self.rfile.read(content_length).decode())
        return {}
    
    def handle_get_indesign_versions(self):
        """Handle getting InDesign versions."""
        try:
            versions = self.version_detector.detect_versions()
            self.send_json_response({'versions': versions})
        except Exception as e:
            self.send_error_response(f"Failed to get InDesign versions: {e}")
    
    def handle_connect(self):
        """Handle connecting to InDesign."""
        try:
            data = self.get_request_data()
            version_info = data.get('version_info')
            
            if version_info:
                app = self.version_detector.connect_to_indesign(version_info)
            else:
                app = self.version_detector.connect_to_indesign()
            
            if app:
                success = self.text_manager.connect_to_indesign()
                if success:
                    self.send_json_response({'success': True, 'message': 'Connected to InDesign'})
                else:
                    self.send_error_response('Failed to connect to InDesign')
            else:
                self.send_error_response('Failed to connect to InDesign')
        except Exception as e:
            self.send_error_response(f"Failed to connect: {e}")
    
    def handle_auto_connect(self):
        """Handle auto-connecting to InDesign."""
        try:
            # Try to connect to running instance
            success = self.text_manager.connect_to_indesign()
            if success:
                self.send_json_response({'success': True, 'message': 'Auto-connected to InDesign'})
            else:
                self.send_error_response('No running InDesign instance found')
        except Exception as e:
            self.send_error_response(f"Auto-connect failed: {e}")
    
    def handle_get_document_info(self):
        """Handle getting document information."""
        try:
            doc_info = self.text_manager.get_active_document()
            if doc_info:
                self.send_json_response({'success': True, 'document': doc_info})
            else:
                self.send_error_response('No active document found')
        except Exception as e:
            self.send_error_response(f"Failed to get document info: {e}")
    
    def handle_extract_text_frames(self):
        """Handle extracting text frames."""
        try:
            frames = self.text_manager.extract_text_frames()
            self.send_json_response({'success': True, 'frames': frames, 'count': len(frames)})
        except Exception as e:
            self.send_error_response(f"Failed to extract text frames: {e}")
    
    def handle_get_current_frame(self):
        """Handle getting current frame."""
        try:
            frame = self.text_manager.get_current_frame()
            if frame:
                self.send_json_response({'success': True, 'frame': frame})
            else:
                self.send_error_response('No current frame')
        except Exception as e:
            self.send_error_response(f"Failed to get current frame: {e}")
    
    def handle_navigate_frame(self):
        """Handle navigating to a specific frame."""
        try:
            data = self.get_request_data()
            frame_index = data.get('frame_index', 0)
            
            frame = self.text_manager.navigate_to_frame(frame_index)
            if frame:
                self.send_json_response({'success': True, 'frame': frame})
            else:
                self.send_error_response('Invalid frame index')
        except Exception as e:
            self.send_error_response(f"Failed to navigate to frame: {e}")
    
    def handle_next_frame(self):
        """Handle navigating to next frame."""
        try:
            frame = self.text_manager.next_frame()
            if frame:
                self.send_json_response({'success': True, 'frame': frame})
            else:
                self.send_error_response('No next frame available')
        except Exception as e:
            self.send_error_response(f"Failed to navigate to next frame: {e}")
    
    def handle_previous_frame(self):
        """Handle navigating to previous frame."""
        try:
            frame = self.text_manager.previous_frame()
            if frame:
                self.send_json_response({'success': True, 'frame': frame})
            else:
                self.send_error_response('No previous frame available')
        except Exception as e:
            self.send_error_response(f"Failed to navigate to previous frame: {e}")
    
    def handle_get_frames_by_page(self):
        """Handle getting frames by page."""
        try:
            data = self.get_request_data()
            page_name = data.get('page_name', '')
            
            frames = self.text_manager.get_frames_by_page(page_name)
            self.send_json_response({'success': True, 'frames': frames, 'count': len(frames)})
        except Exception as e:
            self.send_error_response(f"Failed to get frames by page: {e}")
    
    def handle_get_page_names(self):
        """Handle getting page names."""
        try:
            page_names = self.text_manager.get_page_names()
            self.send_json_response({'success': True, 'page_names': page_names})
        except Exception as e:
            self.send_error_response(f"Failed to get page names: {e}")
    
    def handle_search_text(self):
        """Handle searching text."""
        try:
            data = self.get_request_data()
            search_term = data.get('search_term', '')
            
            results = self.text_manager.search_text(search_term)
            self.send_json_response({'success': True, 'results': results, 'count': len(results)})
        except Exception as e:
            self.send_error_response(f"Failed to search text: {e}")
    
    def handle_get_statistics(self):
        """Handle getting document statistics."""
        try:
            stats = self.text_manager.get_document_statistics()
            self.send_json_response({'success': True, 'statistics': stats})
        except Exception as e:
            self.send_error_response(f"Failed to get statistics: {e}")
    
    def handle_update_text(self):
        """Handle updating text content."""
        try:
            data = self.get_request_data()
            frame_index = data.get('frame_index', 0)
            new_content = data.get('content', '')
            
            success = self.text_manager.update_text_content(frame_index, new_content)
            if success:
                self.send_json_response({'success': True, 'message': 'Text updated successfully'})
            else:
                self.send_error_response('Failed to update text')
        except Exception as e:
            self.send_error_response(f"Failed to update text: {e}")

def main():
    """Main function to start the web server."""
    # Setup logging
    logging.basicConfig(level=logging.INFO)
    logger = logging.getLogger(__name__)
    
    # Server configuration
    PORT = 8081
    HOST = 'localhost'
    
    try:
        # Create server
        server = HTTPServer((HOST, PORT), WebHandler)
        logger.info(f"Starting InDesign Writer Helper server on http://{HOST}:{PORT}")
        
        # Start server in a separate thread
        server_thread = threading.Thread(target=server.serve_forever)
        server_thread.daemon = True
        server_thread.start()
        
        logger.info("Server started successfully!")
        logger.info("Press Ctrl+C to stop the server")
        
        # Keep the main thread alive
        try:
            while True:
                time.sleep(1)
        except KeyboardInterrupt:
            logger.info("Shutting down server...")
            server.shutdown()
            server.server_close()
            logger.info("Server stopped")
            
    except Exception as e:
        logger.error(f"Failed to start server: {e}")
        return 1
    
    return 0

if __name__ == "__main__":
    sys.exit(main())
