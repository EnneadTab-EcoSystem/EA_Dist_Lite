#!/usr/bin/python
# -*- coding: utf-8 -*-

"""
NYU CAD Layer Standards Mapping
This module contains the mapping between Revit BuiltInCategory constants and NYU CAD layer standards.
Based on the official NYU CAD Layer Standards table.

For reference, see: https://www.revitapidocs.com/2026/ba1c5b30-242f-5fdc-8ea9-ec3b61e6e722.htm
"""

import traceback
from Autodesk.Revit import DB # pyright: ignore

def validate_builtin_category(constant_name):
    """Test if a BuiltInCategory constant exists and is valid"""
    try:
        # Try to get the constant from DB.BuiltInCategory
        constant = getattr(DB.BuiltInCategory, constant_name)
        # Test if it's a valid BuiltInCategory enum value
        if isinstance(constant, DB.BuiltInCategory):
            return True, constant
        else:
            return False, None
    except AttributeError:
        return False, None

def show_all_available_ost_constants():
    """Display all available OST_ constants from BuiltInCategory"""
    print("=== All Available OST_ Constants ===")
    available_constants = []
    
    for attr in dir(DB.BuiltInCategory):
        if attr.startswith('OST_'):
            try:
                constant = getattr(DB.BuiltInCategory, attr)
                if isinstance(constant, DB.BuiltInCategory):
                    available_constants.append(attr)
                    print("✓ {}".format(attr))
            except:
                pass
    
    print("\n=== Summary ===")
    print("Total available OST_ constants: {}".format(len(available_constants)))
    return available_constants

def build_nyu_layer_mapping():
    """Dynamically build the NYU layer mapping, testing each constant"""
    
    # Raw mapping data - all potential entries (removed the 6 failed constants)
    raw_mapping_data = {
        # Architectural Elements
        "Walls/Interior": {"constant": "OST_Walls", "dwg_layer": "A-WALL-INTR", "color": 3},
        "Walls/Exterior": {"constant": "OST_Walls", "dwg_layer": "A-WALL-EXTR", "color": 5},
        "Doors": {"constant": "OST_Doors", "dwg_layer": "A-DOOR", "color": 1},
        "Door Identification": {"constant": "OST_Doors", "dwg_layer": "A-DOOR-IDEN", "color": 4},
        "Windows": {"constant": "OST_Windows", "dwg_layer": "A-WNDW", "color": 4},
        "Floors": {"constant": "OST_Floors", "dwg_layer": "A-FLOR", "color": 2},
        "Floor - Elevator": {"constant": "OST_Floors", "dwg_layer": "A-FLOR-EVTR", "color": 2},
        "Floor - Grating": {"constant": "OST_Floors", "dwg_layer": "A-FLOR-GRATE", "color": 2},
        "Floor - Shaft": {"constant": "OST_Floors", "dwg_layer": "A-FLOR-SHFT", "color": 2},
        "Floor - Stairs": {"constant": "OST_Stairs", "dwg_layer": "A-FLOR-STRS", "color": 2},
        "Ceilings": {"constant": "OST_Ceilings", "dwg_layer": "A-CLNG", "color": 2},
        "Roofs": {"constant": "OST_Roofs", "dwg_layer": "A-ROOF", "color": 1},
        "Curbs": {"constant": "OST_GenericModel", "dwg_layer": "A-CURB", "color": 2},
        "Signage": {"constant": "OST_GenericModel", "dwg_layer": "A-FLOR-SIGN", "color": 1},
        "Room Numbers": {"constant": "OST_Rooms", "dwg_layer": "A-FLOR-IDEN-ROOM", "color": 7},
        "Room Names": {"constant": "OST_Rooms", "dwg_layer": "A-FLOR-IDEN-TEXT", "color": 7},
        "Pre-EPIC Room Numbers": {"constant": "OST_Rooms", "dwg_layer": "A-FLOR-IDEN-PRE-EPIC", "color": 7},
        
        # Structural Elements
        "Structural Columns": {"constant": "OST_StructuralColumns", "dwg_layer": "S-COLS", "color": 2},
        "Grids": {"constant": "OST_Grids", "dwg_layer": "S-GRID", "color": 2},
        
        # Electrical Elements
        "Lighting Fixtures": {"constant": "OST_LightingFixtures", "dwg_layer": "E-LITE", "color": 3},
        "Lighting Devices": {"constant": "OST_LightingDevices", "dwg_layer": "E-LITE", "color": 3},
        "Exit Lighting": {"constant": "OST_LightingFixtures", "dwg_layer": "E-LITE-EXIT", "color": 3},
        "Electrical Equipment": {"constant": "OST_ElectricalEquipment", "dwg_layer": "E-POWR-WALL", "color": 3},
        "Electrical Fixtures": {"constant": "OST_ElectricalFixtures", "dwg_layer": "E-POWR-WALL", "color": 3},
        "Security Devices": {"constant": "OST_SecurityDevices", "dwg_layer": "E-SAFETY-CRDRDR", "color": 3},
        "Communication Devices": {"constant": "OST_CommunicationDevices", "dwg_layer": "E-SAFETY-ICDB", "color": 3},
        
        # Mechanical Elements
        "Mechanical Equipment": {"constant": "OST_MechanicalEquipment", "dwg_layer": "M-HVAC-EQPM", "color": 6},
        "Duct Curves": {"constant": "OST_DuctCurves", "dwg_layer": "M-HVAC-EQPM", "color": 6},
        "Duct Fitting": {"constant": "OST_DuctFitting", "dwg_layer": "M-HVAC-EQPM", "color": 6},
        "Duct Accessory": {"constant": "OST_DuctAccessory", "dwg_layer": "M-HVAC-EQPM", "color": 6},
        "Mechanical Control Devices": {"constant": "OST_MechanicalControlDevices", "dwg_layer": "M-HVAC-EQPM", "color": 6},
        "Zone Equipment": {"constant": "OST_ZoneEquipment", "dwg_layer": "M-HVAC-EQPM", "color": 6},
        
        # Plumbing Elements
        "Plumbing Fixtures": {"constant": "OST_PlumbingFixtures", "dwg_layer": "P-FIXT", "color": 6},
        "Plumbing Equipment": {"constant": "OST_PlumbingEquipment", "dwg_layer": "P-FIXT", "color": 6},
        "Pipe Curves": {"constant": "OST_PipeCurves", "dwg_layer": "P-FIXT", "color": 6},
        "Pipe Fitting": {"constant": "OST_PipeFitting", "dwg_layer": "P-FIXT", "color": 6},
        "Pipe Accessory": {"constant": "OST_PipeAccessory", "dwg_layer": "P-FIXT", "color": 6},
        "Sprinklers": {"constant": "OST_Sprinklers", "dwg_layer": "P-SAFETY-SHWSH", "color": 6},
        
        # Interior Elements
        "Furniture": {"constant": "OST_Furniture", "dwg_layer": "I-FURN", "color": 6},
        "Furniture Systems": {"constant": "OST_FurnitureSystems", "dwg_layer": "I-FURN", "color": 6},
        "Casework": {"constant": "OST_Casework", "dwg_layer": "I-MILLWORK", "color": 6},
        "Medical Equipment": {"constant": "OST_MedicalEquipment", "dwg_layer": "I-EQPM-FIX", "color": 6},
        "Food Service Equipment": {"constant": "OST_FoodServiceEquipment", "dwg_layer": "I-EQPM-FIX", "color": 6},
        "Nurse Call Devices": {"constant": "OST_NurseCallDevices", "dwg_layer": "I-EQPM-FIX", "color": 6},
        
        # Site/Landscaping Elements
        "Site": {"constant": "OST_Site", "dwg_layer": "L-SITE", "color": 4},
        "Planting": {"constant": "OST_Planting", "dwg_layer": "L-SITE", "color": 4},
        "Hardscape": {"constant": "OST_Hardscape", "dwg_layer": "L-SITE", "color": 4},
        "Roads": {"constant": "OST_Roads", "dwg_layer": "L-SITE", "color": 4},
        "Parking": {"constant": "OST_Parking", "dwg_layer": "L-SITE", "color": 4},
        
        # General/Annotation Elements
        "Generic Model": {"constant": "OST_GenericModel", "dwg_layer": "G-ANNO-SYMB", "color": 7},
        "Detail Items": {"constant": "OST_DetailComponents", "dwg_layer": "G-ANNO-SYMB", "color": 7},
        "Generic Annotation": {"constant": "OST_GenericAnnotation", "dwg_layer": "G-ANNO-TEXT", "color": 7},
        "Title Blocks": {"constant": "OST_TitleBlocks", "dwg_layer": "G-ANNO-TTLB", "color": 7},
        "Title Block Text": {"constant": "OST_TitleBlocks", "dwg_layer": "G-ANNO-TTLB-TEXT", "color": 7},
        "Logo": {"constant": "OST_TitleBlocks", "dwg_layer": "G-LOGO", "color": 7},
        "Scale": {"constant": "OST_GenericAnnotation", "dwg_layer": "G-SCALE", "color": 7},
        "Viewports": {"constant": "OST_Viewports", "dwg_layer": "G-VP", "color": 7},
        "Levels": {"constant": "OST_Levels", "dwg_layer": "G-ANNO-TEXT", "color": 7},
        "Sections": {"constant": "OST_Sections", "dwg_layer": "G-ANNO-TEXT", "color": 7},
        "Elevation Marks": {"constant": "OST_ElevationMarks", "dwg_layer": "G-ANNO-TEXT", "color": 7},
        "Callout Heads": {"constant": "OST_CalloutHeads", "dwg_layer": "G-ANNO-TEXT", "color": 7},
        "Defpoints": {"constant": "OST_Lines", "dwg_layer": "DEFPOINTS", "color": 7},
        
        # Telecomm Elements
        "Telephone Devices": {"constant": "OST_TelephoneDevices", "dwg_layer": "T-JACK", "color": 3},
        "Data Devices": {"constant": "OST_DataDevices", "dwg_layer": "T-JACK", "color": 3},
    }
    
    # Test each constant and build the final mapping
    valid_mapping = {}
    failed_constants = []
    
    print("=== Testing BuiltInCategory Constants ===")
    
    for human_name, data in raw_mapping_data.items():
        constant_name = data["constant"]
        try:
            is_valid, constant = validate_builtin_category(constant_name)
            
            if is_valid:
                valid_mapping[human_name] = {
                    "OST": constant,
                    "dwg_layer": data["dwg_layer"],
                    "color": data["color"]
                }
                print("✓ {} -> {}".format(human_name, constant_name))
            else:
                failed_constants.append((human_name, constant_name))
                print("✗ {} -> {} (FAILED)".format(human_name, constant_name))
        except Exception as e:
            failed_constants.append((human_name, constant_name))
            print("✗ {} -> {} (ERROR: {})".format(human_name, constant_name, str(e)))
    
    print("\n=== Summary ===")
    print("Valid constants: {}".format(len(valid_mapping)))
    print("Failed constants: {}".format(len(failed_constants)))
    
    if failed_constants:
        print("\n=== Failed Constants to Eliminate ===")
        for human_name, constant_name in failed_constants:
            print("'{}': '{}',".format(human_name, constant_name))
    
    # Add default fallback
    valid_mapping["DEFAULT"] = {
        "OST": None,
        "dwg_layer": "G-ANNO-TEXT",
        "color": 7
    }
    
    return valid_mapping

# Try to build the mapping dynamically, with detailed error handling
try:
    print("=== Starting NYU Layer Mapping Initialization ===")
    NYU_LAYER_MAPPING = build_nyu_layer_mapping()
    print("=== NYU Layer Mapping Initialization Completed Successfully ===")
except Exception as e:
    print("=== ERROR: Failed to initialize NYU_LAYER_MAPPING ===")
    print("Error Type: {}".format(type(e).__name__))
    print("Error Message: {}".format(str(e)))
    print("\n=== Full Traceback ===")
    print(traceback.format_exc())
    print("\n")
    show_all_available_ost_constants()
    
    # Create a minimal fallback mapping
    NYU_LAYER_MAPPING = {
        "DEFAULT": {
            "OST": None,
            "dwg_layer": None,
            "color": 7
        }
    }

def get_nyu_layer_info(category_name):
    """Get NYU layer information for a given category name or BuiltInCategory"""
    # If category_name is a BuiltInCategory, find the mapping by OST value
    if hasattr(category_name, 'IntegerValue'):
        # It's a BuiltInCategory enum
        for human_name, mapping_info in NYU_LAYER_MAPPING.items():
            if mapping_info.get("OST") == category_name:
                return mapping_info
        return NYU_LAYER_MAPPING["DEFAULT"]
    
    # If category_name is a string, try to find by human name
    return NYU_LAYER_MAPPING.get(category_name, NYU_LAYER_MAPPING["DEFAULT"])
