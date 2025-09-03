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
        print("=== INSTANCE PLACEMENT DEBUG ===")
        
        # Start transaction for instance placement
        t = DB.Transaction(self.project_doc, "Place Area2Mass Instance")
        t.Start()
        
        try:
            # Step 1: Get spatial element location
            location = self._get_spatial_element_location()
            if not location:
                print("FAILED: Could not determine spatial element location")
                t.RollBack()
                return False
            
            # Step 2: Get boundary segments for orientation
            boundary_segments = self._get_boundary_segments()
            if not boundary_segments:
                print("FAILED: Could not get boundary segments for orientation")
                t.RollBack()
                return False
            
            # Step 3: Get level for hosting
            level = self._get_spatial_element_level()
            if not level:
                print("FAILED: Could not determine level for hosting")
                t.RollBack()
                return False
            
            # Step 4: Find family symbol
            print("--- STEP 4: Finding family symbol ---")
            family_symbol = self._find_family_symbol()
            if not family_symbol:
                print("FAILED: Could not find family symbol")
                t.RollBack()
                return False
            # Get symbol name using LookupParameter
            try:
                symbol_name = family_symbol.LookupParameter("Type Name").AsString()
                print("SUCCESS: Family symbol found: {} (ID: {})".format(symbol_name, family_symbol.Id))
            except Exception as e:
                print("SUCCESS: Family symbol found (ID: {})".format(family_symbol.Id))
            
            # Step 5: Check if instance already exists
            print("--- STEP 5: Checking for existing instances ---")
            existing_instance = self._check_for_existing_instance(family_symbol)
            if existing_instance:
                print("SUCCESS: Instance already exists (ID: {})".format(existing_instance.Id))
                t.Commit()
                return True
            
            # Step 6: Place instance
            print("--- STEP 6: Placing instance ---")
            try:
                placement_result = self._place_instance_at_location(family_symbol, location, level)
                if not placement_result:
                    print("FAILED: Could not place instance")
                    t.RollBack()
                    return False
            except Exception as e:
                print("EXCEPTION during instance placement: {}".format(str(e)))
                print("Exception type: {}".format(type(e).__name__))
                import traceback
                traceback.print_exc()
                t.RollBack()
                return False
            
            # Commit transaction
            t.Commit()
            print("SUCCESS: Instance placement completed")
            return True
            
        except Exception as e:
            print("EXCEPTION during instance placement: {}".format(str(e)))
            print("Exception type: {}".format(type(e).__name__))
            import traceback
            traceback.print_exc()
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
                    print("Found existing instance: ID {}, Type: {}".format(instance.Id, instance.Symbol.LookupParameter("Type Name").AsString()))
                    return instance
            
            print("No existing instances found for this family type")
            return None
            
        except Exception as e:
            print("Error checking for existing instances: {}".format(str(e)))
            return None
    
    def _get_spatial_element_location(self):
        """Get placement point. Use Internal Origin (0,0,0) to align with created family geometry."""
        print("Using Internal Origin for placement (0,0,0)")
        return DB.XYZ(0, 0, 0)
    
    def _get_boundary_segments(self):
        """Get boundary segments for orientation."""
        options = DB.SpatialElementBoundaryOptions()
        segments = self.spatial_element.GetBoundarySegments(options)
        
        if segments and len(segments) > 0:
            print("SUCCESS: Boundary segments found: {} lists".format(len(segments)))
            return segments
        else:
            print("No boundary segments found")
            return None
    
    def _get_spatial_element_level(self):
        """Get the level where the spatial element is hosted."""
        print("Getting spatial element level")
        
        # Try to get level from spatial element
        if hasattr(self.spatial_element, 'Level'):
            level = self.spatial_element.Level
            if level:
                print("Found level: {}".format(level.Name))
                return level
        
        # Try to get level from parameters
        level_param = self.spatial_element.LookupParameter("Level")
        if level_param and level_param.AsString():
            level_name = level_param.AsString()
            print("Found level from parameter: {}".format(level_name))
            
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
            print("Using fallback level: {}".format(fallback_level.Name))
            return fallback_level
        
        print("No level found")
        return None
    
    def _find_family_symbol(self):
        """Find the family symbol to place using REVIT_FAMILY module."""
        print("Finding family symbol for: '{}'".format(self.family_name))
        
        # Use REVIT_FAMILY.get_all_types_by_family_name to get symbols directly
        family_symbols = REVIT_FAMILY.get_all_types_by_family_name(self.family_name, self.project_doc)
        
        if family_symbols:
            print("Found {} family symbols".format(len(family_symbols)))
            
            # Get the first available symbol
            first_symbol = family_symbols[0]
            
            # Check if it has the expected attributes - use try/catch instead of hasattr
            try:
                symbol_name = first_symbol.LookupParameter("Type Name").AsString()
                print("Symbol name: {}".format(symbol_name))
            except Exception as e:
                print("Error accessing Type Name parameter: {}".format(str(e)))
                return None
                
            try:
                symbol_id = first_symbol.Id
                print("Symbol ID: {}".format(symbol_id))
            except Exception as e:
                print("Error accessing Id attribute: {}".format(str(e)))
                return None
                
            # Check if symbol is active and activate if needed
            try:
                is_active = first_symbol.IsActive
                print("Symbol IsActive: {}".format(is_active))
                
                if not is_active:
                    print("Activating symbol...")
                    first_symbol.Activate()
                    print("Symbol activated successfully")
                    
            except Exception as e:
                print("Error checking/activating symbol: {}".format(str(e)))
                return None
                
            print("Symbol details - IsValidObject: {}".format(first_symbol.IsValidObject))
            return first_symbol
        else:
            print("No family symbols found for family: '{}'".format(self.family_name))
            
            # Debug: list all available families
            collector = DB.FilteredElementCollector(self.project_doc).OfClass(DB.Family)
            families = collector.ToElements()
            family_names = [f.Name for f in families]
            print("Available families in project ({} total):".format(len(family_names)))
            for i, name in enumerate(family_names[:10]):  # Show first 10
                print("  {}. '{}'".format(i+1, name))
            if len(family_names) > 10:
                print("  ... and {} more".format(len(family_names) - 10))
            
            # Check for similar names
            similar_names = [n for n in family_names if self.family_name.lower() in n.lower() or n.lower() in self.family_name.lower()]
            if similar_names:
                print("Similar family names found:")
                for name in similar_names:
                    print("  - '{}'".format(name))
        
        print("Family symbol not found")
        return None
    
    def _place_instance_at_location(self, family_symbol, location, level):
        """Place the family instance at Internal Origin on the specified level, using proven move2origin approach."""
        print("--- STEP 5: Placing instance ---")
        print("Placing instance at Internal Origin on level '{}'".format(level.Name if level else "<None>"))
        print("Location: {}".format(location))
        
        # Get symbol name using LookupParameter
        try:
            symbol_name = family_symbol.LookupParameter("Type Name").AsString()
            print("Family symbol: '{}' (ID: {})".format(symbol_name, family_symbol.Id))
        except Exception as e:
            print("Warning: Could not get symbol name: {}".format(str(e)))
            print("Family symbol: (ID: {})".format(family_symbol.Id))
        
        # Ensure symbol is active
        if not family_symbol.IsActive:
            print("Symbol not active, activating...")
            family_symbol.Activate()
            print("Symbol activated")
        else:
            print("Symbol already active")
        
        # Use the proven move2origin approach for instance creation
        print("Creating NewFamilyInstance using proven approach...")
        print("Debug info:")
        print("  - location: {}".format(location))
        print("  - family_symbol type: {}".format(type(family_symbol).__name__))
        print("  - family_symbol ID: {}".format(family_symbol.Id))
        print("  - level: {}".format(level.Name if level else "None"))
        print("  - project_doc.IsFamilyDocument: {}".format(self.project_doc.IsFamilyDocument))
        
        try:
            # Use correct document creation context (like move2origin does)
            if self.project_doc.IsFamilyDocument:
                doc_create = self.project_doc.FamilyCreate
                print("Using FamilyCreate context")
            else:
                doc_create = self.project_doc.Create
                print("Using Create context")
            
            print("About to call NewFamilyInstance...")
            # Create instance using the proven method
            instance = doc_create.NewFamilyInstance(
                location, family_symbol, level, DB.Structure.StructuralType.NonStructural)
            print("NewFamilyInstance created successfully")
            
        except Exception as e:
            print("Failed to create NewFamilyInstance: {}".format(str(e)))
            print("Exception type: {}".format(type(e).__name__))
            import traceback
            traceback.print_exc()
            return False
        
        if not instance:
            print("NewFamilyInstance returned None")
            return False

        print("Instance created with ID: {}".format(instance.Id))
        
        # Handle level offset like move2origin does
        print("Setting level offset parameters...")
        if level.Elevation != 0:

            print("Level elevation: {}, setting offset: {}".format(level.Elevation, 0))
            
            # Try common parameter names for offset (like move2origin does)
            for para_name in ["Elevation from Level", "Offset from Host"]:
                para = instance.LookupParameter(para_name)
                if para and not para.IsReadOnly:
                    try:
                        para.Set(0)
                        print("Set parameter '{}' to {}".format(para_name, 0))
                        break
                    except Exception as e:
                        print("Warning: Could not set parameter '{}': {}".format(para_name, str(e)))
        else:
            print("Level is at elevation 0, no offset needed")

        # Pin instance
        try:
            instance.Pinned = True
            print("Instance pinned successfully")
        except Exception as e:
            print("Warning: Could not pin instance: {}".format(str(e)))
        
        print("Instance placement completed successfully using proven move2origin approach")
        return True
    

    
    def get_debug_summary(self):
        """Get summary of debug information."""
        return "\n".join(self.debug_info)
