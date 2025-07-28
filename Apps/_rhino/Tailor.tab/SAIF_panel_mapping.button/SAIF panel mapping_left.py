
__title__ = "SaifPanelMapping"
__doc__ = "This button does SaifPanelMapping when left click"


from EnneadTab import ERROR_HANDLE, LOG, DATA_FILE
from EnneadTab.RHINO import RHINO_OBJ_DATA
import rhinoscriptsyntax as rs
import scriptcontext as sc
import Rhino

panel_mapping = {
    "Vertical 400 01_SYSTEM_01": {"family_name": "tower_main", "side_frame_w": "450"},
    "Vertical 700 01_SYSTEM_01": {"family_name": "tower_main", "side_frame_w": "750"},
    "Vertical 1000 01_SYSTEM_01": {"family_name": "tower_main", "side_frame_w": "1050"},
    "FR WIDOW_SYSTEM_01": {"family_name": "tower_main", "side_frame_w": "450", "is_FRW": True},

}

def get_block_instances_safely(block_name):
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

@LOG.log(__file__, __title__)
@ERROR_HANDLE.try_catch_error()
def SAIF_panel_mapping():
    OUT = {}
    
    # Get all available block definitions in the document
    doc = Rhino.RhinoDoc.ActiveDoc
    if not doc:
        print("No active Rhino document found")
        return
        
    available_blocks = []
    for i in range(doc.InstanceDefinitions.Count):
        block_def = doc.InstanceDefinitions[i]
        if block_def:
            available_blocks.append(block_def.Name)
    
    print("Available blocks in document: {}".format(available_blocks))
    
    # get all the blocks instance of the keys in panel_mapping
    for key in panel_mapping.keys():
        print("Processing block: {}".format(key))
        
        # Use safe method to get block instances
        blocks = get_block_instances_safely(key)
        
        if not blocks:
            print("No instances found for block '{}'".format(key))
            continue
            
        print("Found {} instances for block '{}'".format(len(blocks), key))
        
        for block in blocks:
            OUT[block] = {"mapping_data": panel_mapping[key],
                          "locations": []}
            try:
                center = RHINO_OBJ_DATA.get_center(block)
                if center is not None:
                    OUT[block]["locations"].append(center)
                else:
                    print("Warning: Could not get center for block {}".format(block))
            except Exception as e:
                print("Error getting center for block {}: {}".format(block, str(e)))
                OUT[block]["locations"] = []

    print("Final output contains {} mapped blocks".format(len(OUT)))
    print(OUT)

    DATA_FILE.set_data("SAIF_panel_mapping", OUT)



    
if __name__ == "__main__":
    SAIF_panel_mapping()
