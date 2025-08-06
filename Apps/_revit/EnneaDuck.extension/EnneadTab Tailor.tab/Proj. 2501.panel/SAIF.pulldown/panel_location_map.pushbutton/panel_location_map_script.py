#!/usr/bin/python
# -*- coding: utf-8 -*-

__doc__ = "Maps curtain wall panels to their grid positions (U and V indices) and saves the mapping data for use in other tools. This tool analyzes all curtain wall panels in the document and creates a location map that can be used for panel selection and analysis."
__title__ = "Panel Location Map"

import proDUCKtion # pyright: ignore 
proDUCKtion.validify()

from EnneadTab import ERROR_HANDLE, LOG, DATA_FILE, NOTIFICATION
from EnneadTab.REVIT import REVIT_APPLICATION, REVIT_UNIT, REVIT_GEOMETRY
from Autodesk.Revit import DB # pyright: ignore 

UIDOC = REVIT_APPLICATION.get_uidoc()
DOC = REVIT_APPLICATION.get_doc()

# Global constants
SEARCH_DISTANCE_TOLERANCE_MM = 200  # 0.2 meters in millimeters
MAX_SEARCH_DISTANCE_TOLERANCE_MM = 2000  # 2.0 meters maximum tolerance
TOLERANCE_INCREMENT_MM = 200  # 0.2 meters increment


class SpatialIndex:
    """
    A simple spatial index to quickly find panels near specific locations.
    """
    
    def __init__(self, panels, cell_size=1000):
        """
        Initialize spatial index with panels.
        
        Args:
            panels: List of panel elements
            cell_size: Size of spatial cells in Revit internal units
        """
        self.cell_size = cell_size
        self.spatial_grid = {}
        self.panel_centers = {}
        
        # Build spatial index
        for panel in panels:
            center = REVIT_GEOMETRY.get_element_center(panel)
            if center is not None:
                self.panel_centers[panel.Id] = center
                cell_key = self._get_cell_key(center)
                if cell_key not in self.spatial_grid:
                    self.spatial_grid[cell_key] = []
                self.spatial_grid[cell_key].append(panel.Id)
    
    def _get_cell_key(self, point):
        """Get cell key for a point."""
        x_cell = int(point.X / self.cell_size)
        y_cell = int(point.Y / self.cell_size)
        z_cell = int(point.Z / self.cell_size)
        return (x_cell, y_cell, z_cell)
    
    def find_panels_near_point(self, point, tolerance):
        """
        Find panels near a point using spatial indexing.
        
        Args:
            point: DB.XYZ point to search near
            tolerance: Distance tolerance in Revit internal units
            
        Returns:
            list: List of panel IDs near the point
        """
        nearby_panels = []
        
        # Calculate which cells to check based on tolerance
        cell_range = int(tolerance / self.cell_size) + 1
        base_cell = self._get_cell_key(point)
        
        # Check neighboring cells
        for dx in range(-cell_range, cell_range + 1):
            for dy in range(-cell_range, cell_range + 1):
                for dz in range(-cell_range, cell_range + 1):
                    cell_key = (base_cell[0] + dx, base_cell[1] + dy, base_cell[2] + dz)
                    if cell_key in self.spatial_grid:
                        for panel_id in self.spatial_grid[cell_key]:
                            panel_center = self.panel_centers[panel_id]
                            if point.DistanceTo(panel_center) <= tolerance:
                                nearby_panels.append(panel_id)
        
        return nearby_panels


class PanelLocationMapper:
    """
    A class to handle mapping curtain wall panels to their locations and updating their parameters.
    """
    
    def __init__(self, doc):
        """
        Initialize the PanelLocationMapper.
        
        Args:
            doc: Revit document
        """
        self.doc = doc
        self.all_panels = None
        self.data = None
        self.spatial_index = None
        self.panel_dict = None
        self.family_name_cache = {}
        
    def get_all_panels(self):
        """
        Get all curtain wall panels in the document.
        
        Returns:
            list: List of curtain wall panel elements
        """
        if self.all_panels is None:
            self.all_panels = DB.FilteredElementCollector(self.doc).OfCategory(
                DB.BuiltInCategory.OST_CurtainWallPanels).WhereElementIsNotElementType().ToElements()
        return self.all_panels
    
    def build_panel_dict(self):
        """
        Build a dictionary of panels indexed by ID for fast lookup.
        """
        if self.panel_dict is None:
            panels = self.get_all_panels()
            self.panel_dict = {panel.Id: panel for panel in panels}
        return self.panel_dict
    
    def build_spatial_index(self):
        """
        Build spatial index for fast location-based panel finding.
        Optimized for panels that are typically 1.5m x 4.5m.
        """
        if self.spatial_index is None:
            panels = self.get_all_panels()
            # Use 2 meter cell size (converted to Revit internal units)
            # This is optimal for panels that are 1.5m x 4.5m
            # - Large enough to contain most panels in 1-2 cells
            # - Small enough to avoid too many panels per cell
            cell_size = REVIT_UNIT.mm_to_internal(2000)  # 2 meters
            self.spatial_index = SpatialIndex(panels, cell_size)
        return self.spatial_index
    
    def get_panel_family_name(self, panel):
        """
        Get panel family name with comprehensive detection and caching.
        Based on Revit API documentation: FamilyName property on ElementType.
        
        Args:
            panel: Panel element
            
        Returns:
            str: Family name or "N/A" if not available
        """
        panel_id = panel.Id
        if panel_id not in self.family_name_cache:
            try:
                # Method 1: Try PanelType.FamilyName (for loaded families) - Official API method
                if hasattr(panel, 'PanelType') and panel.PanelType is not None:
                    if hasattr(panel.PanelType, 'FamilyName'):
                        family_name = panel.PanelType.FamilyName
                        if family_name and family_name.strip():
                            self.family_name_cache[panel_id] = family_name
                            return self.family_name_cache[panel_id]
                        else:
                            print("  Debug: PanelType.FamilyName exists but is empty for panel {}".format(panel.Id))
                    elif hasattr(panel.PanelType, 'Family') and panel.PanelType.Family:
                        self.family_name_cache[panel_id] = panel.PanelType.Family.Name
                        return self.family_name_cache[panel_id]
                    else:
                        print("  Debug: PanelType exists but no FamilyName or Family property for panel {}".format(panel.Id))
                else:
                    # print("  Debug: No PanelType property for panel {}".format(panel.Id))
                    pass
                
                # Method 2: Try Family property directly
                if hasattr(panel, 'Family') and panel.Family:
                    self.family_name_cache[panel_id] = panel.Family.Name
                    return self.family_name_cache[panel_id]
                
                # Method 3: Try FamilyName property directly
                if hasattr(panel, 'FamilyName') and panel.FamilyName:
                    self.family_name_cache[panel_id] = panel.FamilyName
                    return self.family_name_cache[panel_id]
                
                # Method 4: Try Symbol property (for system families)
                if hasattr(panel, 'Symbol') and panel.Symbol:
                    if hasattr(panel.Symbol, 'Family') and panel.Symbol.Family:
                        self.family_name_cache[panel_id] = panel.Symbol.Family.Name
                        return self.family_name_cache[panel_id]
                
                # Method 5: Try Category name as fallback
                if hasattr(panel, 'Category') and panel.Category:
                    self.family_name_cache[panel_id] = panel.Category.Name
                    return self.family_name_cache[panel_id]
                
                # Method 6: Try Type name as fallback (for system panels)
                if hasattr(panel, 'Name') and panel.Name:
                    self.family_name_cache[panel_id] = panel.Name
                    return self.family_name_cache[panel_id]
                
                # If all methods fail, return "N/A"
                self.family_name_cache[panel_id] = "N/A"
                print("  Debug: All family name detection methods failed for panel {}".format(panel.Id))
                
            except Exception as e:
                print("Warning: Could not get family name for panel {}: {}".format(panel.Id, str(e)))
                self.family_name_cache[panel_id] = "N/A"
        
        return self.family_name_cache[panel_id]
    
    def load_mapping_data(self):
        """
        Load the SAIF panel mapping data.
        
        Returns:
            dict: Mapping data from the data file
        """
        if self.data is None:
            self.data = DATA_FILE.get_data("SAIF_panel_mapping")
        return self.data
    
    def convert_coordinates(self, location, unit="mm"):
        """
        Convert coordinates from Rhino units to Revit internal units.
        
        Args:
            location (list): List of coordinate dictionaries with X, Y, Z keys
            unit (str): Unit of the coordinates (mm, m, ft, in, etc.)
            
        Returns:
            list: List of DB.XYZ points in Revit internal units
        """
        print("Converting coordinates from {} units...".format(unit))
        print("Sample original coordinates:")
        for i, pt in enumerate(location[:3]):
            print("  Point {}: ({}, {}, {}) {}".format(i + 1, pt["X"], pt["Y"], pt["Z"], unit))
        
        if unit == "mm":
            converted = [DB.XYZ(REVIT_UNIT.mm_to_internal(pt["X"]), 
                          REVIT_UNIT.mm_to_internal(pt["Y"]), 
                          REVIT_UNIT.mm_to_internal(pt["Z"])) for pt in location]
        elif unit == "m":
            converted = [DB.XYZ(REVIT_UNIT.m_to_internal(pt["X"]), 
                          REVIT_UNIT.m_to_internal(pt["Y"]), 
                          REVIT_UNIT.m_to_internal(pt["Z"])) for pt in location]
        elif unit in ["ft", "feet"]:
            # If already in feet, no conversion needed (Revit internal units are feet)
            converted = [DB.XYZ(pt["X"], pt["Y"], pt["Z"]) for pt in location]
        elif unit in ["in", "inches"]:
            # Convert inches to feet
            converted = [DB.XYZ(pt["X"]/12.0, pt["Y"]/12.0, pt["Z"]/12.0) for pt in location]
        else:
            # Fallback to millimeters if unit is unknown
            print("Warning: Unknown unit '{}', assuming millimeters".format(unit))
            converted = [DB.XYZ(REVIT_UNIT.mm_to_internal(pt["X"]), 
                          REVIT_UNIT.mm_to_internal(pt["Y"]), 
                          REVIT_UNIT.mm_to_internal(pt["Z"])) for pt in location]
        
        print("Sample converted coordinates (Revit internal units):")
        for i, pt in enumerate(converted[:3]):
            print("  Point {}: ({:.2f}, {:.2f}, {:.2f}) feet".format(i + 1, pt.X, pt.Y, pt.Z))
        
        return converted
    
    def get_panels_by_locations(self, location_mapped, initial_tolerance, target_family_name, used_panels=None):
        """
        Find panels for each location within tolerance using spatial indexing.
        Each location gets a unique panel (no duplicates).
        Progressively increases tolerance if no panels are found.
        
        Args:
            location_mapped (list): List of DB.XYZ points to search near
            initial_tolerance (float): Initial distance tolerance in Revit internal units
            target_family_name (str): Expected family name for filtering (None to skip filtering)
            used_panels (set): Set of panel IDs that have already been used
            
        Returns:
            dict: Dictionary mapping location index to panel element, or None if not found
        """
        if used_panels is None:
            used_panels = set()
            
        spatial_index = self.build_spatial_index()
        panel_dict = self.build_panel_dict()
        
        if target_family_name:
            print("Searching for panels with family name: '{}'".format(target_family_name))
        else:
            print("Searching for panels without family name filtering")
        
        # Debug: Check what family names are actually available (only show if verbose)
        available_families = set()
        for panel in self.get_all_panels():
            family_name = self.get_panel_family_name(panel)
            available_families.add(family_name)
        print("Available family names: {}".format(sorted(list(available_families))))
        
        location_to_panel = {}
        current_tolerance = initial_tolerance
        max_tolerance = REVIT_UNIT.mm_to_internal(MAX_SEARCH_DISTANCE_TOLERANCE_MM)
        tolerance_increment = REVIT_UNIT.mm_to_internal(TOLERANCE_INCREMENT_MM)
        
        print("Starting with tolerance: {:.2f} feet ({:.0f} mm)".format(current_tolerance, current_tolerance * 304.8))
        
        # Try to find panels for each location with progressive tolerance increase
        for i, pt in enumerate(location_mapped):
            print("Checking location {}: ({:.2f}, {:.2f}, {:.2f})".format(
                i + 1, pt.X, pt.Y, pt.Z))
            
            panel_found = False
            attempt_tolerance = current_tolerance
            
            # Progressively increase tolerance until panel is found or max tolerance reached
            while attempt_tolerance <= max_tolerance and not panel_found:
                nearby_panel_ids = spatial_index.find_panels_near_point(pt, attempt_tolerance)
                
                # Check each nearby panel for family name match (skip already used panels)
                for panel_id in nearby_panel_ids:
                    if panel_id in used_panels:
                        continue  # Skip already used panels
                        
                    panel = panel_dict[panel_id]
                    family_name = self.get_panel_family_name(panel)
                    
                    # If no family name filtering, use the first unused panel found
                    if target_family_name is None:
                        print("  MATCH FOUND! Panel '{}' at location {} (no family filtering)".format(panel.Name, i + 1))
                        location_to_panel[i] = panel
                        used_panels.add(panel_id)
                        panel_found = True
                        break
                    # Otherwise, check for family name match
                    elif family_name == target_family_name:
                        print("  MATCH FOUND! Panel '{}' at location {} (tolerance: {:.0f}mm)".format(panel.Name, i + 1, attempt_tolerance * 304.8))
                        location_to_panel[i] = panel
                        used_panels.add(panel_id)
                        panel_found = True
                        break
                
                if not panel_found:
                    attempt_tolerance += tolerance_increment
            
            if not panel_found:
                print("  No suitable panel found for location {} even with maximum tolerance".format(i + 1))
            else:
                # Update current tolerance to the successful tolerance for next locations
                current_tolerance = attempt_tolerance
        
        print("Found {} panels for {} locations".format(len(location_to_panel), len(location_mapped)))
        return location_to_panel
    
    def update_panel_parameters_batch(self, panel, parameter_updates):
        """
        Update multiple panel parameters in batch within a transaction.
        
        Args:
            panel (DB.Element): Panel element to update
            parameter_updates (dict): Dictionary of parameter_name: value pairs
            
        Returns:
            bool: True if all updates were successful
        """
        try:
            # Start a transaction for this batch of parameter updates
            t = DB.Transaction(self.doc, "Update Panel Parameters")
            t.Start()
            
            success = True
            for param_name, value in parameter_updates.items():
                param = panel.LookupParameter(param_name)
                if param is not None:
                    param.Set(value)
                else:
                    print("Warning: Parameter '{}' not found on panel '{}'".format(param_name, panel.Name))
                    success = False
            
            if success:
                t.Commit()
                # print("  Transaction committed successfully")
            else:
                t.RollBack()
                print("  Transaction rolled back due to parameter errors")
            
            return success
            
        except Exception as e:
            print("Error updating parameters on panel '{}': {}".format(panel.Name, str(e)))
            # Make sure to rollback transaction if there's an error
            try:
                if t.HasStarted():
                    t.RollBack()
                    print("  Transaction rolled back due to error")
            except:
                pass
            return False
    
    def process_mapping_block(self, key, value):
        """
        Process a single mapping block from the data.
        
        Args:
            key (str): Block key
            value (dict): Block data containing mapping_data and locations
            
        Returns:
            bool: True if processing was successful
        """
        print("Processing block: ", key)
        print("family_name: ", value["mapping_data"]["family_name"])
        print("side_frame_w: ", value["mapping_data"]["side_frame_w"])
        print("is_FRW: ", value["mapping_data"].get("is_FRW", False))
        
        locations = value["locations"]
        print("Unit detected: ", value.get("unit", "mm (default)"))
        print("Number of locations: ", len(locations))
        
        # Convert coordinates
        unit = value.get("unit", "mm")
        location_mapped = self.convert_coordinates(locations, unit)

        
        # Debug: Show first few converted coordinates
        def _show_location(_locations):
            for i, pt in enumerate(_locations[:3]):
                if hasattr(pt, 'X'):  # DB.XYZ object
                    print("  Location {}: ({:.2f}, {:.2f}, {:.2f}) feet".format(i + 1, pt.X, pt.Y, pt.Z))
                else:  # Dictionary object
                    print("  Location {}: ({}, {}, {})".format(i + 1, pt.get("X", "N/A"), pt.get("Y", "N/A"), pt.get("Z", "N/A")))
        print("Sample coordinates:")
        _show_location(location_mapped)
        
        # Set tolerance for individual location matching
        # Use global constant for panel matching tolerance
        tolerance = REVIT_UNIT.mm_to_internal(SEARCH_DISTANCE_TOLERANCE_MM)  # 0.2 meters
        
        # Find panels for each location with family name filtering
        target_family_name = value["mapping_data"]["family_name"]
        used_panels = set()  # Track used panels to avoid duplicates
        
        # First try with family name filtering
        location_to_panel_dict = self.get_panels_by_locations(location_mapped, tolerance, target_family_name, used_panels)
        
        # If not enough panels found, try without family name filtering for remaining locations
        if len(location_to_panel_dict) < len(location_mapped):
            print("Only found {} panels with family name '{}', trying without family filtering for remaining locations...".format(
                len(location_to_panel_dict), target_family_name))
            remaining_locations = [i for i in range(len(location_mapped)) if i not in location_to_panel_dict]
            remaining_panels = self.get_panels_by_locations(
                [location_mapped[i] for i in remaining_locations], 
                tolerance, None, used_panels)
            # Update location_to_panel with remaining panels
            for i, panel in remaining_panels.items():
                location_to_panel_dict[remaining_locations[i]] = panel
        
        if location_to_panel_dict:
            # Prepare batch parameter updates
            parameter_updates = {
                "side_frame_w": REVIT_UNIT.mm_to_internal(value["mapping_data"]["side_frame_w"])
            }
            
            # Add FRW parameter if needed (only if it exists on panels)
            if value["mapping_data"].get("is_FRW", False):
                # Check if the parameter exists on the first panel
                first_panel = next(iter(location_to_panel_dict.values()))
                frw_param = first_panel.LookupParameter("is_FRW")
                if frw_param is not None:
                    parameter_updates["is_FRW"] = True
                else:
                    print("Note: 'is_FRW' parameter not found on panels, skipping this parameter")
            
            # Update parameters for each panel
            success_count = 0
            for location_idx, panel in location_to_panel_dict.items():
                success = self.update_panel_parameters_batch(panel, parameter_updates)
                if success:
                    success_count += 1
                else:
                    print("Failed to update panel '{}' at location {}".format(panel.Name, location_idx + 1))
            
            print("Updated {}/{} panels for block '{}'".format(success_count, len(location_to_panel_dict), key))
            return success_count > 0
        else:
            print("No panels found for any location in block: ", key)
            return False
    
    def run(self):
        """
        Main method to run the panel location mapping process.
        
        Returns:
            dict: Results of the mapping process
        """
        # Get all panels
        panels = self.get_all_panels()
        if not panels:
            NOTIFICATION.messenger("No curtain wall panels found in the document."))
            return {}
        
        print("Found {} curtain wall panels".format(len(panels)))
        
        # Load mapping data
        data = self.load_mapping_data()
        if not data:
            NOTIFICATION.messenger("No SAIF panel mapping data found."))
            return {}
        
        # Print data structure overview
        print("\nData file structure:")
        print("Available keys: {}".format(list(data.keys())))
        print("Total mapping blocks: {}".format(len(data)))
        
        # Print sample data for each key
        print("\nSample data for each mapping block:")
        for key, value in data.items():
            print("  Key: '{}'".format(key))
            if "mapping_data" in value:
                print("    Family: '{}'".format(value["mapping_data"].get("family_name", "N/A")))
                print("    Side frame width: {} mm".format(value["mapping_data"].get("side_frame_w", "N/A")))
                print("    Is FRW: {}".format(value["mapping_data"].get("is_FRW", False)))
            if "locations" in value:
                locations = value["locations"]
                print("    Number of locations: {}".format(len(locations)))
                if locations:
                    # Show first and last location coordinates
                    first_loc = locations[0]
                    last_loc = locations[-1]
                    unit = value.get("unit", "mm")
                    print("    First location: ({}, {}, {}) {}".format(
                        first_loc.get("X", "N/A"), first_loc.get("Y", "N/A"), first_loc.get("Z", "N/A"), unit))
                    print("    Last location: ({}, {}, {}) {}".format(
                        last_loc.get("X", "N/A"), last_loc.get("Y", "N/A"), last_loc.get("Z", "N/A"), unit))
            print("")
        
        # Pre-build spatial index and panel dictionary
        print("Building spatial index...")
        self.build_spatial_index()
        self.build_panel_dict()
        
        # Print spatial index statistics
        spatial_index = self.build_spatial_index()
        total_cells = len(spatial_index.spatial_grid)
        total_panels = len(panels)
        avg_panels_per_cell = total_panels / max(total_cells, 1)
        print("Spatial Index Statistics:")
        print("  - Total cells: {}".format(total_cells))
        print("  - Total panels: {}".format(total_panels))
        print("  - Average panels per cell: {}".format(avg_panels_per_cell))
        print("  - Cell size: 2.0 meters (optimized for 1.5m x 4.5m panels)")
        
        # Debug: Show some panel locations and properties
        print("\nSample panel locations (first 3):")
        for i, panel in enumerate(panels[:3]):
            center = REVIT_GEOMETRY.get_element_center(panel)
            if center:
                family_name = self.get_panel_family_name(panel)
                print("  Panel '{}': ({:.2f}, {:.2f}, {:.2f}) - Family: '{}'".format(
                    panel.Id, center.X, center.Y, center.Z, family_name))
        
        # Debug: Show coordinate ranges for all panels
        print("Coordinate ranges for all panels:")
        all_centers = []
        for panel in panels:
            center = REVIT_GEOMETRY.get_element_center(panel)
            if center:
                all_centers.append(center)
        
        if all_centers:
            x_coords = [pt.X for pt in all_centers]
            y_coords = [pt.Y for pt in all_centers]
            z_coords = [pt.Z for pt in all_centers]
            
            print("  X range: {:.2f} to {:.2f} feet".format(min(x_coords), max(x_coords)))
            print("  Y range: {:.2f} to {:.2f} feet".format(min(y_coords), max(y_coords)))
            print("  Z range: {:.2f} to {:.2f} feet".format(min(z_coords), max(z_coords)))
            print("")
        
        # Start transaction group for all operations
        tg = DB.TransactionGroup(self.doc, "Panel Location Mapping")
        tg.Start()
        
        try:
            # Process each mapping block
            results = {}
            data_items = list(data.items())
            
            for i, (key, value) in enumerate(data_items):
                print("--------------------------------")
                print("Processing block {} of {}: {}".format(i + 1, len(data_items), key))
                success = self.process_mapping_block(key, value)
                results[key] = success
            
            # Commit the transaction group if everything was successful
            tg.Assimilate()
            print("\nTransaction group committed successfully!")
            return results
            
        except Exception as e:
            print("Error in panel location mapping: {}".format(str(e)))
            tg.RollBack()
            print("Transaction group rolled back due to error")
            return {}


@LOG.log(__file__, __title__)
@ERROR_HANDLE.try_catch_error()
def panel_location_map(doc):
    """
    Creates a mapping of curtain wall panels to their grid positions.
    
    Args:
        doc: Revit document
        
    Returns:
        dict: Results of the mapping process
    """
    mapper = PanelLocationMapper(doc)
    return mapper.run()


################## main code below #####################
if __name__ == "__main__":
    panel_location_map(DOC)







