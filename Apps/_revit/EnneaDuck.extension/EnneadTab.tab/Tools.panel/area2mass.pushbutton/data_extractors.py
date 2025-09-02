#!/usr/bin/python
# -*- coding: utf-8 -*-

"""Data extraction classes for Area2Mass conversion."""

from Autodesk.Revit import DB # pyright: ignore 


class ElementInfoExtractor:
    """Extracts and validates element information."""
    
    def __init__(self, spatial_element, element_type):
        self.spatial_element = spatial_element
        self.element_type = element_type
        self.name = None
        self.is_valid_flag = False
        self.extract_info()
    
    def extract_info(self):
        """Extract element information."""
        try:
            # Try to get name parameter
            name_param = self.spatial_element.LookupParameter("Name")
            if name_param and name_param.AsString():
                base_name = name_param.AsString()
            else:
                # Fallback to number parameter
                number_param = self.spatial_element.LookupParameter("Number")
                if number_param and number_param.AsString():
                    base_name = number_param.AsString()
                else:
                    # Final fallback to element ID
                    base_name = "{}_ID{}".format(self.element_type, self.spatial_element.Id.IntegerValue)
            
            # Sanitize name for Revit family naming
            self.name = self.sanitize_family_name(base_name)
            self.is_valid_flag = True
            
        except Exception as e:
            print("Error extracting element info: {}".format(str(e)))
            self.is_valid_flag = False
    
    def sanitize_family_name(self, name):
        """Sanitize name for use as Revit family name."""
        # Remove or replace invalid characters
        invalid_chars = ['<', '>', ':', '"', '/', '\\', '|', '?', '*']
        for char in invalid_chars:
            name = name.replace(char, '_')
        
        # Limit length
        if len(name) > 50:
            name = name[:50]
        
        # Ensure it's not empty
        if not name.strip():
            name = "Unnamed"
        
        return name.strip()
    
    def is_valid(self):
        return self.is_valid_flag and self.name is not None


class BoundaryDataExtractor:
    """Extracts boundary data from spatial elements."""
    
    def __init__(self, spatial_element):
        self.spatial_element = spatial_element
        self.segments = None
        self.is_valid_flag = False
        self.extract_boundaries()
    
    def extract_boundaries(self):
        """Extract boundary segments."""
        try:
            options = DB.SpatialElementBoundaryOptions()
            self.segments = self.spatial_element.GetBoundarySegments(options)
            self.is_valid_flag = self.segments is not None and len(self.segments) > 0
            
        except Exception as e:
            print("Error extracting boundaries: {}".format(str(e)))
            self.is_valid_flag = False
    
    def is_valid(self):
        return self.is_valid_flag
