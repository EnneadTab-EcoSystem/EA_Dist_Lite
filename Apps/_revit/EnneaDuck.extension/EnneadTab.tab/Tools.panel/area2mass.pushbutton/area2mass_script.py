#!/usr/bin/python
# -*- coding: utf-8 -*-

__doc__ = "Convert area/room boundaries into loadable Revit mass families by using boundary segment curve loops to build mass extrusions in mass family, then load into project using internal coordinates like Block2Family."
__title__ = "Area2Mass"

import proDUCKtion # pyright: ignore 
proDUCKtion.validify()

import os
import math
import clr # pyright: ignore 
from pyrevit import forms # pyright: ignore 
from pyrevit.revit import ErrorSwallower # pyright: ignore 

from EnneadTab import ERROR_HANDLE, FOLDER, DATA_FILE, NOTIFICATION, LOG, ENVIRONMENT, UI, SAMPLE_FILE
from EnneadTab.REVIT import REVIT_APPLICATION, REVIT_FAMILY, REVIT_UNIT, REVIT_SELECTION
from EnneadTab import ENVIRONMENT
from Autodesk.Revit import DB # pyright: ignore 
from Autodesk.Revit import ApplicationServices # pyright: ignore 

# Import modular classes
from data_extractors import ElementInfoExtractor, BoundaryDataExtractor
from template_finder import TemplateFinder
from mass_family_creator import MassFamilyCreator
from family_loader import FamilyLoader
from instance_placer import FamilyInstancePlacer

UIDOC = REVIT_APPLICATION.get_uidoc()
DOC = REVIT_APPLICATION.get_doc()


# =============================================================================
# MAIN CONVERTER CLASS
# =============================================================================

class Area2MassConverter:
    """Main class for converting areas/rooms to mass families."""
    
    def __init__(self):
        self.doc = DOC
        self.uidoc = UIDOC
        self.areas = []
        self.rooms = []
        self.success_count = 0
        self.total_count = 0
        self.template_path = None
        
    def run(self):
        """Main execution method with step-by-step process."""
        try:
            # Step 1: Validate environment
            if not self.step_01_validate_environment():
                return False
                
            # Step 2: Get and filter selection
            if not self.step_02_get_and_filter_selection():
                return False
                
            # Step 3: Get template
            if not self.step_03_get_template():
                return False
                
            # Step 4: Process spatial elements
            if not self.step_04_process_spatial_elements():
                return False
                
            # Step 5: Show results
            self.step_05_show_results()
            return True
            
        except Exception as e:
            NOTIFICATION.messenger("Error in Area2Mass conversion: {}".format(str(e)))
            print("Error in Area2Mass conversion: {}".format(str(e)))
            return False
    
    def step_01_validate_environment(self):
        """Step 1: Validate that we're in the right environment."""
        NOTIFICATION.messenger("Step 1: Validating environment...")
        
        if not self.doc:
            NOTIFICATION.messenger("No active document found.")
            return False
            
        if self.doc.IsFamilyDocument:
            NOTIFICATION.messenger("This tool only works in project documents, not family documents.")
            return False
            
        NOTIFICATION.messenger("Environment validation passed.")
        return True
    
    def step_02_get_and_filter_selection(self):
        """Step 2: Get selected elements and filter for areas/rooms."""
        NOTIFICATION.messenger("Step 2: Getting and filtering selection...")
        
        selected_elements = REVIT_SELECTION.get_selected_elements()
        if not selected_elements:
            NOTIFICATION.messenger("No elements selected. Please select areas or rooms to convert.")
            return False
        
        # Filter for areas and rooms
        for element in selected_elements:
            if isinstance(element, DB.Area):
                self.areas.append(element)
            elif isinstance(element, DB.Room):
                self.rooms.append(element)
        
        if not self.areas and not self.rooms:
            NOTIFICATION.messenger("No areas or rooms found in selection. Please select areas or rooms to convert.")
            return False
        
        self.total_count = len(self.areas) + len(self.rooms)
        NOTIFICATION.messenger("Found {} areas and {} rooms to convert.".format(len(self.areas), len(self.rooms)))
        return True
    
    def step_03_get_template(self):
        """Step 3: Get the mass family template."""
        NOTIFICATION.messenger("Step 3: Getting mass family template...")
        
        template_finder = TemplateFinder()
        self.template_path = template_finder.get_mass_family_template()
        
        if not self.template_path:
            NOTIFICATION.messenger("Could not find mass family template")
            return False
            
        NOTIFICATION.messenger("Template found: {}".format(os.path.basename(self.template_path)))
        return True
    
    def step_04_process_spatial_elements(self):
        """Step 4: Process all spatial elements."""
        NOTIFICATION.messenger("Step 4: Processing spatial elements...")
        
        # Process areas
        for area in self.areas:
            if self.process_single_element(area, "Area"):
                self.success_count += 1
        
        # Process rooms
        for room in self.rooms:
            if self.process_single_element(room, "Room"):
                self.success_count += 1
                
        return True
    
    def process_single_element(self, spatial_element, element_type):
        """Process a single spatial element through all conversion steps."""
        try:
            # Step 4a: Get element info
            element_info = ElementInfoExtractor(spatial_element, element_type)
            if not element_info.is_valid():
                print("Warning: Invalid element info for {} {}".format(element_type, spatial_element.Id))
                return False
            
            # Step 4b: Get boundary data
            boundary_data = BoundaryDataExtractor(spatial_element)
            if not boundary_data.is_valid():
                print("Warning: No boundary data for {} {}".format(element_type, spatial_element.Id))
                return False
            
            # Step 4c: Create mass family
            family_creator = MassFamilyCreator(self.template_path, element_info.name)
            family_doc = family_creator.create_from_boundaries(boundary_data.segments)
            if not family_doc:
                print("Warning: Failed to create mass family for {} {}".format(element_type, element_info.name))
                return False
            
            # Step 4d: Load family into project
            family_loader = FamilyLoader(family_doc, element_info.name)
            if not family_loader.load_into_project(self.doc):
                print("Warning: Failed to load mass family: {}".format(element_info.name))
                return False
            
            # Step 4e: Place family instance
            instance_placer = FamilyInstancePlacer(self.doc, element_info.name, spatial_element)
            if not instance_placer.place_instance():
                print("Warning: Family loaded but failed to place instance: {}".format(element_info.name))
                return False
            
            print("Successfully created, loaded, and placed mass family: {}".format(element_info.name))
            return True
            
        except Exception as e:
            print("Error processing {} {}: {}".format(element_type, spatial_element.Id, str(e)))
            return False
    
    def step_05_show_results(self):
        """Step 5: Show final results."""
        NOTIFICATION.messenger("Step 5: Conversion complete!")
        
        completion_message = "Successfully converted {} out of {} spatial elements to mass families.".format(
            self.success_count, self.total_count)
        NOTIFICATION.messenger(completion_message)
        print(completion_message)


# =============================================================================
# MAIN EXECUTION
# =============================================================================

@LOG.log(__file__, __title__)
@ERROR_HANDLE.try_catch_error()
def area2mass():
    """Main function to convert areas/rooms to mass families."""
    converter = Area2MassConverter()
    return converter.run()


################## main code below #####################
if __name__ == "__main__":
    area2mass()
