#!/usr/bin/python
# -*- coding: utf-8 -*-

"""Family instance placement classes for Area2Mass conversion."""

from Autodesk.Revit import DB # pyright: ignore 


class FamilyInstancePlacer:
    """Handles placing family instances in the project."""
    
    def __init__(self, project_doc, family_name, spatial_element):
        self.project_doc = project_doc
        self.family_name = family_name
        self.spatial_element = spatial_element
    
    def place_instance(self):
        """Place a family instance in the project."""
        try:
            # Find the loaded family symbol
            family_symbols = DB.FilteredElementCollector(self.project_doc).OfClass(DB.FamilySymbol).ToElements()
            target_symbol = None
            
            for symbol in family_symbols:
                if symbol.Family.Name == self.family_name:
                    target_symbol = symbol
                    break
            
            if not target_symbol:
                print("Could not find family symbol: {}".format(self.family_name))
                return False
            
            # Activate the family symbol if needed
            if not target_symbol.IsActive:
                target_symbol.Activate()
            
            # Get placement location from spatial element
            location_point = self.get_spatial_element_location()
            if not location_point:
                print("Could not get location for spatial element")
                return False
            
            # Get level for hosting
            level = self.get_spatial_element_level()
            if not level:
                print("Could not get level for spatial element")
                return False
            
            # Start transaction for placing instance
            t = DB.Transaction(self.project_doc, "Place Mass Family Instance")
            t.Start()
            
            try:
                # Create family instance
                if self.project_doc and location_point and target_symbol and level:
                    instance = self.project_doc.Create.NewFamilyInstance(
                        location_point,
                        target_symbol,
                        level,
                        DB.Structure.StructuralType.NonStructural
                    )
                else:
                    print("Missing required elements for family instance creation")
                    t.RollBack()
                    return False
                
                # Set instance parameters if needed
                self.set_instance_parameters(instance)
                
                t.Commit()
                return True
                
            except Exception as e:
                t.RollBack()
                print("Error placing family instance: {}".format(str(e)))
                return False
                
        except Exception as e:
            print("Error placing family instance in project: {}".format(str(e)))
            return False
    
    def get_spatial_element_location(self):
        """Get the location point of a spatial element."""
        try:
            # Try to get location from spatial element
            if hasattr(self.spatial_element, 'Location') and self.spatial_element.Location:
                if hasattr(self.spatial_element.Location, 'Point'):
                    return self.spatial_element.Location.Point
                elif hasattr(self.spatial_element.Location, 'Curve'):
                    # For curve-based elements, get midpoint
                    curve = self.spatial_element.Location.Curve
                    return curve.GetEndPoint(0).Add(curve.GetEndPoint(1)).Multiply(0.5)
            
            # Fallback: calculate centroid from boundary
            boundary_segments = self.get_boundary_segments()
            if boundary_segments:
                # Calculate centroid from first boundary loop
                for segment_list in boundary_segments:
                    if segment_list:
                        points = []
                        for segment in segment_list:
                            curve = segment.GetCurve()
                            if curve:
                                points.append(curve.GetEndPoint(0))
                                points.append(curve.GetEndPoint(1))
                        
                        if points:
                            # Calculate centroid
                            centroid = DB.XYZ(0, 0, 0)
                            for point in points:
                                centroid = centroid.Add(point)
                            centroid = centroid.Multiply(1.0 / len(points))
                            return centroid
            
            return None
            
        except Exception as e:
            print("Error getting spatial element location: {}".format(str(e)))
            return None
    
    def get_boundary_segments(self):
        """Get boundary segments from spatial element."""
        try:
            options = DB.SpatialElementBoundaryOptions()
            boundary_segments = self.spatial_element.GetBoundarySegments(options)
            return boundary_segments
        except Exception as e:
            print("Error getting boundary segments: {}".format(str(e)))
            return None
    
    def get_spatial_element_level(self):
        """Get the level of a spatial element."""
        try:
            # Try to get level parameter
            level_param = self.spatial_element.LookupParameter("Level")
            if level_param and self.project_doc:
                level_id = level_param.AsElementId()
                if level_id != DB.ElementId.InvalidElementId:
                    level = self.project_doc.GetElement(level_id)
                    if level:
                        return level
            
            # Fallback: get first level in project
            levels = DB.FilteredElementCollector(self.project_doc).OfClass(DB.Level).WhereElementIsNotElementType().ToElements()
            if levels:
                return levels[0]
            
            return None
            
        except Exception as e:
            print("Error getting spatial element level: {}".format(str(e)))
            return None
    
    def set_instance_parameters(self, instance):
        """Set parameters on the family instance based on spatial element."""
        try:
            # Copy key parameters from spatial element to family instance
            parameters_to_copy = ["Name", "Number", "Area", "Perimeter"]
            
            for param_name in parameters_to_copy:
                source_param = self.spatial_element.LookupParameter(param_name)
                target_param = instance.LookupParameter(param_name)
                
                if source_param and target_param:
                    if source_param.StorageType == DB.StorageType.String:
                        target_param.Set(source_param.AsString())
                    elif source_param.StorageType == DB.StorageType.Double:
                        target_param.Set(source_param.AsDouble())
                    elif source_param.StorageType == DB.StorageType.Integer:
                        target_param.Set(source_param.AsInteger())
            
            # Set a custom parameter to track the source
            source_param = instance.LookupParameter("Source Element")
            if source_param:
                source_param.Set("Area2Mass Conversion")
                
        except Exception as e:
            print("Error setting instance parameters: {}".format(str(e)))
