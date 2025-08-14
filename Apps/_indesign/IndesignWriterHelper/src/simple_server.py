#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Simple HTTP Server for InDesign Writer Helper
A basic HTTP server implementation using sockets.
"""

import os
import sys
import json
import socket
import threading
import time
from urllib.parse import urlparse, parse_qs

class SimpleHTTPServer:
    def __init__(self, host='localhost', port=8081):
        self.host = host
        self.port = port
        self.server_socket = None
        self.running = False
        
    def start(self):
        """Start the HTTP server."""
        try:
            # Check if Python is available
            import subprocess
            try:
                subprocess.run(['python', '--version'], capture_output=True, check=True)
            except (subprocess.CalledProcessError, FileNotFoundError):
                print("ERROR: Python is not installed on this computer.")
                print("Please install Python 3.13 from the Microsoft Store:")
                print("https://www.microsoft.com/store/apps/9PJPW5LDXLZ5")
                return
            
            self.server_socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            self.server_socket.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
            self.server_socket.bind((self.host, self.port))
            self.server_socket.listen(5)
            self.running = True
            
            print(f"Server started on http://{self.host}:{self.port}")
            
            while self.running:
                try:
                    client_socket, address = self.server_socket.accept()
                    client_thread = threading.Thread(target=self.handle_client, args=(client_socket,))
                    client_thread.daemon = True
                    client_thread.start()
                except Exception as e:
                    if self.running:
                        print(f"Error accepting connection: {e}")
                        
        except Exception as e:
            print(f"Failed to start server: {e}")
            
    def stop(self):
        """Stop the HTTP server."""
        self.running = False
        if self.server_socket:
            self.server_socket.close()
            
    def handle_client(self, client_socket):
        """Handle a client connection."""
        try:
            request = client_socket.recv(1024).decode('utf-8')
            if not request:
                return
                
            lines = request.split('\n')
            if not lines:
                return
                
            # Parse request line
            request_line = lines[0].strip()
            parts = request_line.split()
            if len(parts) < 2:
                return
                
            method = parts[0]
            path = parts[1]
            
            # Handle different paths
            if method == 'GET':
                self.handle_get(client_socket, path)
            elif method == 'POST':
                self.handle_post(client_socket, path, request)
            else:
                self.send_response(client_socket, 405, "Method Not Allowed")
                
        except Exception as e:
            print(f"Error handling client: {e}")
        finally:
            client_socket.close()
            
    def handle_get(self, client_socket, path):
        """Handle GET requests."""
        if path == '/':
            path = '/launcher.html'
        elif path == '/api/status':
            self.send_json_response(client_socket, {'status': 'ready'})
            return
            
        # Serve static files
        file_path = os.path.join(os.path.dirname(__file__), path.lstrip('/'))
        if os.path.exists(file_path) and os.path.isfile(file_path):
            self.serve_file(client_socket, file_path)
        else:
            self.send_response(client_socket, 404, "File Not Found")
            
    def handle_post(self, client_socket, path, request):
        """Handle POST requests."""
        if path == '/api/status':
            self.send_json_response(client_socket, {'status': 'ready'})
        else:
            self.send_response(client_socket, 404, "API endpoint not found")
            
    def serve_file(self, client_socket, file_path):
        """Serve a static file."""
        try:
            with open(file_path, 'rb') as f:
                content = f.read()
                
            # Determine content type
            ext = os.path.splitext(file_path)[1].lower()
            content_types = {
                '.html': 'text/html',
                '.css': 'text/css',
                '.js': 'application/javascript',
                '.png': 'image/png',
                '.jpg': 'image/jpeg',
                '.jpeg': 'image/jpeg',
                '.gif': 'image/gif',
                '.ico': 'image/x-icon'
            }
            content_type = content_types.get(ext, 'text/plain')
            
            response = f"HTTP/1.1 200 OK\r\n"
            response += f"Content-Type: {content_type}; charset=utf-8\r\n"
            response += f"Content-Length: {len(content)}\r\n"
            response += "Access-Control-Allow-Origin: *\r\n"
            response += "\r\n"
            
            client_socket.send(response.encode('utf-8'))
            client_socket.send(content)
            
        except Exception as e:
            print(f"Error serving file {file_path}: {e}")
            self.send_response(client_socket, 500, "Internal Server Error")
            
    def send_json_response(self, client_socket, data):
        """Send JSON response."""
        content = json.dumps(data).encode('utf-8')
        response = "HTTP/1.1 200 OK\r\n"
        response += "Content-Type: application/json\r\n"
        response += f"Content-Length: {len(content)}\r\n"
        response += "Access-Control-Allow-Origin: *\r\n"
        response += "\r\n"
        
        client_socket.send(response.encode('utf-8'))
        client_socket.send(content)
        
    def send_response(self, client_socket, status_code, message):
        """Send a simple response."""
        response = f"HTTP/1.1 {status_code} {message}\r\n"
        response += "Content-Type: text/plain\r\n"
        response += "Access-Control-Allow-Origin: *\r\n"
        response += "\r\n"
        response += message
        
        client_socket.send(response.encode('utf-8'))

def main():
    """Main function to start the server."""
    server = SimpleHTTPServer()
    
    try:
        print("Starting InDesign Writer Helper server...")
        server.start()
    except KeyboardInterrupt:
        print("\nShutting down server...")
        server.stop()
        print("Server stopped")

if __name__ == "__main__":
    main()
