#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Basic test script for InDesign Write Assistant
"""

import os
import sys
import json

def test_basic_imports():
    """Test basic imports."""
    print("Testing basic imports...")
    
    try:
        import os
        print("✓ os module imported")
    except Exception as e:
        print(f"✗ Failed to import os: {e}")
        
    try:
        import sys
        print("✓ sys module imported")
    except Exception as e:
        print(f"✗ Failed to import sys: {e}")
        
    try:
        import json
        print("✓ json module imported")
    except Exception as e:
        print(f"✗ Failed to import json: {e}")
        
    try:
        import socket
        print("✓ socket module imported")
    except Exception as e:
        print(f"✗ Failed to import socket: {e}")
        
    try:
        import threading
        print("✓ threading module imported")
    except Exception as e:
        print(f"✗ Failed to import threading: {e}")

def test_file_operations():
    """Test file operations."""
    print("\nTesting file operations...")
    
    try:
        # Test reading a file
        with open('launcher.html', 'r', encoding='utf-8') as f:
            content = f.read()
            print(f"✓ Successfully read launcher.html ({len(content)} characters)")
    except Exception as e:
        print(f"✗ Failed to read launcher.html: {e}")
        
    try:
        # Test JSON operations
        test_data = {"status": "ready", "message": "test"}
        json_str = json.dumps(test_data)
        parsed_data = json.loads(json_str)
        print("✓ JSON operations work correctly")
    except Exception as e:
        print(f"✗ Failed JSON operations: {e}")

def test_socket_operations():
    """Test socket operations."""
    print("\nTesting socket operations...")
    
    try:
        import socket
        # Test creating a socket
        test_socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        test_socket.close()
        print("✓ Socket creation works")
    except Exception as e:
        print(f"✗ Failed socket operations: {e}")

def main():
    """Main test function."""
    print("InDesign Writer Helper - Basic Tests")
    print("=" * 40)
    
    test_basic_imports()
    test_file_operations()
    test_socket_operations()
    
    print("\n" + "=" * 40)
    print("Basic tests completed!")

if __name__ == "__main__":
    main()
