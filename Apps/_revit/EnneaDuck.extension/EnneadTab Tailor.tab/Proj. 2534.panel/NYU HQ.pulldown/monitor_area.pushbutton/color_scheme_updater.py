#!/usr/bin/python
# -*- coding: utf-8 -*-

"""
Color Scheme Updater Module
Updates Revit color schemes based on color hierarchy from Excel
"""

import config
from EnneadTab import COLOR
from EnneadTab.REVIT import REVIT_COLOR_SCHEME, REVIT_SELECTION

try:
    from Autodesk.Revit import DB # pyright: ignore
except:
    pass


def hex_to_revit_color(hex_color):
    """
    Convert hex color string to Revit Color object
    
    Args:
        hex_color (str): Hex color string like "#rrggbb"
    
    Returns:
        DB.Color: Revit Color object
    """
    rgb = COLOR.hex_to_rgb(hex_color)
    return COLOR.tuple_to_color(rgb)


def update_color_scheme_from_dict(doc, color_scheme_name, color_dict):
    """
    Update a Revit color scheme with colors from a dictionary
    
    Args:
        doc: Revit document
        color_scheme_name (str): Name of the color scheme to update
        color_dict (dict): Dictionary mapping entry names to hex colors
                          e.g. {'DEPARTMENT_NAME': '#rrggbb', ...}
    
    Returns:
        bool: True if successful, False otherwise
    """
    if not color_dict:
        print("No color data provided for scheme '{}'".format(color_scheme_name))
        return False
    
    # Get the color scheme
    color_schemes = REVIT_COLOR_SCHEME.get_color_schemes_by_name(color_scheme_name, doc)
    if not color_schemes:
        print("Color scheme '{}' not found in document".format(color_scheme_name))
        return False
    
    for color_scheme in color_schemes:
    
        # Get storage type from existing entry (must have at least one placeholder)
        try:
            sample_entry = list(color_scheme.GetEntries())[0]
            storage_type = sample_entry.StorageType
        except:
            print("Color scheme '{}' has no entries. Please add at least one placeholder entry.".format(color_scheme_name))
            return False
        
        # Get current entry names
        current_entries = {x.GetStringValue(): x for x in color_scheme.GetEntries()}
        
        entries_added = 0
        entries_updated = 0
        
        # Add or update entries
        for entry_name, hex_color in color_dict.items():
            if not hex_color or not hex_color.startswith('#'):
                continue
            
            revit_color = hex_to_revit_color(hex_color)
            
            if entry_name in current_entries:
                # Update existing entry
                existing_entry = current_entries[entry_name]
                old_color = existing_entry.Color
                
                # Check if color needs updating
                if not COLOR.is_same_color(old_color, revit_color):
                    existing_entry.Color = revit_color
                    color_scheme.UpdateEntry(existing_entry)
                    entries_updated += 1
                    print("  Updated '{}': {} -> {}".format(
                        entry_name,
                        COLOR.rgb_to_hex((old_color.Red, old_color.Green, old_color.Blue)),
                        hex_color
                    ))
            else:
                # Add new entry
                entry = DB.ColorFillSchemeEntry(storage_type)
                entry.Color = revit_color
                entry.SetStringValue(entry_name)
                entry.FillPatternId = REVIT_SELECTION.get_solid_fill_pattern_id(doc)
                color_scheme.AddEntry(entry)
                entries_added += 1
                print("  Added '{}': {}".format(entry_name, hex_color))
        
        print("Color scheme '{}': {} added, {} updated".format(
            color_scheme_name, entries_added, entries_updated
        ))
    
    return True


def update_all_color_schemes(doc, color_hierarchy):
    """
    Update all three color schemes (Department, Division, Room Name) from color hierarchy
    
    Args:
        doc: Revit document
        color_hierarchy (dict): Dictionary with keys 'department', 'division', 'room_name'
                               Each containing name->hex color mappings
    """
    # Get scheme mapping from config
    scheme_mapping = config.COLOR_SCHEME_NAMES
    
    print("\nUpdating color schemes from Excel...")
    
    t = DB.Transaction(doc, "Update Color Schemes from Excel")
    t.Start()
    
    success_count = 0
    for hierarchy_key, scheme_name in scheme_mapping.items():
        color_dict = color_hierarchy.get(hierarchy_key, {})
        if color_dict:
            print("\nProcessing '{}' ({} colors)...".format(scheme_name, len(color_dict)))
            if update_color_scheme_from_dict(doc, scheme_name, color_dict):
                success_count += 1
        else:
            print("No colors found for '{}'".format(scheme_name))
    
    t.Commit()
    
    print("\nColor scheme update complete: {}/{} schemes updated".format(
        success_count, len(scheme_mapping)
    ))

