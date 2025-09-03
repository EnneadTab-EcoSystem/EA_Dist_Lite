#!/usr/bin/python
# -*- coding: utf-8 -*-

"""Family instance placement classes for Area2Mass conversion."""

from Autodesk.Revit import DB # pyright: ignore
from EnneadTab import ERROR_HANDLE
from EnneadTab.REVIT import REVIT_FAMILY 


class FamilyInstancePlacer:
    """Places family instances in the project."""
    
    def __init__(self, project_doc, family_name, spatial_element):
        self.project_doc = project_doc
        self.family_name = family_name
        self.spatial_element = spatial_element
        self.debug_info = []
        
    def add_debug_info(self, message):
        """Add debug information."""
        self.debug_info.append(message)
        ERROR_HANDLE.print_note("DEBUG: {}".format(message))
    
    def place_instance(self):
        """Place a family instance at the spatial element location."""
        
        # Start transaction for instance placement
        t = DB.Transaction(self.project_doc, "Place Area2Mass Instance")
        t.Start()
        
        try:
            # Step 1: Get spatial element location
            location = self._get_spatial_element_location()
            if not location:
                t.RollBack()
                return False
            
            # Step 2: Get boundary segments for orientation
            boundary_segments = self._get_boundary_segments()
            if not boundary_segments:
                t.RollBack()
                return False
            
            # Step 3: Get level for hosting
            level = self._get_spatial_element_level()
            if not level:
                t.RollBack()
                return False
            
            # Step 4: Find family symbol
            family_symbol = self._find_family_symbol()
            if not family_symbol:
                t.RollBack()
                return False
            
            # Step 5: Check if instance already exists
            existing_instance = self._check_for_existing_instance(family_symbol)
            if existing_instance:
                t.Commit()
                return True
            
            # Step 6: Place instance
            try:
                placement_result = self._place_instance_at_location(family_symbol, location, level)
                if not placement_result:
                    t.RollBack()
                    return False
            except Exception as e:
                t.RollBack()
                return False
            
            # Commit transaction
            t.Commit()
            return True
            
        except Exception as e:
            t.RollBack()
            return False
    
    def _check_for_existing_instance(self, family_symbol):
        """Check if an instance of this family type already exists in the project."""
        try:
            # Get all instances of this family type
            collector = DB.FilteredElementCollector(self.project_doc).OfClass(DB.FamilyInstance)
            instances = collector.ToElements()
            
            # Check if any instance uses the same family symbol
            for instance in instances:
                if instance.Symbol.Id == family_symbol.Id:
                    return instance
            
            return None
            
        except Exception as e:
            return None
    
    def _get_spatial_element_location(self):
        """Get placement point. Use the actual level location instead of Internal Origin."""
        # Get the level elevation and place at that location
        level = self._get_spatial_element_level()
        if level:
            elevation = level.Elevation
            return DB.XYZ(0, 0, elevation)
        else:
            return DB.XYZ(0, 0, 0)
    
    def _get_boundary_segments(self):
        """Get boundary segments for orientation."""
        options = DB.SpatialElementBoundaryOptions()
        segments = self.spatial_element.GetBoundarySegments(options)
        
        if segments and len(segments) > 0:
            return segments
        else:
            return None
    
    def _get_spatial_element_level(self):
        """Get the level where the spatial element is hosted."""
        
        # Try to get level from spatial element
        if hasattr(self.spatial_element, 'Level'):
            level = self.spatial_element.Level
            if level:
                return level
        
        # Try to get level from parameters
        level_param = self.spatial_element.LookupParameter("Level")
        if level_param and level_param.AsString():
            level_name = level_param.AsString()
            
            # Find level by name
            collector = DB.FilteredElementCollector(self.project_doc).OfClass(DB.Level)
            for level in collector:
                if level.Name == level_name:
                    return level
        
        # Fallback: use first level
        collector = DB.FilteredElementCollector(self.project_doc).OfClass(DB.Level)
        levels = collector.ToElements()
        if levels:
            fallback_level = levels[0]
            return fallback_level
        
        return None
    
    def _find_family_symbol(self):
        """Find the family symbol to place using REVIT_FAMILY module."""
        
        # Use REVIT_FAMILY.get_all_types_by_family_name to get symbols directly
        family_symbols = REVIT_FAMILY.get_all_types_by_family_name(self.family_name, self.project_doc)
        
        if family_symbols:
            # Get the first available symbol
            first_symbol = family_symbols[0]
            
            # Check if it has the expected attributes - use try/catch instead of hasattr
            try:
                first_symbol.LookupParameter("Type Name").AsString()
            except Exception as e:
                return None
                
            try:
                first_symbol.Id
            except Exception as e:
                return None
                
            # Check if symbol is active and activate if needed
            try:
                is_active = first_symbol.IsActive
                
                if not is_active:
                    first_symbol.Activate()
                    
            except Exception as e:
                return None
                
            return first_symbol
        
        return None
    
    def _place_instance_at_location(self, family_symbol, location, level):
        """Place the family instance at Internal Origin on the specified level, using proven move2origin approach."""
        
        # Ensure symbol is active
        if not family_symbol.IsActive:
            family_symbol.Activate()
        
        # Set working plane to the level before placing instance
        try:
            # Create a reference plane at the level for proper placement
            # This ensures the instance is oriented correctly relative to the level
            level_ref = level.GetReference()
            
            # Create a reference plane at the level elevation
            # This helps with proper instance orientation and placement
            ref_plane = self.project_doc.Create.NewReferencePlane(
                DB.XYZ(0, 0, level.Elevation),  # Origin point
                DB.XYZ(1, 0, level.Elevation),  # Direction vector
                DB.XYZ(0, 1, level.Elevation),  # Up vector
                self.project_doc.ActiveView)
            
        except Exception as e:
            pass
        
        try:
            # Use correct document creation context (like move2origin does)
            if self.project_doc.IsFamilyDocument:
                doc_create = self.project_doc.FamilyCreate
            else:
                doc_create = self.project_doc.Create
            
            # Create instance using the proven method
            instance = doc_create.NewFamilyInstance(
                location, family_symbol, level, DB.Structure.StructuralType.NonStructural)
            
        except Exception as e:
            return False
        
        if not instance:
            return False

        # Pin instance
        try:
            instance.Pinned = True
        except Exception as e:
            pass
        
        return True
    

    
    def get_debug_summary(self):
        """Get summary of debug information."""
        return "\n".join(self.debug_info)
    
    def create_dedicated_3d_view(self):
        """Create a dedicated 3D view for the mass instances."""
        view_name = "AREA2MASS - 3D VIEW"
        
        try:
            # Try to find existing view
            collector = DB.FilteredElementCollector(self.project_doc)
            views = collector.OfClass(DB.View3D).WhereElementIsNotElementType()
            
            for view in views:
                if view.Name == view_name:
                    return view
            
            # Create new 3D view if not found
            
            # Get default 3D view type
            view_family_types = DB.FilteredElementCollector(self.project_doc).OfClass(DB.ViewFamilyType)
            view_family_type = None
            
            for vft in view_family_types:
                if vft.ViewFamily == DB.ViewFamily.ThreeDimensional:
                    view_family_type = vft
                    break
            
            if not view_family_type:
                # Create isometric view
                view = DB.View3D.CreateIsometric(self.project_doc, DB.ElementId.InvalidElementId)
            else:
                view = DB.View3D.CreateIsometric(self.project_doc, view_family_type.Id)
            
            # Set view properties
            view.Name = view_name
            
            # Set view scale and other properties for better visualization
            try:
                view.Scale = 100  # 1:100 scale
            except:
                pass
            
            # Set view to show mass category prominently
            try:
                # Get mass category
                mass_category = self.project_doc.Settings.Categories.get_Item(DB.BuiltInCategory.OST_Mass)
                if mass_category:
                    # Set category visibility
                    view.SetCategoryHidden(mass_category.Id, False)
            except Exception as e:
                pass
            
            return view
            
        except Exception as e:
            return None
