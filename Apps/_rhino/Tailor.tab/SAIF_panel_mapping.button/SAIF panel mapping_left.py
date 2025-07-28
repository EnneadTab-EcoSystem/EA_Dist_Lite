
__title__ = "SaifPanelMapping"
__doc__ = "This button does SaifPanelMapping when left click"


from EnneadTab import ERROR_HANDLE, LOG, DATA_FILE
from EnneadTab.RHINO import RHINO_OBJ_DATA
import rhinoscriptsyntax as rs

panel_mapping = {
    "Vertical 400 01_SYSTEM_01": {"family_name": "tower_main", "side_frame_w": "450"},
    "Vertical 700 01_SYSTEM_01": {"family_name": "tower_main", "side_frame_w": "750"},
    "Vertical 1000 01_SYSTEM_01": {"family_name": "tower_main", "side_frame_w": "1050"},
    "FR WIDOW_SYSTEM_01": {"family_name": "tower_main", "side_frame_w": "450", "is_FRW": True},

}

@LOG.log(__file__, __title__)
@ERROR_HANDLE.try_catch_error()
def SAIF_panel_mapping():
    OUT = {}
    # get all the blocks instance of the keys in panel_mapping
    for key in panel_mapping.keys():
        blocks = rs.BlockInstances(key)
        for block in blocks:
            OUT[block] = {"mapping_data": panel_mapping[key],
                          "locations": []}
            for location in RHINO_OBJ_DATA.get_center(block):
                OUT[block]["locations"].append(location)

    print(OUT)

    DATA_FILE.set_data("SAIF_panel_mapping", OUT)



    
if __name__ == "__main__":
    SAIF_panel_mapping()
