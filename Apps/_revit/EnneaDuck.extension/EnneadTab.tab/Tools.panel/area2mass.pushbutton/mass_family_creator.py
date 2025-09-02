#!/usr/bin/python
# -*- coding: utf-8 -*-

"""Mass family creation classes for Area2Mass conversion."""

import os
from Autodesk.Revit import DB # pyright: ignore 
from Autodesk.Revit import ApplicationServices # pyright: ignore 

from EnneadTab import FOLDER, ERROR_HANDLE
from EnneadTab.REVIT import REVIT_APPLICATION, REVIT_UNIT


class MassFamilyCreator:
    """Creates mass families from boundary data."""
    
    def __init__(self, template_path, family_name):
        self.template_path = template_path
        self.family_name = family_name
        self.family_doc = None
        self.debug_info = []
        
    def add_debug_info(self, message):
        """Add debug information."""
        self.debug_info.append(message)
        ERROR_HANDLE.print_note("DEBUG: {}".format(message))
    
    def create_from_boundaries(self, boundary_segments):
        """Create mass family from boundary segments."""
        print("Starting mass family creation for: {}".format(self.family_name))
        ERROR_HANDLE.print_note("Starting mass family creation for: {}".format(self.family_name))
        
        # Validate boundary segments
        if not boundary_segments:
            print("No boundary segments provided")
            ERROR_HANDLE.print_note("No boundary segments provided")
            return None
        
        print("Boundary segments structure: {} lists".format(len(boundary_segments)))
        ERROR_HANDLE.print_note("Boundary segments structure: {} lists".format(len(boundary_segments)))
        for i, segment_list in enumerate(boundary_segments):
            if segment_list:
                print("  List {}: {} segments".format(i, len(segment_list)))
                ERROR_HANDLE.print_note("  List {}: {} segments".format(i, len(segment_list)))
            else:
                print("  List {}: None or empty".format(i))
                ERROR_HANDLE.print_note("  List {}: None or empty".format(i))
        
        # Create family document from template
        print("Creating family document from template...")
        ERROR_HANDLE.print_note("Creating family document from template...")
        self.family_doc = self._create_family_doc_from_template()
        if not self.family_doc:
            print("Failed to create family document from template")
            ERROR_HANDLE.print_note("Failed to create family document from template")
            return None
        
        print("Successfully created family document: {}".format(self.family_doc.Title))
        ERROR_HANDLE.print_note("Successfully created family document: {}".format(self.family_doc.Title))
        
        # Create mass geometry
        print("Creating mass geometry...")
        ERROR_HANDLE.print_note("Creating mass geometry...")
        geometry_result = self._create_mass_geometry(boundary_segments)
        if not geometry_result:
            print("Failed to create mass geometry - _create_mass_geometry returned False")
            ERROR_HANDLE.print_note("Failed to create mass geometry - _create_mass_geometry returned False")
            return None
        
        print("Successfully created mass geometry")
        ERROR_HANDLE.print_note("Successfully created mass geometry")
        
        # Set family name
        print("Setting family name...")
        ERROR_HANDLE.print_note("Setting family name...")
        self.family_doc.Title = self.family_name
        
        print("Successfully created mass family: {}".format(self.family_name))
        ERROR_HANDLE.print_note("Successfully created mass family: {}".format(self.family_name))
        return self.family_doc
    
    def _create_family_doc_from_template(self):
        """Create a family document from template path."""
        print("Creating family document from template: {}".format(self.template_path))
        ERROR_HANDLE.print_note("Creating family document from template: {}".format(self.template_path))
        
        # Always use .rfa files for mass families to ensure proper template type
        if self.template_path.lower().endswith('.rfa'):
            print("Template is .rfa file, opening directly...")
            # For .rfa files, open directly
            app = REVIT_APPLICATION.get_app()
            print("Got Revit application, opening template file...")
            family_doc = app.OpenDocumentFile(self.template_path)
            if family_doc:
                print("Successfully opened family document from .rfa template")
                ERROR_HANDLE.print_note("Created family document from .rfa template")
                return family_doc
            else:
                print("Failed to open family document from .rfa template")
        else:
            print("Template is not .rfa file, trying to find .rfa version...")
            # If we have .rft, try to find the corresponding .rfa
            rfa_path = self.template_path.replace('.rft', '.rfa')
            if os.path.exists(rfa_path):
                print("Found .rfa version: {}".format(rfa_path))
                app = REVIT_APPLICATION.get_app()
                family_doc = app.OpenDocumentFile(rfa_path)
                if family_doc:
                    print("Successfully opened family document from .rfa template (converted from .rft)")
                    ERROR_HANDLE.print_note("Created family document from .rfa template (converted from .rft)")
                    return family_doc
                else:
                    print("Failed to open family document from .rfa template (converted from .rft)")
            else:
                print("No .rfa version found")
        
        print("Failed to create family document from template")
        ERROR_HANDLE.print_note("Failed to create family document from template")
        return None
    
    def _create_mass_geometry(self, boundary_segments):
        """Create mass geometry from boundary segments."""
        print("Creating mass geometry from boundary segments...")
        if not self.family_doc:
            print("No family document available for geometry creation")
            ERROR_HANDLE.print_note("No family document available for geometry creation")
            return False
            
        print("Creating mass geometry from {} boundary segment lists".format(len(boundary_segments)))
        ERROR_HANDLE.print_note("Creating mass geometry from {} boundary segment lists".format(len(boundary_segments)))
        
        # Start transaction for family creation
        print("Starting transaction...")
        t = DB.Transaction(self.family_doc, "Create Mass Geometry")
        t.Start()
        print("Transaction started successfully")
        
        # Create extrusion directly from the boundary segments structure
        # GetBoundarySegments returns IList<IList<BoundarySegment>> which is perfect for NewExtrusion
        print("Calling _create_extrusion_from_boundary_segments...")
        ERROR_HANDLE.print_note("Calling _create_extrusion_from_boundary_segments...")
        extrusion_result = self._create_extrusion_from_boundary_segments(boundary_segments)
        if not extrusion_result:
            print("Failed to create extrusion from boundary segments - _create_extrusion_from_boundary_segments returned False")
            ERROR_HANDLE.print_note("Failed to create extrusion from boundary segments - _create_extrusion_from_boundary_segments returned False")
            t.RollBack()
            print("Transaction rolled back due to extrusion failure")
            return False
        
        print("Successfully created extrusion from boundary segments")
        ERROR_HANDLE.print_note("Successfully created extrusion from boundary segments")
        
        t.Commit()
        print("Transaction committed successfully")
        ERROR_HANDLE.print_note("Successfully created mass geometry")
        return True
    
    def _create_extrusion_from_boundary_segments(self, boundary_segments):
        """Create extrusion from boundary segments using NewExtrusionForm for mass families.
        
        GetBoundarySegments returns IList<IList<BoundarySegment>> which needs to be converted
        to ReferenceArray for NewExtrusionForm method.
        """
        print("Creating extrusion from {} boundary segment lists using NewExtrusionForm".format(len(boundary_segments)))
        ERROR_HANDLE.print_note("Creating extrusion from {} boundary segment lists using NewExtrusionForm".format(len(boundary_segments)))
        
        # Validate boundary segments
        if not boundary_segments or len(boundary_segments) == 0:
            print("No boundary segments provided")
            ERROR_HANDLE.print_note("No boundary segments provided")
            return False
        
        # Convert IList<IList<BoundarySegment>> to ReferenceArray
        # NewExtrusionForm expects ReferenceArray profile with one curve loop
        reference_array = DB.ReferenceArray()
        
        for i, segment_list in enumerate(boundary_segments):
            if not segment_list:
                ERROR_HANDLE.print_note("  List {}: None or empty".format(i))
                continue
                
            ERROR_HANDLE.print_note("  List {}: {} segments".format(i, len(segment_list)))
            
            # Create curves from this segment list
            curve_list = []
            for j, segment in enumerate(segment_list):
                curve = segment.GetCurve()
                if curve:
                    curve_list.append(curve)
                    ERROR_HANDLE.print_note("    Added curve {} from segment list {}".format(j, i))
                else:
                    ERROR_HANDLE.print_note("    Segment {} in list {} has no curve".format(j, i))
            
            if len(curve_list) > 0:
                ERROR_HANDLE.print_note("  List {}: {} valid curves".format(i, len(curve_list)))
                
                # Create a curve loop from the curves and add to reference array
                try:
                    curve_loop = DB.CurveLoop.Create(curve_list)
                    if curve_loop:
                        # Create a reference from the curve loop
                        reference = curve_loop.Reference
                        if reference:
                            reference_array.Append(reference)
                            ERROR_HANDLE.print_note("  Added curve loop {} to reference array".format(i))
                        else:
                            ERROR_HANDLE.print_note("  Failed to get reference from curve loop {}".format(i))
                    else:
                        ERROR_HANDLE.print_note("  Failed to create curve loop from list {}".format(i))
                except Exception as e:
                    ERROR_HANDLE.print_note("  Error creating curve loop from list {}: {}".format(i, str(e)))
            else:
                ERROR_HANDLE.print_note("  List {}: no valid curves".format(i))
        
        if reference_array.Size == 0:
            print("No valid references created")
            ERROR_HANDLE.print_note("No valid references created")
            return False
        
        # Get default height for extrusion direction
        height = self._get_default_extrusion_height()
        direction = DB.XYZ(0, 0, height)  # Extrude in Z direction
        print("Extrusion parameters - Height: {}, Direction: {}".format(height, direction))
        
        # Create extrusion using NewExtrusionForm
        if not self.family_doc:
            print("No family document available for extrusion")
            ERROR_HANDLE.print_note("No family document available for extrusion")
            return False
            
        print("Attempting to create extrusion with NewExtrusionForm:")
        print("  - ReferenceArray size: {}".format(reference_array.Size))
        print("  - Direction: {}".format(direction))
        print("  - Height: {}".format(height))
        ERROR_HANDLE.print_note("Attempting to create extrusion with NewExtrusionForm:")
        ERROR_HANDLE.print_note("  - ReferenceArray size: {}".format(reference_array.Size))
        ERROR_HANDLE.print_note("  - Direction: {}".format(direction))
        ERROR_HANDLE.print_note("  - Height: {}".format(height))
        
        factory = self.family_doc.FamilyCreate
        print("Got FamilyCreate factory")
        
        try:
            # Use NewExtrusionForm which is designed for mass families
            print("Calling factory.NewExtrusionForm...")
            form = factory.NewExtrusionForm(True, reference_array, direction)
            
            if form:
                print("Successfully created mass extrusion form with {} references".format(reference_array.Size))
                ERROR_HANDLE.print_note("Successfully created mass extrusion form with {} references".format(reference_array.Size))
                return True
            else:
                print("Failed to create mass extrusion form - NewExtrusionForm returned None")
                ERROR_HANDLE.print_note("Failed to create mass extrusion form - NewExtrusionForm returned None")
                return False
                
        except Exception as e:
            print("Exception during NewExtrusionForm: {}".format(str(e)))
            ERROR_HANDLE.print_note("Exception during NewExtrusionForm: {}".format(str(e)))
            return False
    
    def _get_default_extrusion_height(self):
        """Get default height for mass extrusion."""
        # Default height of 10 feet in project units (assuming feet)
        return 10.0
    
    def get_debug_summary(self):
        """Get summary of debug information."""
        return "\n".join(self.debug_info)
