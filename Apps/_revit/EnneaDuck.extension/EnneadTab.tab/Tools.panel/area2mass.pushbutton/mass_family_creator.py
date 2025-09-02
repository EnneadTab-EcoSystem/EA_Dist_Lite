#!/usr/bin/python
# -*- coding: utf-8 -*-

"""Mass family creation classes for Area2Mass conversion."""

import os
from Autodesk.Revit import DB # pyright: ignore 
from Autodesk.Revit import ApplicationServices # pyright: ignore 

from EnneadTab import FOLDER
from EnneadTab.REVIT import REVIT_APPLICATION, REVIT_UNIT


class MassFamilyCreator:
    """Creates mass families from boundary data."""
    
    def __init__(self, template_path, family_name):
        self.template_path = template_path
        self.family_name = family_name
        self.family_doc = None
    
    def create_from_boundaries(self, boundary_segments):
        """Create mass family from boundary segments."""
        try:
            # Create family document from template
            self.family_doc = self.create_family_doc_from_template()
            if not self.family_doc:
                return None
            
            # Create mass geometry
            if not self.create_mass_geometry(boundary_segments):
                return None
            
            # Set family name
            self.family_doc.Title = self.family_name
            
            return self.family_doc
            
        except Exception as e:
            print("Error creating mass family: {}".format(str(e)))
            return None
    
    def create_family_doc_from_template(self):
        """Create a family document from template path."""
        try:
            # Check if template is .rfa or .rft
            if self.template_path.lower().endswith('.rfa'):
                # For .rfa files, open the family and create a copy
                app = REVIT_APPLICATION.get_app()
                family_doc = app.OpenDocumentFile(self.template_path)
                if family_doc:
                    # Create a copy by saving to temp location and reopening
                    temp_path = FOLDER.get_local_dump_folder_file("temp_mass_family.rfa")
                    options = DB.SaveAsOptions()
                    options.OverwriteExistingFile = True
                    family_doc.SaveAs(temp_path, options)
                    family_doc.Close(False)
                    
                    # Open the copy
                    family_doc = app.OpenDocumentFile(temp_path)
                    return family_doc
            else:
                # For .rft files, use NewFamilyDocument
                family_doc = ApplicationServices.Application.NewFamilyDocument(REVIT_APPLICATION.get_app(), self.template_path)
                return family_doc
            
            return None
            
        except Exception as e:
            print("Error creating family document from template: {}".format(str(e)))
            return None
    
    def create_mass_geometry(self, boundary_segments):
        """Create mass geometry from boundary segments."""
        try:
            if not self.family_doc:
                print("No family document available for geometry creation")
                return False
                
            # Start transaction for family creation
            t = DB.Transaction(self.family_doc, "Create Mass from Boundaries")
            t.Start()
            
            try:
                # Process each boundary segment list
                for segment_list in boundary_segments:
                    if not segment_list:
                        continue
                    
                    # Create curve loop from segments
                    curve_loop = self.create_curve_loop_from_segments(segment_list)
                    if not curve_loop:
                        continue
                    
                    # Create mass extrusion from curve loop
                    self.create_mass_extrusion(curve_loop)
                
                t.Commit()
                return True
                
            except Exception as e:
                t.RollBack()
                print("Error creating mass geometry: {}".format(str(e)))
                return False
                
        except Exception as e:
            print("Error in mass geometry creation: {}".format(str(e)))
            return False
    
    def create_curve_loop_from_segments(self, segment_list):
        """Create a curve loop from boundary segments."""
        try:
            curve_loop = DB.CurveLoop()
            
            for segment in segment_list:
                curve = segment.GetCurve()
                if curve:
                    curve_loop.Append(curve)
            
            # Check if curve loop is valid
            if curve_loop.Size() > 0:
                return curve_loop
            else:
                return None
                
        except Exception as e:
            print("Error creating curve loop: {}".format(str(e)))
            return None
    
    def create_mass_extrusion(self, curve_loop):
        """Create a mass extrusion from curve loop."""
        try:
            if not self.family_doc:
                print("No family document available for mass extrusion")
                return None
                
            # Get the default level for hosting
            levels = DB.FilteredElementCollector(self.family_doc).OfClass(DB.Level).WhereElementIsNotElementType().ToElements()
            if not levels:
                print("No levels found in family document")
                return None
            
            level = levels[0]  # Use first level
            
            # Create reference array from curve loop
            ref_array = DB.ReferenceArray()
            model_curves = []
            
            for curve in curve_loop:
                try:
                    # Create model curve from geometry curve
                    sketch_plane = DB.SketchPlane.Create(self.family_doc, level.Id)
                    model_curve = self.family_doc.FamilyCreate.NewModelCurve(curve, sketch_plane)
                    model_curves.append(model_curve)
                    ref_array.Append(model_curve.GeometryCurve.Reference)
                except Exception as e:
                    print("Warning: Could not create model curve: {}".format(str(e)))
                    continue
            
            # Create form by cap (mass extrusion)
            if ref_array.Size > 0:
                try:
                    # Create a simple extrusion by creating a form
                    form = self.family_doc.FamilyCreate.NewFormByCap(True, ref_array)
                    
                    # Add height parameter for extrusion
                    self.add_height_parameter_and_extrude(form, level)
                    
                    return form
                except Exception as e:
                    print("Error creating form by cap: {}".format(str(e)))
                    # Try alternative method - create solid directly
                    return self.create_solid_from_curves(model_curves, level)
            
            return None
            
        except Exception as e:
            print("Error creating mass extrusion: {}".format(str(e)))
            return None
    
    def add_height_parameter_and_extrude(self, form, level):
        """Add height parameter and extrude the form."""
        try:
            if not self.family_doc:
                print("No family document available for height parameter")
                return
                
            # Add height parameter if it doesn't exist
            manager = self.family_doc.FamilyManager
            height_param = None
            
            # Check if height parameter already exists
            for param in manager.GetParameters():
                if param.Definition.Name == "Height":
                    height_param = param
                    break
            
            if not height_param:
                # Create height parameter
                height_param = manager.AddParameter("Height", DB.GroupTypeId.Data, 
                                                  REVIT_UNIT.lookup_unit_spec_id("length"), True)
                # Set default height (10 feet)
                height_param.Set(10.0)
            
            # Get the height value
            height_value = height_param.AsDouble()
            
            # Create extrusion direction
            direction = DB.XYZ(0, 0, height_value)
            
            # Extrude the form
            if hasattr(form, 'Extrude'):
                form.Extrude(direction)
            else:
                # Alternative: create new form by extrusion
                ref_array = DB.ReferenceArray()
                ref_array.Append(form.Reference)
                self.family_doc.FamilyCreate.NewFormByExtrusion(ref_array, direction)
                
        except Exception as e:
            print("Error adding height parameter and extruding: {}".format(str(e)))
    
    def create_solid_from_curves(self, model_curves, level):
        """Create a solid from model curves as fallback method."""
        try:
            if not self.family_doc:
                print("No family document available for solid creation")
                return None
                
            # Create a simple solid by lofting curves
            if len(model_curves) < 2:
                return None
            
            # Create reference array for loft
            ref_array = DB.ReferenceArray()
            for curve in model_curves:
                ref_array.Append(curve.GeometryCurve.Reference)
            
            # Create form by loft
            form = self.family_doc.FamilyCreate.NewFormByLoft(ref_array, True)
            return form
            
        except Exception as e:
            print("Error creating solid from curves: {}".format(str(e)))
            return None
