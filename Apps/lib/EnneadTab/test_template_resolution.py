#!/usr/bin/python
# -*- coding: utf-8 -*-
"""
Diagnostic script to test template file resolution for block2family tool.
This script helps debug issues with finding RhinoImportBaseFamily template files.
"""

import os
import sys

# Add the current directory to the path so we can import EnneadTab modules
current_dir = os.path.dirname(os.path.abspath(__file__))
sys.path.append(current_dir)

try:
    import ENVIRONMENT
    import SAMPLE_FILE
    print("✓ Successfully imported ENVIRONMENT and SAMPLE_FILE modules")
except Exception as e:
    print("✗ Failed to import modules: {}".format(e))
    sys.exit(1)

def test_template_resolution():
    """Test template file resolution for different scenarios."""
    print("\n=== Template File Resolution Test ===")
    
    # Test basic environment detection
    print("1. Environment Detection:")
    print("   - DOCUMENT_FOLDER: {}".format(ENVIRONMENT.DOCUMENT_FOLDER))
    print("   - App name: {}".format(ENVIRONMENT.get_app_name()))
    
    # Test Revit version detection if in Revit environment
    if ENVIRONMENT.get_app_name() == "revit":
        try:
            from REVIT import REVIT_APPLICATION
            revit_version = REVIT_APPLICATION.get_revit_version()
            print("   - Revit version: {}".format(revit_version))
        except Exception as e:
            print("   - Could not get Revit version: {}".format(e))
    
    # Test template file resolution
    print("\n2. Template File Resolution:")
    template_files = [
        "RhinoImportBaseFamily_ft.rfa",
        "RhinoImportBaseFamily_mm.rfa",
        "GM_Blank.rfa"  # Test with a known existing file
    ]
    
    for template_file in template_files:
        print("\n   Testing: {}".format(template_file))
        result = SAMPLE_FILE.get_file(template_file)
        if result:
            print("   ✓ Found at: {}".format(result))
        else:
            print("   ✗ Not found")
            
            # Manual path checking
            if ENVIRONMENT.get_app_name() == "revit":
                possible_paths = [
                    os.path.join(ENVIRONMENT.DOCUMENT_FOLDER, "revit", template_file),
                ]
                
                # Add version-specific paths if we can get the version
                try:
                    from REVIT import REVIT_APPLICATION
                    revit_version = REVIT_APPLICATION.get_revit_version()
                    possible_paths.insert(0, os.path.join(ENVIRONMENT.DOCUMENT_FOLDER, "revit", str(revit_version), template_file))
                except:
                    pass
                
                print("   Checking manual paths:")
                for path in possible_paths:
                    exists = os.path.exists(path)
                    print("     {}: {}".format("✓" if exists else "✗", path))
    
    print("\n3. Available Files in Documents/Revit:")
    revit_docs_path = os.path.join(ENVIRONMENT.DOCUMENT_FOLDER, "revit")
    if os.path.exists(revit_docs_path):
        print("   Base folder files:")
        for item in os.listdir(revit_docs_path):
            if os.path.isfile(os.path.join(revit_docs_path, item)):
                print("     - {}".format(item))
        
        print("   Version folders:")
        for item in os.listdir(revit_docs_path):
            item_path = os.path.join(revit_docs_path, item)
            if os.path.isdir(item_path) and item.isdigit():
                print("     - {}:".format(item))
                try:
                    for file_item in os.listdir(item_path):
                        if file_item.startswith("RhinoImportBaseFamily"):
                            print("       ✓ {}".format(file_item))
                except Exception as e:
                    print("       ✗ Error reading folder: {}".format(e))
    else:
        print("   ✗ Revit documents folder does not exist: {}".format(revit_docs_path))

if __name__ == "__main__":
    test_template_resolution()
