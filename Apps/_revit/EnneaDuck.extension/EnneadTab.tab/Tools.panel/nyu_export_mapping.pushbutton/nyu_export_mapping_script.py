#!/usr/bin/python
# -*- coding: utf-8 -*-

__doc__ = """Apply NYU CAD Layer Standards to DWG Export Settings.
This tool maps Revit categories to NYU standard layer names and colors.
All subcategories will use the parent category's layer settings."""
__title__ = "NYU Export\nCAD Layer Mapping"

__tip__ = True

from pyrevit import forms, script
from Autodesk.Revit import DB # pyright: ignore

import proDUCKtion # pyright: ignore 
proDUCKtion.validify()
from EnneadTab.REVIT import REVIT_FORMS, REVIT_APPLICATION
from EnneadTab import NOTIFICATION, ERROR_HANDLE, LOG

# Import NYU layer mapping
from nyu_layer_mapping import get_nyu_layer_info, NYU_LAYER_MAPPING

uidoc = REVIT_APPLICATION.get_uidoc()
doc = REVIT_APPLICATION.get_doc()

def get_category_layer_settings(category_name, doc):
    """Get NYU layer settings for a given category name"""
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
        return {
            "layer_name": category_name.upper(),
            "color_number": 7  # Default color for unmapped categories
        }
    else:
        return {
            "layer_name": nyu_info["dwg_layer"],
            "color_number": nyu_info["color"]
        }

def collect_parent_category_settings(existing_layer_table, doc):
    """Collect layer settings for all parent categories"""
    parent_category_settings = {}
    
    for export_layer_key in existing_layer_table.GetKeys():
        category_name = export_layer_key.CategoryName
        subcategory_name = export_layer_key.SubCategoryName
        
        # Only process parent categories (no subcategory name)
        if not subcategory_name:
            settings = get_category_layer_settings(category_name, doc)
            parent_category_settings[category_name] = settings
    
    return parent_category_settings

def create_nyu_layer_table(existing_layer_table, parent_category_settings):
    """Create a new layer table with NYU standards applied"""
    new_export_layer_table = DB.ExportLayerTable()
    
    for export_layer_key in existing_layer_table.GetKeys():
        category_name = export_layer_key.CategoryName
        
        # Get parent category settings (subcategories inherit from parent)
        if category_name in parent_category_settings:
            settings = parent_category_settings[category_name]
        else:
            # Fallback if parent category not found
            settings = {
                "layer_name": category_name.upper(),
                "color_number": 7
            }
        
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
    
    # Collect parent category settings
    parent_category_settings = collect_parent_category_settings(existing_layer_table, doc)
    
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
    
    return old_name

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
    return apply_nyu_layer_mapping_to_setting(sel_setting, doc)

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
    TG = DB.TransactionGroup(doc, "Apply NYU Export Mapping")
    TG.Start()
    
    try:
        for setting in sel_settings:
            setting_name = apply_nyu_layer_mapping_to_setting(setting, doc)
            processed_settings.append(setting_name)
        TG.Assimilate()
        
        # Show success message
        if len(processed_settings) == 1:
            message = "NYU CAD layer standards applied to '{}'".format(processed_settings[0])
        else:
            message = "NYU CAD layer standards applied to {} settings:\n".format(len(processed_settings)) + \
                     "\n".join(["• {}".format(name) for name in processed_settings])
        
        NOTIFICATION.messenger(main_text=message)
        
    except Exception as e:
        TG.RollBack()
        print("Error applying NYU export mapping: {}".format(e))

if __name__ == "__main__":
    output = script.get_output()
    output.close_others()
    main()
