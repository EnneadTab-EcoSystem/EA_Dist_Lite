
__title__ = "SaifPanelMapping"
__doc__ = "Maps SAIF panels using new naming convention CW01_SOLID X_YYYY_ZZZZ and CW06_SOLID X_YYYY_ZZZZ, extracting pier width (X) as-is"


from EnneadTab import ERROR_HANDLE, LOG, DATA_FILE
from EnneadTab.RHINO import RHINO_OBJ_DATA
import rhinoscriptsyntax as rs
import Rhino
import re

# Py2/Py3 compatibility for linters; define basestring if missing
try:
    basestring  # type: ignore[name-defined]
except NameError:
    # define for type checkers; in IronPython 2.7 this already exists
    class basestring(str):
        pass


class SAIFPanelMapper:
    """
    A class to handle SAIF panel mapping functionality.
    
    Maps SAIF panels using the new naming convention:
    - CW01_SOLID X_YYYY_ZZZZ (tower main family)
    - CW06_SOLID X_YYYY_ZZZZ (podium main family)
    
    Where X is the pier width extracted as-is (no plus 50), Y is block height, 
    and Z are special notes like FRW (fire rescue window), PIER, CORNER, etc.
    """
    
    def __init__(self):
        """Initialize the mapper with raw mapping data."""
        self._RAW_MAPPING = {
            # Exact rule: CW01_SOLID (frame width)_(anything)
            r"^CW01_SOLID (\d+)_(.+)$": {"family_name": "tower_main", "side_frame_w": "extract_width", "is_FRW": False},
            
            # Exact rule counterpart for CW06
            r"^CW06_SOLID (\d+)_(.+)$": {"family_name": "podium_main", "side_frame_w": "extract_width", "is_FRW": False},
        }
        self.PANEL_MAPPING = self._refine_panel_mapping()
    
    def _refine_panel_mapping(self):
        """
        Find actual block names in Rhino that are regex similar to keys in original mapping
        and inherit the mapping data.
        
        Returns:
            dict: Mapping of actual block names to their inherited mapping data
        """
        all_block_names = rs.BlockNames()
        refined_mapping = {}
        
        print("Original mapping keys: {}".format(list(self._RAW_MAPPING.keys())))
        print("Available block names: {}".format(all_block_names))
        
        for block_name in all_block_names:
            for key in self._RAW_MAPPING.keys():
                try:
                    # Try exact match first, then regex match
                    if block_name == key:
                        refined_mapping[block_name] = self._RAW_MAPPING[key].copy()
                        print("Matched block '{}' to pattern '{}'".format(block_name, key))
                        break
                    elif re.search(key, block_name, re.IGNORECASE):
                        # Get the mapping data
                        mapping_data = self._RAW_MAPPING[key].copy()
                        
                        # Handle dynamic width extraction
                        if mapping_data.get("side_frame_w") == "extract_width":
                            match = re.search(key, block_name, re.IGNORECASE)
                            if match and len(match.groups()) > 0:
                                # Extract the width value from the first capture group
                                width_str = match.group(1)
                                try:
                                    width_value = int(width_str)
                                    mapping_data["side_frame_w"] = width_value
                                    print("Extracted width {} from '{}', calculated side_frame_w: {}".format(
                                        width_value, block_name, mapping_data["side_frame_w"]))
                                except ValueError:
                                    print("Warning: Could not parse width value '{}' from block '{}'".format(width_str, block_name))
                                    mapping_data["side_frame_w"] = 0  # fallback value
                        
                        refined_mapping[block_name] = mapping_data
                        print("Matched block '{}' to pattern '{}'".format(block_name, key))
                        break
                except re.error as e:
                    print("Warning: Invalid regex pattern '{}': {}".format(key, str(e)))
                    # Fallback to simple string matching
                    if key.lower() in block_name.lower():
                        refined_mapping[block_name] = self._RAW_MAPPING[key].copy()
                        print("Matched block '{}' to pattern '{}' (fallback)".format(block_name, key))
                        break
        
        print("Refined mapping contains {} blocks".format(len(refined_mapping)))
        return refined_mapping
    
    def _get_block_instances_safely(self, block_name):
        """
        Safely get block instances with proper error handling.
        
        Args:
            block_name (str): Name of the block to find instances for
            
        Returns:
            list: List of block instances, or empty list if not found
        """
        try:
            # First check if the block definition exists
            doc = Rhino.RhinoDoc.ActiveDoc
            if not doc:
                print("No active Rhino document found")
                return []
                
            # Check if block definition exists
            block_def = doc.InstanceDefinitions.Find(block_name)
            if not block_def:
                print("Block definition '{}' does not exist in the current document".format(block_name))
                return []
                
            # Get instances safely
            instances = rs.BlockInstances(block_name)
            if instances is None:
                return []
            return instances
            
        except Exception as e:
            print("Error getting instances for block '{}': {}".format(block_name, str(e)))
            return []
    
    def _get_block_center(self, block):
        """
        Get the center point of a block safely.
        
        Args:
            block: Rhino block instance
            
        Returns:
            dict: Center point coordinates or None if failed
        """
        try:
            center = RHINO_OBJ_DATA.get_center(block)
            if center is not None:
                # Convert center point to serializable format
                center_dict = {
                    "X": center.X,
                    "Y": center.Y,
                    "Z": center.Z
                }
                return center_dict
            else:
                print("Warning: Could not get center for block {}".format(block))
                return None
        except Exception as e:
            print("Error getting center for block {}: {}".format(block, str(e)))
            return None
    
    def _create_point_from_location(self, location):
        """
        Create a Rhino point from location coordinates.
        
        Args:
            location (dict): Location dictionary with X, Y, Z coordinates
            
        Returns:
            str: GUID of created point, or None if failed
        """
        try:
            point_guid = rs.AddPoint([location["X"], location["Y"], location["Z"]])
            if point_guid:
                print("Created point at ({}, {}, {})".format(location["X"], location["Y"], location["Z"]))
                return point_guid
            else:
                print("Warning: Failed to create point at ({}, {}, {})".format(location["X"], location["Y"], location["Z"]))
                return None
        except Exception as e:
            print("Error creating point at ({}, {}, {}): {}".format(location["X"], location["Y"], location["Z"], str(e)))
            return None
    
    def _group_objects(self, object_guids, group_name):
        """
        Group a list of object GUIDs with a given name.
        
        Args:
            object_guids (list): List of object GUIDs to group
            group_name (str): Name for the group
            
        Returns:
            bool: True if grouping successful, False otherwise
        """
        try:
            if not object_guids:
                print("No objects to group")
                return False
                
            # Filter out None values
            valid_guids = [guid for guid in object_guids if guid is not None]
            
            if not valid_guids:
                print("No valid objects to group")
                return False
            
            # Create group
            group_result = rs.AddGroup(group_name)
            if group_result is None:
                print("Warning: Failed to create group '{}'".format(group_name))
                return False
            
            # Add objects to group
            success = rs.AddObjectsToGroup(valid_guids, group_result)
            if success:
                print("Successfully grouped {} objects into group '{}'".format(len(valid_guids), group_name))
                return True
            else:
                print("Warning: Failed to add objects to group '{}'".format(group_name))
                return False
                
        except Exception as e:
            print("Error grouping objects: {}".format(str(e)))
            return False
    
    def _process_block_instances(self, block_name):
        """
        Process all instances of a specific block and get their locations.
        
        Args:
            block_name (str): Name of the block to process
            
        Returns:
            list: List of center point dictionaries for all instances
        """
        print("Processing block: {}".format(block_name))
        
        # Use safe method to get block instances
        blocks = self._get_block_instances_safely(block_name)
        
        if not blocks:
            print("No instances found for block '{}'".format(block_name))
            return []
            
        print("Found {} instances for block '{}'".format(len(blocks), block_name))
        
        locations = []
        for block in blocks:
            center_dict = self._get_block_center(block)
            if center_dict:
                locations.append(center_dict)
        
        return locations
    
    def _debug_info(self):
        """Print debug information about the current state."""
        print("=" * 50)
        print("SAIF Panel Mapping Debug Info:")
        print("Original mapping patterns: {}".format(list(self._RAW_MAPPING.keys())))
        print("Refined mapping (actual blocks): {}".format(list(self.PANEL_MAPPING.keys())))
        print("=" * 50)
    
    def map_panels(self):
        """
        Main method to map all panels in the current Rhino document.
        Creates points for each panel location and groups them together.
        
        Returns:
            dict: Complete mapping data with locations and created points
        """
        OUT = {}
        all_created_points = []
        
        # Get all available block definitions in the document
        doc = Rhino.RhinoDoc.ActiveDoc
        if not doc:
            print("No active Rhino document found")
            return OUT
        
        # Debug: Show what we're working with
        self._debug_info()
        
        # Load existing recorded data to decide which blocks should create points
        recorded_data = DATA_FILE.get_data("SAIF_panel_mapping") or {}
        print("Recorded blocks available: {}".format(list(recorded_data.keys())))

        # Process all blocks in the refined panel mapping
        for key in self.PANEL_MAPPING.keys():
            locations = self._process_block_instances(key)
            
            # Only create points if this block was previously recorded
            should_create_points = key in recorded_data
            if not should_create_points:
                print("Skipping point creation for unrecorded block '{}'".format(key))

            # Create points for each location
            created_points = []
            if should_create_points:
                for location in locations:
                    point_guid = self._create_point_from_location(location)
                    if point_guid:
                        # Store GUIDs as strings to ensure JSON serializability
                        created_points.append(str(point_guid))
                        all_created_points.append(str(point_guid))
            
            OUT[key] = {
                "mapping_data": self.PANEL_MAPPING[key],
                "locations": locations,
                "created_points": created_points
            }
        
        # Group all created points together
        if all_created_points:
            group_success = self._group_objects(all_created_points, "SAIF_Panel_Locations")
            if group_success:
                print("Successfully created and grouped {} points for SAIF panel locations".format(len(all_created_points)))
            else:
                print("Warning: Failed to group created points")
        else:
            print("No points were created - no panel locations found")
        
        print("Final output contains {} mapped blocks".format(len(OUT)))
        print(OUT)
        
        return OUT
    
    def save_mapping_data(self, mapping_data):
        """
        Save the mapping data to the data file.
        
        Args:
            mapping_data (dict): The mapping data to save
        """
        def _json_safe(value):
            # Convert values to JSON-serializable equivalents
            try:
                import System
            except:
                System = None
            # Py2/Py3 compatibility for basestring
            # basestring is guaranteed to exist from module-level shim
            
            # Handle .NET Guid or Rhino GUIDs by converting to string
            try:
                if System is not None and isinstance(value, System.Guid):
                    return str(value)
            except:
                pass
            
            # Basic primitives pass through
            if isinstance(value, (int, float, bool)) or value is None:
                return value
            if isinstance(value, basestring):
                return value
            
            # Lists/Tuples
            if isinstance(value, (list, tuple)):
                return [_json_safe(v) for v in value]
            
            # Dicts
            if isinstance(value, dict):
                iter_method = getattr(value, 'iteritems', None)
                iterator = iter_method() if iter_method is not None else value.items()
                return dict([(str(k), _json_safe(v)) for k, v in iterator])
            
            # Fallback to string representation
            return str(value)
        
        safe_data = _json_safe(mapping_data)
        DATA_FILE.set_data(safe_data, "SAIF_panel_mapping")


# Global instance for easy access
mapper = SAIFPanelMapper()


@LOG.log(__file__, __title__)
@ERROR_HANDLE.try_catch_error()
def SAIF_panel_mapping():
    """
    Main function to execute SAIF panel mapping.
    This is the entry point for the button click.
    """
    mapping_data = mapper.map_panels()
    mapper.save_mapping_data(mapping_data)


if __name__ == "__main__":
    SAIF_panel_mapping()
