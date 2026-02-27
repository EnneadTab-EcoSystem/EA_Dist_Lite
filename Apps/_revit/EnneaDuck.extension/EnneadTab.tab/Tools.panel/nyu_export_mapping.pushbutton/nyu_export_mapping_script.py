#!/usr/bin/python
# -*- coding: utf-8 -*-

__doc__ = """Apply NYU CAD Layer Standards to DWG Export Settings.
This tool maps Revit categories to NYU standard layer names and colors.
All subcategories will use the parent category's layer settings."""
__title__ = "NYU Export\nCAD Layer Mapping"

__tip__ = True

from pyrevit import forms, script
from Autodesk.Revit import DB # pyright: ignore
import os
from datetime import datetime

import proDUCKtion # pyright: ignore 
proDUCKtion.validify()
from EnneadTab.REVIT import REVIT_FORMS, REVIT_APPLICATION
from EnneadTab import NOTIFICATION, ERROR_HANDLE, LOG

# Import NYU layer mapping
from nyu_layer_mapping import get_nyu_layer_info, NYU_LAYER_MAPPING

# Fallback layer from NYU ref table only (General - annotation text)
FALLBACK_LAYER = "G-ANNO-TEXT"
FALLBACK_COLOR = 7

def is_import_or_link_layer(category_name):
    """True if this key is from linked/imported CAD (e.g. layer name from .dwg/.sat)."""
    if not category_name or not isinstance(category_name, str):
        return False
    name_lower = category_name.lower()
    return (name_lower.endswith(".dwg") or name_lower.endswith(".dxf") or
            name_lower.endswith(".sat") or name_lower.endswith(".dgn"))

uidoc = REVIT_APPLICATION.get_uidoc()
doc = REVIT_APPLICATION.get_doc()

def get_category_layer_settings(category_name, doc, unmapped_list=None):
    """Get NYU layer settings for a given category name.
    If unmapped_list is provided, append category_name when falling back to default.
    Linked/imported CAD layers (.dwg, .dxf, .sat) go to G-ANNO-TEXT and are not reported as unmapped."""
    # Linked/imported CAD layers: use ref-table fallback, do not add to unmapped list
    if is_import_or_link_layer(category_name):
        return {"layer_name": FALLBACK_LAYER, "color_number": FALLBACK_COLOR}
    # Try to find by human name in our mapping
    nyu_info = get_nyu_layer_info(category_name)
    
    # If not found by human name, try to find by OST value
    if nyu_info == NYU_LAYER_MAPPING["DEFAULT"]:
        # Try to find the BuiltInCategory that matches this category name
        for human_name, mapping_info in NYU_LAYER_MAPPING.items():
            if mapping_info.get("OST"):
                # Get the category from the BuiltInCategory
                try:
                    category = DB.Category.GetCategory(doc, mapping_info["OST"])
                    if category and category.Name == category_name:
                        nyu_info = mapping_info
                        break
                except:
                    # If we can't get the category, skip this mapping
                    continue
    
    # Return layer settings
    if nyu_info == NYU_LAYER_MAPPING["DEFAULT"]:
        if unmapped_list is not None:
            unmapped_list.append(category_name)
        return {"layer_name": FALLBACK_LAYER, "color_number": FALLBACK_COLOR}
    else:
        return {
            "layer_name": nyu_info["dwg_layer"],
            "color_number": nyu_info["color"]
        }

def collect_parent_category_settings(existing_layer_table, doc):
    """Collect layer settings for all parent categories.
    Returns (parent_category_settings dict, unmapped_category_names list)."""
    parent_category_settings = {}
    unmapped_categories = []
    
    for export_layer_key in existing_layer_table.GetKeys():
        category_name = export_layer_key.CategoryName
        subcategory_name = export_layer_key.SubCategoryName
        
        # Only process parent categories (no subcategory name)
        if not subcategory_name:
            settings = get_category_layer_settings(category_name, doc, unmapped_list=unmapped_categories)
            parent_category_settings[category_name] = settings
    
    return parent_category_settings, unmapped_categories

def create_nyu_layer_table(existing_layer_table, parent_category_settings):
    """Create a new layer table with NYU standards applied"""
    new_export_layer_table = DB.ExportLayerTable()
    
    for export_layer_key in existing_layer_table.GetKeys():
        category_name = export_layer_key.CategoryName
        
        # Get parent category settings (subcategories inherit from parent)
        if category_name in parent_category_settings:
            settings = parent_category_settings[category_name]
        else:
            # Fallback if parent category not found (e.g. import/link layers)
            if is_import_or_link_layer(category_name):
                settings = {"layer_name": FALLBACK_LAYER, "color_number": FALLBACK_COLOR}
            else:
                settings = {"layer_name": FALLBACK_LAYER, "color_number": FALLBACK_COLOR}
        
        # Create new layer info
        new_layer_info = DB.ExportLayerInfo()
        
        # Apply parent category settings (subcategories use parent category settings)
        new_layer_info.LayerName = settings["layer_name"]
        new_layer_info.CutLayerName = settings["layer_name"]
        new_layer_info.ColorNumber = settings["color_number"]
        new_layer_info.CutColorNumber = settings["color_number"]
        
        # Add to new table
        new_export_layer_table.Add(export_layer_key, new_layer_info)
    
    return new_export_layer_table

def apply_nyu_layer_mapping_to_setting(sel_setting, doc):
    """Apply NYU CAD layer standards to a single DWG export setting"""
    old_name = sel_setting.Name
    
    # Create a backup by temporarily renaming
    t = DB.Transaction(doc, "Create NYU mapping backup")
    t.Start()
    sel_setting.Name += "_NYU_backup"
    new_setting = DB.ExportDWGSettings.Create(doc, old_name, sel_setting.GetDWGExportOptions())
    t.Commit()

    # Get existing export options and layer table
    existing_option = sel_setting.GetDWGExportOptions()
    existing_layer_table = existing_option.GetExportLayerTable()
    
    # Collect parent category settings and unmapped categories
    parent_category_settings, unmapped_categories = collect_parent_category_settings(existing_layer_table, doc)
    
    # Create new layer table with NYU standards
    new_export_layer_table = create_nyu_layer_table(existing_layer_table, parent_category_settings)
    
    # Apply the new layer table
    t = DB.Transaction(doc, "Apply NYU layer mapping")
    t.Start()
    existing_option.SetExportLayerTable(new_export_layer_table)
    sel_setting.SetDWGExportOptions(existing_option)
    t.Commit()
    
    # Clean up backup
    t = DB.Transaction(doc, "Clean up backup")
    t.Start()
    if new_setting and new_setting.Id and doc:
        doc.Delete(new_setting.Id)
    t.Commit()
    
    # Restore original name
    t = DB.Transaction(doc, "Restore original name")
    t.Start()
    sel_setting.Name = old_name
    t.Commit()
    
    return old_name, unmapped_categories

def get_dwg_export_settings(doc):
    """Get all existing DWG export settings from the document"""
    return DB.FilteredElementCollector(doc)\
                .OfClass(DB.ExportDWGSettings)\
                .WhereElementIsNotElementType()\
                .ToElements()

def select_dwg_settings(existing_dwg_settings):
    """Let user select DWG export settings"""
    return forms.SelectFromList.show(
        existing_dwg_settings,
        name_attr="Name",
        multiselect=True,
        button_name='Apply NYU Layer Standards',
        title="Select DWG Export Setting(s) to Apply NYU CAD Layer Standards"
    )

def process_nyu_mapping(sel_setting):
    """Legacy function for backward compatibility"""
    name, _ = apply_nyu_layer_mapping_to_setting(sel_setting, doc)
    return name

def get_log_path():
    """Log file path next to this script."""
    script_dir = os.path.dirname(os.path.abspath(__file__))
    return os.path.join(script_dir, "nyu_export_mapping.log")

def write_log(processed_settings, all_unmapped, error_msg=None):
    """Append one run to log file next to script."""
    log_path = get_log_path()
    ts = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    doc_title = doc.Title if doc else "?"
    lines = [
        "",
        "---",
        "[{}] doc: {}".format(ts, doc_title),
    ]
    if error_msg:
        lines.append("  ERROR: {}".format(error_msg))
    else:
        lines.append("  Settings applied: {}".format(", ".join(processed_settings)))
        if all_unmapped:
            lines.append("  Unmapped categories (used G-ANNO-TEXT):")
            for cat in sorted(all_unmapped):
                lines.append("    - {}".format(cat))
        else:
            lines.append("  Unmapped: none")
    lines.append("")
    text = "\n".join(lines)
    try:
        with open(log_path, "a") as f:
            f.write(text)
    except Exception as e:
        print("Could not write log to {}: {}".format(log_path, e))

@LOG.log(__file__, __title__)
@ERROR_HANDLE.try_catch_error()
def main():
    """Main function to handle NYU export mapping"""
    
    # Get existing DWG export settings
    existing_dwg_settings = get_dwg_export_settings(doc)
    
    if not existing_dwg_settings:
        REVIT_FORMS.notification(main_text="No DWG export settings found in the document.",
                                self_destruct=10)
        return
    
    # Let user select DWG export setting
    sel_settings = select_dwg_settings(existing_dwg_settings)
    
    if not sel_settings:
        REVIT_FORMS.notification(main_text="No export setting selected.\nNothing was changed.",
                                self_destruct=10)
        return
    
    # Process each selected setting
    processed_settings = []
    all_unmapped = set()
    TG = DB.TransactionGroup(doc, "Apply NYU Export Mapping")
    TG.Start()
    
    try:
        for setting in sel_settings:
            setting_name, unmapped = apply_nyu_layer_mapping_to_setting(setting, doc)
            processed_settings.append(setting_name)
            for cat in unmapped:
                all_unmapped.add(cat)
        TG.Assimilate()
        
        # Write log next to script
        write_log(processed_settings, all_unmapped)
        
        # Show success message
        if len(processed_settings) == 1:
            message = "NYU CAD layer standards applied to '{}'".format(processed_settings[0])
        else:
            message = "NYU CAD layer standards applied to {} settings:\n".format(len(processed_settings)) + \
                     "\n".join(["• {}".format(name) for name in processed_settings])
        
        NOTIFICATION.messenger(main_text=message)
        
        # Show categories not in mapping so user can update nyu_layer_mapping.py
        if all_unmapped:
            unmapped_sorted = sorted(all_unmapped)
            unmapped_text = "\n".join(unmapped_sorted)
            report = "Categories not in NYU mapping (used G-ANNO-TEXT).\nAdd these to nyu_layer_mapping.py raw_mapping_data to customize:\n\n" + unmapped_text
            print(report)
            print("Log written to: {}".format(get_log_path()))
        
    except Exception as e:
        TG.RollBack()
        print("Error applying NYU export mapping: {}".format(e))
        write_log(processed_settings, all_unmapped, error_msg=str(e))

if __name__ == "__main__":
    output = script.get_output()
    output.close_others()
    main()
    # Keep output open so user can read unmapped categories list (5 min)
    output.self_destruct(300)
