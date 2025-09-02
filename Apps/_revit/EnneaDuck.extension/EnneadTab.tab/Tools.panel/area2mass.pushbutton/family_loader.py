#!/usr/bin/python
# -*- coding: utf-8 -*-

"""Family loading classes for Area2Mass conversion."""

import os
from Autodesk.Revit import DB # pyright: ignore 
from pyrevit.revit import ErrorSwallower # pyright: ignore 

from EnneadTab import FOLDER
from EnneadTab.REVIT import REVIT_FAMILY


class FamilyLoader:
    """Handles loading families into the project."""
    
    def __init__(self, family_doc, family_name):
        self.family_doc = family_doc
        self.family_name = family_name
    
    def load_into_project(self, project_doc):
        """Load the family into the main project."""
        try:
            # Save family to temp location
            temp_folder = FOLDER.get_local_dump_folder_folder("area2mass_temp")
            family_path = os.path.join(temp_folder, "{}.rfa".format(self.family_name))
            
            # Create temp folder if it doesn't exist
            if not os.path.exists(temp_folder):
                os.makedirs(temp_folder)
            
            # Save family document
            options = DB.SaveAsOptions()
            options.OverwriteExistingFile = True
            self.family_doc.SaveAs(family_path, options)
            
            # Load family into project using EnneadTab pattern
            with ErrorSwallower() as swallower:
                REVIT_FAMILY.load_family(self.family_doc, project_doc)
                
                # Check for swallowed errors
                errors = swallower.get_swallowed_errors()
                if errors:
                    print("Warnings/errors swallowed during family loading: {}".format(errors))
            
            # Close family document
            self.family_doc.Close(False)
            
            # Clean up temp file
            try:
                os.remove(family_path)
            except:
                pass
            
            return True
            
        except Exception as e:
            print("Error loading family into project: {}".format(str(e)))
            try:
                self.family_doc.Close(False)
            except:
                pass
            return False
