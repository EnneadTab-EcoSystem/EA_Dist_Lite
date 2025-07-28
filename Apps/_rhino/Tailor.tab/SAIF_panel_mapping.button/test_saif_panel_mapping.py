"""
Test script for SAIF Panel Mapping functionality.
This script tests the error handling and validation improvements.
"""

import rhinoscriptsyntax as rs
import scriptcontext as sc
import Rhino

def test_block_validation():
    """Test block validation functionality."""
    print("Testing block validation...")
    
    # Test with non-existent block
    non_existent_blocks = [
        "Vertical 400 01_SYSTEM_01",
        "Vertical 700 01_SYSTEM_01", 
        "Vertical 1000 01_SYSTEM_01",
        "FR WIDOW_SYSTEM_01"
    ]
    
    for block_name in non_existent_blocks:
        print(f"Testing block: {block_name}")
        
        # Check if block definition exists
        doc = Rhino.RhinoDoc.ActiveDoc
        if doc:
            block_def = doc.InstanceDefinitions.Find(block_name)
            if block_def:
                print(f"  ✓ Block definition '{block_name}' exists")
                instances = rs.BlockInstances(block_name)
                if instances:
                    print(f"  ✓ Found {len(instances)} instances")
                else:
                    print(f"  ⚠ No instances found for '{block_name}'")
            else:
                print(f"  ✗ Block definition '{block_name}' does not exist")
        else:
            print("  ✗ No active Rhino document")
    
    print("Block validation test completed.\n")

def test_available_blocks():
    """List all available blocks in the current document."""
    print("Available blocks in current document:")
    
    doc = Rhino.RhinoDoc.ActiveDoc
    if not doc:
        print("No active Rhino document found")
        return
    
    available_blocks = []
    for i in range(doc.InstanceDefinitions.Count):
        block_def = doc.InstanceDefinitions[i]
        if block_def:
            available_blocks.append(block_def.Name)
    
    if available_blocks:
        for i, block_name in enumerate(available_blocks, 1):
            print(f"  {i}. {block_name}")
    else:
        print("  No blocks found in document")
    
    print(f"Total blocks: {len(available_blocks)}\n")

def test_safe_block_instances():
    """Test the safe block instances function."""
    print("Testing safe block instances function...")
    
    # Import the function from the main script
    import sys
    import os
    
    # Add the current directory to path
    current_dir = os.path.dirname(__file__)
    if current_dir not in sys.path:
        sys.path.append(current_dir)
    
    try:
        from SAIF_panel_mapping_left import get_block_instances_safely
        
        test_blocks = [
            "Vertical 400 01_SYSTEM_01",
            "Vertical 700 01_SYSTEM_01",
            "NonExistentBlock",
            "AnotherTestBlock"
        ]
        
        for block_name in test_blocks:
            print(f"Testing safe instances for: {block_name}")
            instances = get_block_instances_safely(block_name)
            if instances:
                print(f"  ✓ Found {len(instances)} instances")
            else:
                print(f"  ⚠ No instances found (this is expected for non-existent blocks)")
                
    except ImportError as e:
        print(f"Could not import function: {e}")
    except Exception as e:
        print(f"Error during test: {e}")
    
    print("Safe block instances test completed.\n")

def main():
    """Run all tests."""
    print("=" * 60)
    print("SAIF Panel Mapping Test Suite")
    print("=" * 60)
    
    test_available_blocks()
    test_block_validation()
    test_safe_block_instances()
    
    print("=" * 60)
    print("Test suite completed!")
    print("=" * 60)
    
    print("\nRecommendations:")
    print("1. If the required blocks don't exist, create them or import them")
    print("2. Make sure the block names match exactly (case-sensitive)")
    print("3. The script will now handle missing blocks gracefully")
    print("4. Check the console output for detailed error messages")

if __name__ == "__main__":
    main() 