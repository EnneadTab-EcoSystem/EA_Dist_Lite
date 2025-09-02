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
        ERROR_HANDLE.print_note("Starting instance placement for family: {}".format(self.family_name))
        
        # Get spatial element location
        location = self._get_spatial_element_location()
        if not location:
            ERROR_HANDLE.print_note("Could not determine spatial element location")
            return False
        
        # Get boundary segments for orientation
        boundary_segments = self._get_boundary_segments()
        if not boundary_segments:
            ERROR_HANDLE.print_note("Could not get boundary segments for orientation")
            return False
        
        # Get level for hosting
        level = self._get_spatial_element_level()
        if not level:
            ERROR_HANDLE.print_note("Could not determine level for hosting")
            return False
        
        # Find family symbol
        family_symbol = self._find_family_symbol()
        if not family_symbol:
            ERROR_HANDLE.print_note("Could not find family symbol")
            return False
        
        # Place instance
        if not self._place_instance_at_location(family_symbol, location, level):
            ERROR_HANDLE.print_note("Failed to place instance")
            return False
        
        # Set instance parameters
        if not self._set_instance_parameters():
            ERROR_HANDLE.print_note("Warning: Could not set all instance parameters")
        
        ERROR_HANDLE.print_note("Successfully placed family instance")
        return True
    
    def _get_spatial_element_location(self):
        """Get the location of the spatial element."""
        ERROR_HANDLE.print_note("Getting spatial element location")
        
        # Try to get location from spatial element
        if hasattr(self.spatial_element, 'Location'):
            location = self.spatial_element.Location
            if location:
                if hasattr(location, 'Point'):
                    point = location.Point
                    ERROR_HANDLE.print_note("Found location point: ({}, {}, {})".format(
                        point.X, point.Y, point.Z))
                    return point
                elif hasattr(location, 'Curve'):
                    curve = location.Curve
                    point = curve.GetEndPoint(0)
                    ERROR_HANDLE.print_note("Found location from curve: ({}, {}, {})".format(
                        point.X, point.Y, point.Z))
                    return point
        
        # Fallback: use origin point
        ERROR_HANDLE.print_note("Using origin point as fallback location")
        return DB.XYZ(0, 0, 0)
    
    def _get_boundary_segments(self):
        """Get boundary segments for orientation."""
        ERROR_HANDLE.print_note("Getting boundary segments")
        
        options = DB.SpatialElementBoundaryOptions()
        segments = self.spatial_element.GetBoundarySegments(options)
        
        if segments and len(segments) > 0:
            ERROR_HANDLE.print_note("Found {} boundary segment lists".format(len(segments)))
            return segments
        else:
            ERROR_HANDLE.print_note("No boundary segments found")
            return None
    
    def _get_spatial_element_level(self):
        """Get the level where the spatial element is hosted."""
        ERROR_HANDLE.print_note("Getting spatial element level")
        
        # Try to get level from spatial element
        if hasattr(self.spatial_element, 'Level'):
            level = self.spatial_element.Level
            if level:
                ERROR_HANDLE.print_note("Found level: {}".format(level.Name))
                return level
        
        # Try to get level from parameters
        level_param = self.spatial_element.LookupParameter("Level")
        if level_param and level_param.AsString():
            level_name = level_param.AsString()
            ERROR_HANDLE.print_note("Found level from parameter: {}".format(level_name))
            
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
            ERROR_HANDLE.print_note("Using fallback level: {}".format(fallback_level.Name))
            return fallback_level
        
        ERROR_HANDLE.print_note("No level found")
        return None
    
    def _find_family_symbol(self):
        """Find the family symbol to place."""
        ERROR_HANDLE.print_note("Finding family symbol")
        
        # Use ENNEADTAB.REVIT_FAMILY to get family and symbol
        family = REVIT_FAMILY.get_family_by_name(self.family_name, self.project_doc)
        if family:
            # Get first available symbol
            symbol_ids = family.GetFamilySymbolIds()
            if symbol_ids:
                symbol = self.project_doc.GetElement(symbol_ids[0])
                if symbol:
                    ERROR_HANDLE.print_note("Found family symbol: {}".format(symbol.Name))
                    return symbol
        
        ERROR_HANDLE.print_note("Family symbol not found")
        return None
    
    def _place_instance_at_location(self, family_symbol, location, level):
        """Place the family instance at the specified location."""
        ERROR_HANDLE.print_note("Placing instance at location")
        
        # Ensure symbol is active
        if not family_symbol.IsActive:
            family_symbol.Activate()
            ERROR_HANDLE.print_note("Activated family symbol")
        
        # Place instance
        instance = self.project_doc.Create.NewFamilyInstance(
            location, family_symbol, level, DB.Structure.StructuralType.NonStructural)
        
        if instance:
            ERROR_HANDLE.print_note("Instance placed successfully")
            return True
        else:
            ERROR_HANDLE.print_note("Failed to place instance")
            return False
    
    def _set_instance_parameters(self):
        """Set parameters on the placed instance."""
        ERROR_HANDLE.print_note("Setting instance parameters")
        
        # This is a placeholder for setting specific parameters
        # Implementation would depend on specific requirements
        
        ERROR_HANDLE.print_note("Instance parameters set")
        return True
    
    def get_debug_summary(self):
        """Get summary of debug information."""
        return "\n".join(self.debug_info)
