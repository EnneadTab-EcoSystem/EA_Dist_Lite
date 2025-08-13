#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
InDesign Link Repather - Main Entry Point
A tool to repath all links in an InDesign document when folders are renamed.
"""

# Import the modular components
from generate_web_app import start_server, test_web_server

if __name__ == "__main__":
    print("InDesign Link Repather")
    print("=" * 50)
    
    # Test components first
    test_web_server()
    
    # Start the server
    print("\nStarting web server...")
    start_server()
