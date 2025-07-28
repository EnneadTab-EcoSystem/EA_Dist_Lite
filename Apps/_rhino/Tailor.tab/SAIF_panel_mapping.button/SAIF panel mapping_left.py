
__title__ = "SaifPanelMapping"
__doc__ = "This button does SaifPanelMapping when left click"


from EnneadTab import ERROR_HANDLE, LOG, DATA_FILE
from EnneadTab.RHINO import RHINO_OBJ_DATA
import rhinoscriptsyntax as rs
import scriptcontext as sc
import Rhino
import re


class SAIFPanelMapper:
    """
    A class to handle SAIF panel mapping functionality.
    Finds actual block names in Rhino that match regex patterns and inherits mapping data.
    """
    
    def __init__(self):
        """Initialize the mapper with raw mapping data."""
        self._RAW_MAPPING = {
            "Vertical 400 01_SYSTEM_01": {"family_name": "tower_main", "side_frame_w": 450, "is_FRW": False},
            "Vertical 700 01_SYSTEM_01": {"family_name": "tower_main", "side_frame_w": 650, "is_FRW": False},
            "Vertical 1000 01_SYSTEM_01": {"family_name": "tower_main", "side_frame_w": 850, "is_FRW": False},
            "FR WIDOW_SYSTEM_01": {"family_name": "tower_main", "side_frame_w": 450, "is_FRW": True},
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
                    if block_name == key or re.search(key, block_name, re.IGNORECASE):
                        refined_mapping[block_name] = self._RAW_MAPPING[key].copy()  # Make a copy to avoid reference issues
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
        
        Returns:
            dict: Complete mapping data with locations
        """
        OUT = {}
        
        # Get all available block definitions in the document
        doc = Rhino.RhinoDoc.ActiveDoc
        if not doc:
            print("No active Rhino document found")
            return OUT
        
        # Debug: Show what we're working with
        self._debug_info()
        
        # Process all blocks in the refined panel mapping
        for key in self.PANEL_MAPPING.keys():
            locations = self._process_block_instances(key)
            
            OUT[key] = {
                "mapping_data": self.PANEL_MAPPING[key],
                "locations": locations,
                "unit": "m"
            }
        
        print("Final output contains {} mapped blocks".format(len(OUT)))
        print(OUT)
        
        return OUT
    
    def save_mapping_data(self, mapping_data):
        """
        Save the mapping data to the data file.
        
        Args:
            mapping_data (dict): The mapping data to save
        """
        DATA_FILE.set_data(mapping_data, "SAIF_panel_mapping")


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
