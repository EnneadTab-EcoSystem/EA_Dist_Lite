#!/usr/bin/python
# -*- coding: utf-8 -*-
"""
Extract model_guid and project_guid from currently open Revit cloud model for AutoExporter config.
"""

__doc__ = "Extract model_guid and project_guid from currently open Revit cloud model for AutoExporter config."
__title__ = "Get Model\nGUIDs"
__author__ = "EnneadTab"

from pyrevit import script
from Autodesk.Revit import DB # pyright: ignore

output = script.get_output()

try:
    doc = __revit__.ActiveUIDocument.Document # pyright: ignore
    
    output.print_md("# MODEL GUID EXTRACTOR")
    output.print_md("---")
    output.print_md("**Model Title:** `{}`".format(doc.Title))
    
    # Get the model path
    model_path = doc.GetWorksharingCentralModelPath()
    
    if model_path.ServerPath:
        # This is a cloud model
        output.print_md("\n## Cloud Model Detected")
        
        try:
            # Get the cloud path info
            cloud_path_str = DB.ModelPathUtils.ConvertModelPathToUserVisiblePath(model_path)
            output.print_md("**Cloud Path:** `{}`".format(cloud_path_str))
            
            # Get the model GUID (from ModelPath.GetModelGUID())
            model_guid = str(model_path.GetModelGUID())
            
            # Get the project GUID (from ModelPath.GetProjectGUID())
            project_guid = str(model_path.GetProjectGUID())
            
            # Get region (try to extract from path)
            region = "US"  # Default
            if "emea" in cloud_path_str.lower():
                region = "EMEA"
            elif "apac" in cloud_path_str.lower():
                region = "APAC"
            
            # Get Revit version
            app = doc.Application
            revit_version = app.VersionNumber
            
            output.print_md("\n---")
            output.print_md("## Copy These Values Into Your Config File:")
            output.print_md("---")
            
            # Print in JSON format for easy copying
            output.print_code('''{{
  "model_guid": "{}",
  "project_guid": "{}",
  "region": "{}",
  "revit_version": "{}"
}}'''.format(model_guid, project_guid, region, revit_version))
            
            output.print_md("\n---")
            output.print_md("### Individual Values:")
            output.print_md("- **model_guid:** `{}`".format(model_guid))
            output.print_md("- **project_guid:** `{}`".format(project_guid))
            output.print_md("- **region:** `{}`".format(region))
            output.print_md("- **revit_version:** `{}`".format(revit_version))
            
            output.print_md("\n---")
            output.print_md("✅ **Success!** Copy the JSON above into your AutoExporter config file.")
            output.print_md("\nConfig files are located at:")
            output.print_md("`Apps/_revit/EnneaDuck.extension/EnneadTab.tab/ACE.panel/AutoExporter.pushbutton/configs/`")
            
        except Exception as e:
            output.print_md("## ❌ ERROR")
            output.print_md("Failed to extract GUIDs: `{}`".format(e))
            output.print_md("\nThis model may not be a cloud model or may not be workshared.")
            import traceback
            output.print_code(traceback.format_exc())
    else:
        output.print_md("\n## ⚠️ Not a Cloud Model")
        output.print_md("This is a **local or server model**, not a cloud model.")
        output.print_md("\n**This script only works with ACC/BIM360 cloud models.**")
        output.print_md("\nIf this should be a cloud model, make sure it's opened from ACC/BIM360, not from a local sync location.")
        
except Exception as e:
    output.print_md("## ❌ ERROR")
    output.print_md("```\n{}\n```".format(e))
    import traceback
    output.print_code(traceback.format_exc())

if __name__ == "__main__":
    pass

