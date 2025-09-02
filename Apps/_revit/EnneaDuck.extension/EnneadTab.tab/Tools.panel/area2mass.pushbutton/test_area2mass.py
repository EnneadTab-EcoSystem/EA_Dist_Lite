#!/usr/bin/python
# -*- coding: utf-8 -*-

"""Test script for Area2Mass functionality."""

import os
import sys

# Add the current directory to the path so we can import our modules
current_dir = os.path.dirname(os.path.abspath(__file__))
if current_dir not in sys.path:
    sys.path.insert(0, current_dir)

def test_imports():
    """Test if all required modules can be imported."""
    print("Testing module imports...")
    
    try:
        from data_extractors import ElementInfoExtractor, BoundaryDataExtractor
        print("✓ data_extractors imported successfully")
    except ImportError as e:
        print("✗ Failed to import data_extractors: {}".format(e))
        return False
    
    try:
        from template_finder import TemplateFinder
        print("✓ template_finder imported successfully")
    except ImportError as e:
        print("✗ Failed to import template_finder: {}".format(e))
        return False
    
    try:
        from mass_family_creator import MassFamilyCreator
        print("✓ mass_family_creator imported successfully")
    except ImportError as e:
        print("✗ Failed to import mass_family_creator: {}".format(e))
        return False
    
    try:
        from family_loader import FamilyLoader
        print("✓ family_loader imported successfully")
    except ImportError as e:
        print("✗ Failed to import family_loader: {}".format(e))
        return False
    
    try:
        from instance_placer import FamilyInstancePlacer
        print("✓ instance_placer imported successfully")
    except ImportError as e:
        print("✗ Failed to import instance_placer: {}".format(e))
        return False
    
    try:
        from area2mass_script import Area2MassConverter
        print("✓ area2mass_script imported successfully")
    except ImportError as e:
        print("✗ Failed to import area2mass_script: {}".format(e))
        return False
    
    print("All modules imported successfully!")
    return True

def test_template_finder():
    """Test the template finder functionality."""
    print("\nTesting template finder...")
    
    try:
        from template_finder import TemplateFinder
        
        finder = TemplateFinder()
        print("✓ TemplateFinder instance created")
        
        # Test template options for different Revit versions
        for version in [2017, 2018, 2020, 2023]:
            options = finder.get_template_options(version)
            print("  Revit {}: {} template options".format(version, len(options)))
        
        # Test debug summary
        summary = finder.get_debug_summary()
        print("✓ Debug summary generated ({} lines)".format(len(summary.split('\n'))))
        
        return True
        
    except Exception as e:
        print("✗ Template finder test failed: {}".format(e))
        return False

def test_data_extractors():
    """Test the data extractors functionality."""
    print("\nTesting data extractors...")
    
    try:
        from data_extractors import ElementInfoExtractor, BoundaryDataExtractor
        
        # Test with mock data (since we don't have actual Revit elements)
        print("✓ Data extractor classes imported")
        
        # Test name sanitization logic
        test_names = [
            "Normal Name",
            "Name with <invalid> chars",
            "Name:with:colons",
            "Very long name that exceeds the maximum allowed length for Revit family names",
            ""
        ]
        
        for name in test_names:
            # Create a mock extractor to test sanitization
            class MockElement:
                def __init__(self, name):
                    self.name = name
                    self.Id = "MockID"
            
            mock_element = MockElement(name)
            extractor = ElementInfoExtractor(mock_element, "Test")
            print("  '{}' -> '{}'".format(name, extractor.name))
        
        return True
        
    except Exception as e:
        print("✗ Data extractors test failed: {}".format(e))
        return False

def test_mass_family_creator():
    """Test the mass family creator functionality."""
    print("\nTesting mass family creator...")
    
    try:
        from mass_family_creator import MassFamilyCreator
        
        creator = MassFamilyCreator("test_template.rft", "TestFamily")
        print("✓ MassFamilyCreator instance created")
        
        # Test debug functionality
        creator.add_debug_info("Test debug message")
        summary = creator.get_debug_summary()
        print("✓ Debug summary generated ({} lines)".format(len(summary.split('\n'))))
        
        return True
        
    except Exception as e:
        print("✗ Mass family creator test failed: {}".format(e))
        return False

def test_family_loader():
    """Test the family loader functionality."""
    print("\nTesting family loader...")
    
    try:
        from family_loader import FamilyLoader
        
        # Test with None values since we don't have actual documents
        loader = FamilyLoader(None, "TestFamily")
        print("✓ FamilyLoader instance created")
        
        # Test debug functionality
        loader.add_debug_info("Test debug message")
        summary = loader.get_debug_summary()
        print("✓ Debug summary generated ({} lines)".format(len(summary.split('\n'))))
        
        return True
        
    except Exception as e:
        print("✗ Family loader test failed: {}".format(e))
        return False

def test_instance_placer():
    """Test the instance placer functionality."""
    print("\nTesting instance placer...")
    
    try:
        from instance_placer import FamilyInstancePlacer
        
        # Test with None values since we don't have actual documents
        placer = FamilyInstancePlacer(None, "TestFamily", None)
        print("✓ FamilyInstancePlacer instance created")
        
        # Test debug functionality
        placer.add_debug_info("Test debug message")
        summary = placer.get_debug_summary()
        print("✓ Debug summary generated ({} lines)".format(len(summary.split('\n'))))
        
        return True
        
    except Exception as e:
        print("✗ Instance placer test failed: {}".format(e))
        return False

def run_all_tests():
    """Run all tests and provide a summary."""
    print("=" * 60)
    print("AREA2MASS FUNCTIONALITY TEST")
    print("=" * 60)
    
    tests = [
        ("Module Imports", test_imports),
        ("Template Finder", test_template_finder),
        ("Data Extractors", test_data_extractors),
        ("Mass Family Creator", test_mass_family_creator),
        ("Family Loader", test_family_loader),
        ("Instance Placer", test_instance_placer)
    ]
    
    results = []
    for test_name, test_func in tests:
        try:
            result = test_func()
            results.append((test_name, result))
        except Exception as e:
            print("✗ {} test crashed: {}".format(test_name, e))
            results.append((test_name, False))
    
    # Print summary
    print("\n" + "=" * 60)
    print("TEST SUMMARY")
    print("=" * 60)
    
    passed = 0
    total = len(results)
    
    for test_name, result in results:
        status = "✓ PASS" if result else "✗ FAIL"
        print("{:<25} {}".format(test_name, status))
        if result:
            passed += 1
    
    print("-" * 60)
    print("Overall: {}/{} tests passed".format(passed, total))
    
    if passed == total:
        print("🎉 All tests passed! Area2Mass is ready to use.")
    else:
        print("⚠️  Some tests failed. Check the output above for details.")
    
    return passed == total

if __name__ == "__main__":
    success = run_all_tests()
    sys.exit(0 if success else 1)
