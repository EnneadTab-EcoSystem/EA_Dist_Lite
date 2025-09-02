#!/usr/bin/python
# -*- coding: utf-8 -*-

"""Family loading classes for Area2Mass conversion."""

import os
from Autodesk.Revit import DB # pyright: ignore 
from pyrevit.revit import ErrorSwallower # pyright: ignore 

from EnneadTab import FOLDER, ERROR_HANDLE
from EnneadTab.REVIT import REVIT_FAMILY


class FamilyLoader:
    """Loads and manages Revit families."""
    
    def __init__(self, family_doc, family_name):
        self.family_doc = family_doc
        self.family_name = family_name
        self.loaded_family = None
        self.debug_info = []
        
    def add_debug_info(self, message):
        """Add debug information."""
        self.debug_info.append(message)
        ERROR_HANDLE.print_note("DEBUG: {}".format(message))
    
    def load_into_project(self, project_doc):
        """Load family into the project document."""
        ERROR_HANDLE.print_note("Loading family '{}' into project".format(self.family_name))
        
        # Validate inputs
        if not self._validate_inputs(project_doc):
            return False
        
        # Save family to temporary location
        temp_path = self._save_family_to_temp()
        if not temp_path:
            return False
        
        # Load family into project
        if not self._load_family_into_project(project_doc, temp_path):
            return False
        
        # Verify family was loaded
        if not self._verify_family_loaded(project_doc):
            return False
        
        ERROR_HANDLE.print_note("Successfully loaded family '{}' into project".format(self.family_name))
        return True
    
    def _validate_inputs(self, project_doc):
        """Validate input parameters."""
        if not self.family_doc:
            ERROR_HANDLE.print_note("No family document provided")
            return False
        
        if not project_doc:
            ERROR_HANDLE.print_note("No project document provided")
            return False
        
        if not self.family_name:
            ERROR_HANDLE.print_note("No family name provided")
            return False
        
        ERROR_HANDLE.print_note("Input validation passed")
        return True
    
    def _save_family_to_temp(self):
        """Save family to temporary location."""
        ERROR_HANDLE.print_note("Saving family to temporary location")
        
        # Create temporary file path
        temp_filename = "{}.rfa".format(self.family_name)
        temp_path = FOLDER.get_local_dump_folder_file(temp_filename)
        
        # Save family document
        options = DB.SaveAsOptions()
        options.OverwriteExistingFile = True
        
        self.family_doc.SaveAs(temp_path, options)
        
        if os.path.exists(temp_path):
            ERROR_HANDLE.print_note("Family saved to: {}".format(temp_path))
            return temp_path
        else:
            ERROR_HANDLE.print_note("Failed to save family to temporary location")
            return None
    
    def _load_family_into_project(self, project_doc, temp_path):
        """Load family from temporary path into project."""
        ERROR_HANDLE.print_note("Loading family from temp path: {}".format(temp_path))
        
        # Use ENNEADTAB.REVIT_FAMILY.load_family method
        loaded_family = REVIT_FAMILY.load_family(self.family_doc, project_doc)
        
        if loaded_family:
            self.loaded_family = loaded_family
            ERROR_HANDLE.print_note("Family loaded successfully")
            return True
        else:
            ERROR_HANDLE.print_note("Failed to load family into project")
            return False
    
    def _verify_family_loaded(self, project_doc):
        """Verify that family was loaded into project."""
        ERROR_HANDLE.print_note("Verifying family was loaded")
        
        # Check if family exists in project
        collector = DB.FilteredElementCollector(project_doc).OfClass(DB.Family)
        
        for family in collector:
            if family.Name == self.family_name:
                ERROR_HANDLE.print_note("Family verified in project: {}".format(family.Name))
                return True
        
        ERROR_HANDLE.print_note("Family not found in project after loading")
        return False
    
    def get_loaded_family(self):
        """Get the loaded family object."""
        return self.loaded_family
    
    def get_debug_summary(self):
        """Get summary of debug information."""
        return "\n".join(self.debug_info)
