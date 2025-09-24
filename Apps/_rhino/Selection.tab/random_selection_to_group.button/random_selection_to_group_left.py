__title__ = "RandomSelectionToGroup"
__doc__ = """Randomly distributes selected objects into groups.

Features:
- Creates specified number of groups
- Randomly assigns objects to groups
- Useful for applying varied materials/shading
- Maintains object relationships

Usage:
1. Select objects to group
2. Specify number of groups
3. Objects will be randomly distributed"""
__is_popular__ = True
import random
from EnneadTab import ERROR_HANDLE, LOG, NOTIFICATION
from EnneadTab.RHINO import RHINO_OBJ_DATA
import rhinoscriptsyntax as rs

@LOG.log(__file__, __title__)
@ERROR_HANDLE.try_catch_error()
def random_selection_to_group_left():
    ids = rs.SelectedObjects(False, False)
    if not ids: 
        NOTIFICATION.messenger("No objects selected, action cancelled.")
        return
    if len(ids) == 1: 
        NOTIFICATION.messenger("Only one object selected, action cancelled.")
        return
    # Compute bounding box for the entire selection (supporting list of ids)
    corners = rs.BoundingBox(ids)
    if not corners or len(corners) < 7:
        NOTIFICATION.messenger("Could not compute bounding box for selection.")
        return
    bbox_center_pt = (corners[0] + corners[6]) / 2
    X = rs.Distance(corners[0], corners[1])
    Y = rs.Distance(corners[1], corners[2])
    Z = rs.Distance(corners[0], corners[5])
    rough_size = (X + Y + Z) / 3.0
    
    res = rs.StringBox(message = "Seperate selection to how many groups?", default_value = "4", title = "EnneadTab")

    if res is None:
        return

    try:
        group_num = int(res)
    except Exception:
        NOTIFICATION.messenger("Invalid number, action cancelled.")
        return
    if group_num < 2:
        NOTIFICATION.messenger("Need at least 2 groups, action cancelled.")
        return

    percent = int(100 / group_num )

    collection = dict()
    for index in range(group_num):
        collection[index] = [rs.AddTextDot(1 + index, bbox_center_pt + rs.CreateVector([index * rough_size * 0.05,0,0]) )]

    # Safety check to ensure ids is still valid before iteration
    if not ids:
        NOTIFICATION.messenger("Selection became invalid during processing.")
        return

    for el in ids:
        index = random.randint(0, group_num - 1)
        collection[index].append(el)

    for index in range(group_num):
        rs.AddObjectsToGroup(collection[index], rs.AddGroup())


    rs.UnselectObjects(ids)

    for index in range(group_num):
        continue


if __name__ == "__main__":
    random_selection_to_group_left()
