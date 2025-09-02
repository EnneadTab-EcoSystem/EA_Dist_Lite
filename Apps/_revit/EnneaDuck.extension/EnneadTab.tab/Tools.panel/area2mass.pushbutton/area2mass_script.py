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
from EnneadTab.REVIT import REVIT_APPLICATION, REVIT_FAMILY, REVIT_UNIT, REVIT_SELECTION, REVIT_FORMS
from EnneadTab import ENVIRONMENT
from Autodesk.Revit import DB # pyright: ignore 
from Autodesk.Revit import ApplicationServices # pyright: ignore 

# Import modular classes
try:
    from data_extractors import ElementInfoExtractor, BoundaryDataExtractor
    from template_finder import TemplateFinder
    from mass_family_creator import MassFamilyCreator
    from family_loader import FamilyLoader
    from instance_placer import FamilyInstancePlacer
except ImportError as e:
    print("Error importing modules: {}".format(str(e)))
    print("Please ensure all required modules are available in the same directory.")
    # Show error message if modules can't be imported
    print("Failed to import required modules. Check console for details.")

UIDOC = REVIT_APPLICATION.get_uidoc()
DOC = REVIT_APPLICATION.get_doc()


# =============================================================================
# MAIN CONVERTER CLASS
# =============================================================================

class Area2MassConverter:
    """Main class for converting areas/rooms to mass families."""
    
    def __init__(self):
        """Initialize the Area2Mass converter."""
        self.doc = DOC
        self.uidoc = UIDOC
        self.areas = []
        self.rooms = []
        self.success_count = 0
        self.total_count = 0
        self.template_path = None
        self.created_families = []
        
    def run(self):
        """Main execution method with step-by-step process."""
        try:
            # Step 1: Validate environment
            if not self._step_01_validate_environment():
                return False
                
            # Step 2: Get and filter selection
            if not self._step_02_get_and_filter_selection():
                return False
                
            # Step 3: Get template
            if not self._step_03_get_template():
                return False
                
            # Step 4: Process spatial elements
            if not self._step_04_process_spatial_elements():
                return False
                
            # Step 5: Show results
            self._step_05_show_results()
            return True
            
        except Exception as e:
            NOTIFICATION.messenger("Error in Area2Mass conversion: {}".format(str(e)))
            print("Error in Area2Mass conversion: {}".format(str(e)))
            return False
    
    @ERROR_HANDLE.try_catch_error()
    def _step_01_validate_environment(self):
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
    
    @ERROR_HANDLE.try_catch_error()
    def _step_02_get_and_filter_selection(self):
        """Step 2: Get selected elements and filter for areas/rooms."""
        NOTIFICATION.messenger("Step 2: Getting and filtering selection...")
        
        # Use REVIT_FORMS.dialogue to get user input
        # Ask user what type of spatial elements they want to process
        options = ["Areas", "Rooms"]
        user_choice = REVIT_FORMS.dialogue(
            title="Area2Mass - Select Element Type",
            main_text="What type of spatial elements would you like to convert to mass families?",
            options=options
        )
        
        if not user_choice or user_choice == "Close" or user_choice == "Cancel":
            print("User cancelled element type selection")
            NOTIFICATION.messenger("Operation cancelled by user.")
            return False
        
        print("User selected: {}".format(user_choice))
        
        # Process based on user choice
        if user_choice == "Areas":
            if not self._process_areas():
                return False
        elif user_choice == "Rooms":
            if not self._process_rooms():
                return False
        
        # Check if we have any elements to process
        if not self.areas and not self.rooms:
            NOTIFICATION.messenger("No areas or rooms found to process.")
            return False
        
        self.total_count = len(self.areas) + len(self.rooms)
        print("Found {} areas and {} rooms to convert".format(
            len(self.areas), len(self.rooms)))
        NOTIFICATION.messenger("Found {} areas and {} rooms to convert.".format(len(self.areas), len(self.rooms)))
        return True
    
    @ERROR_HANDLE.try_catch_error()
    def _process_areas(self):
        """Process areas with area scheme selection."""
        print("Processing areas...")
        
        # Get all area schemes in the project
        area_schemes = DB.FilteredElementCollector(self.doc).OfClass(DB.AreaScheme).ToElements()
        
        if not area_schemes:
            print("No area schemes found in project")
            NOTIFICATION.messenger("No area schemes found in project.")
            return False
        
        # Let user select which area scheme to process
        scheme_options = []
        for scheme in area_schemes:
            scheme_name = scheme.Name if scheme.Name else "Unnamed Scheme"
            scheme_options.append(scheme_name)
        
        selected_scheme_name = REVIT_FORMS.dialogue(
            title="Area2Mass - Select Area Scheme",
            main_text="Select the area scheme to process:",
            options=scheme_options
        )
        
        if not selected_scheme_name or selected_scheme_name == "Close" or selected_scheme_name == "Cancel":
            print("User cancelled area scheme selection")
            return False
        
        # Find the selected scheme by matching the name
        selected_scheme = None
        for scheme in area_schemes:
            scheme_name = scheme.Name if scheme.Name else "Unnamed Scheme"
            if scheme_name == selected_scheme_name:
                selected_scheme = scheme
                break
        
        if not selected_scheme:
            print("Could not find selected area scheme")
            return False
        
        print("Selected area scheme: {}".format(selected_scheme.Name))
        
        # Get all areas from the selected scheme using SpatialElement
        spatial_elements = DB.FilteredElementCollector(self.doc).OfClass(DB.SpatialElement).ToElements()
        scheme_areas = []
        
        for element in spatial_elements:
            # Check if it's an Area and belongs to the selected scheme
            if hasattr(element, 'AreaScheme') and element.AreaScheme.Id == selected_scheme.Id:
                scheme_areas.append(element)
        
        if not scheme_areas:
            print("No areas found in selected scheme")
            NOTIFICATION.messenger("No areas found in the selected area scheme.")
            return False
        
        # Process all areas automatically
        self.areas = scheme_areas
        print("Processing all {} areas".format(len(scheme_areas)))
        
        return True
    
    @ERROR_HANDLE.try_catch_error()
    def _process_rooms(self):
        """Process all rooms in the project."""
        print("Processing rooms...")
        
        # Get all rooms in the project using SpatialElement
        spatial_elements = DB.FilteredElementCollector(self.doc).OfClass(DB.SpatialElement).ToElements()
        rooms = []
        
        for element in spatial_elements:
            # Check if it's a Room
            if hasattr(element, 'Number'):  # Rooms have Number parameter
                rooms.append(element)
        
        if not rooms:
            print("No rooms found in project")
            NOTIFICATION.messenger("No rooms found in project.")
            return False
        
        # Process all rooms automatically
        self.rooms = rooms
        print("Processing all {} rooms".format(len(rooms)))
        
        return True
    
    @ERROR_HANDLE.try_catch_error()
    def _step_03_get_template(self):
        """Step 3: Get mass family template."""
        NOTIFICATION.messenger("Step 3: Getting mass family template...")
        
        template_finder = TemplateFinder()
        self.template_path = template_finder.get_mass_family_template()
        
        if not self.template_path:
            NOTIFICATION.messenger("Failed to get mass family template.")
            return False
        
        print("Template path: {}".format(self.template_path))
        NOTIFICATION.messenger("Template found: {}".format(os.path.basename(self.template_path)))
        return True
    
    @ERROR_HANDLE.try_catch_error()
    def _step_04_process_spatial_elements(self):
        """Step 4: Process each spatial element to create mass families."""
        NOTIFICATION.messenger("Step 4: Processing spatial elements...")
        
        # Process areas
        for area in self.areas:
            if not self._process_single_element(area, "Area"):
                print("Failed to process area: {}".format(area.Id))
                continue
        
        # Process rooms
        for room in self.rooms:
            if not self._process_single_element(room, "Room"):
                print("Failed to process room: {}".format(room.Id))
                continue
        
        if not self.created_families:
            NOTIFICATION.messenger("No mass families were created successfully.")
            return False
        
        print("Successfully created {} mass families".format(len(self.created_families)))
        NOTIFICATION.messenger("Successfully created {} mass families.".format(len(self.created_families)))
        return True
    
    @ERROR_HANDLE.try_catch_error()
    def _process_single_element(self, element, element_type):
        """Process a single spatial element to create a mass family."""
        print("Processing {}: {}".format(element_type, element.Id))
        
        # Extract boundary data
        print("Extracting boundary data for {}: {}".format(element_type, element.Id))
        extractor = BoundaryDataExtractor(element)
        if not extractor.is_valid():
            print("Failed to extract boundary data for {}: {}".format(element_type, element.Id))
            return False
        
        # Debug: Show what we got
        if extractor.segments:
            print("  Got {} boundary segment lists".format(len(extractor.segments)))
            for i, segment_list in enumerate(extractor.segments):
                if segment_list:
                    print("    List {}: {} segments".format(i, len(segment_list)))
                else:
                    print("    List {}: None or empty".format(i))
        else:
            print("  No boundary segments extracted")
        
        # Get element info for naming
        info_extractor = ElementInfoExtractor(element, element_type)
        element_info = info_extractor._extract_info()
        
        if not element_info or not element_info.get('name'):
            print("Failed to extract element info for {}: {}".format(element_type, element.Id))
            return False
        
        # Create mass family
        segments_count = len(extractor.segments) if extractor.segments else 0
        print("Creating mass family for {}: {} with {} boundary segment lists".format(
            element_type, element.Id, segments_count))
        
        mass_creator = MassFamilyCreator(self.template_path, element_info['name'])
        family_doc = mass_creator.create_from_boundaries(extractor.segments)
        
        if not family_doc:
            print("Failed to create mass family for {}: {}".format(element_type, element.Id))
            print("Debug info: template_path={}, element_name={}, segments_count={}".format(
                self.template_path, element_info['name'], segments_count))
            return False
        
        # Load family into project
        family_loader = FamilyLoader(family_doc, element_info['name'])
        if not family_loader.load_into_project(self.doc):
            print("Failed to load family for {}: {}".format(element_type, element.Id))
            return False
        
        # Place instance
        placer = FamilyInstancePlacer(self.doc, element_info['name'], element)
        if not placer.place_instance():
            print("Failed to place instance for {}: {}".format(element_type, element.Id))
            return False
        
        # Store created family info
        self.created_families.append({
            'element_id': element.Id,
            'element_type': element_type,
            'family_name': element_info['name'],
            'success': True
        })
        
        print("Successfully processed {}: {}".format(element_type, element.Id))
        return True
    
    @ERROR_HANDLE.try_catch_error()
    def _step_05_show_results(self):
        """Step 5: Show final results and cleanup."""
        NOTIFICATION.messenger("Step 5: Finalizing results...")
        
        # Show summary
        success_count = len(self.created_families)
        total_count = self.total_count
        
        if success_count == total_count:
            message = "All {} spatial elements successfully converted to mass families!".format(success_count)
        else:
            message = "Converted {}/{} spatial elements to mass families.".format(success_count, total_count)
        
        NOTIFICATION.messenger(message)
        print(message)
        
        # Show detailed results
        print("\nDetailed Results:")
        for family_info in self.created_families:
            print("  {} {} -> Mass Family Instance {}".format(
                family_info['element_type'],
                family_info['element_id'],
                family_info['instance_id']
            ))
        
        return True


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
