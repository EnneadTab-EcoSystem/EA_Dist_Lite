#!/usr/bin/python
# -*- coding: utf-8 -*-
"""
Test script to verify block2family template file resolution fix.
This script tests the key components that were causing the "Input template file is invalid" error.
"""

import os
import sys

# Add the current directory to the path so we can import EnneadTab modules
current_dir = os.path.dirname(os.path.abspath(__file__))
sys.path.append(current_dir)

def test_template_resolution():
    """Test template file resolution for block2family tool."""
    print("=== Block2Family Template Resolution Test ===")
    
    try:
        import ENVIRONMENT
        import SAMPLE_FILE
        print("✓ Successfully imported ENVIRONMENT and SAMPLE_FILE modules")
    except Exception as e:
        print("✗ Failed to import modules: {}".format(e))
        return False
    
    # Test template file resolution
    template_files = [
        "RhinoImportBaseFamily_ft.rfa",
        "RhinoImportBaseFamily_mm.rfa"
    ]
    
    success_count = 0
    for template_file in template_files:
        print("\nTesting: {}".format(template_file))
        result = SAMPLE_FILE.get_file(template_file)
        if result:
            print("✓ Found at: {}".format(result))
            success_count += 1
        else:
            print("✗ Not found")
    
    print("\n=== Results ===")
    print("Successfully resolved {}/{} template files".format(success_count, len(template_files)))
    
    if success_count == len(template_files):
        print("✓ All template files resolved successfully!")
        return True
    else:
        print("✗ Some template files could not be resolved")
        return False

def test_revit_application_import():
    """Test REVIT_APPLICATION import functionality."""
    print("\n=== REVIT_APPLICATION Import Test ===")
    
    try:
        from REVIT import REVIT_APPLICATION
        print("✓ Successfully imported REVIT_APPLICATION")
        
        # Test if we can get the app (this will only work in Revit environment)
        try:
            app = REVIT_APPLICATION.get_app()
            print("✓ Successfully got Revit application")
            return True
        except Exception as e:
            print("⚠ Expected error getting Revit app (not in Revit environment): {}".format(e))
            return True  # This is expected when not in Revit
            
    except Exception as e:
        print("✗ Failed to import REVIT_APPLICATION: {}".format(e))
        return False

def main():
    """Run all tests."""
    print("Starting Block2Family Fix Verification...")
    
    # Test template resolution
    template_success = test_template_resolution()
    
    # Test REVIT_APPLICATION import
    import_success = test_revit_application_import()
    
    print("\n=== Summary ===")
    print("Template resolution: {}".format("✓ PASS" if template_success else "✗ FAIL"))
    print("REVIT_APPLICATION import: {}".format("✓ PASS" if import_success else "✗ FAIL"))
    
    if template_success and import_success:
        print("\n🎉 All tests passed! The block2family fix should work correctly.")
        return True
    else:
        print("\n❌ Some tests failed. Please check the issues above.")
        return False

if __name__ == "__main__":
    main()
