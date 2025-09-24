
__title__ = "2425ReplaceBlocks"
__doc__ = """Block Replacement Tool for 2425 Project

Replaces blocks between Twinmotion and Enscape versions based on Excel mapping data.
Features:
- Supports bidirectional block replacement (Twinmotion ↔ Enscape)
- Uses Excel mapping file for block name relationships
- Processes entire document with progress tracking
- Maintains block transformations and properties
- Provides user selection for replacement direction
- Automatically redraws viewport after replacement

Replacement Options:
1. Twinmotion block → Enscape block
2. Enscape block → Twinmotion block

Excel Mapping:
- Reads from 'enscape_twinmotion_block_mapping.xlsx'
- Uses 'EnneadTab Helper' worksheet
- Maps block names in columns A and B
- Supports multiple block mappings

Workflow:
1. User selects replacement direction
2. Reads block mapping from Excel file
3. Iterates through mapping data
4. Replaces blocks using RHINO_BLOCK utility
5. Redraws viewport to show changes

Usage:
- Select replacement direction when prompted
- Tool processes all mapped blocks automatically
- Maintains block positions and transformations
- Provides completion feedback"""

import rhinoscriptsyntax as rs
from EnneadTab import ERROR_HANDLE, LOG, EXCEL
from EnneadTab.RHINO import RHINO_BLOCK
@LOG.log(__file__, __title__)
@ERROR_HANDLE.try_catch_error()
def replace_blocks():
    options = ["Twinmotion block --> Enscape block",
               "Enscape block --> Twinmotion block"]
    res = rs.ListBox(options, "How to handle block replacement?", "Select option")
    if res == options[0]:
        normal_direction = False
    elif res == options[1]:
        normal_direction = True
    else:
        return
        
    data = EXCEL.read_data_from_excel("J:\\2425\\0_3D\\03_Enscape\\enscape_twinmotion_block_mapping.xlsx",
                                            return_dict=False,
                                            worksheet="EnneadTab Helper")
    data = data[1:]
    for row in data:
        if normal_direction:
            old_block = row[0].get("value") # getting enscape block
            new_block = row[1].get("value") # getting twinmotion block
        else:
            old_block = row[1].get("value") # getting twinmotion block
            new_block = row[0].get("value") # getting enscape block
        RHINO_BLOCK.replace_block(old_block, new_block)
    rs.Redraw()
    
if __name__ == "__main__":
    replace_blocks()
