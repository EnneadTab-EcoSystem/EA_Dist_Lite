#!/usr/bin/python
# -*- coding: utf-8 -*-



__doc__ = "Align horizontal curtain grids to intersecting detail lines or level datums. Use in elevation views."
__title__ = "Align H. Curtain Grid To Detail Lines/Levels(Elevation)"
__youtube__ = "https://youtu.be/iiAy-Gxl5ZU"
__tip__ = True
# from pyrevit import forms #
from pyrevit import script #

import proDUCKtion # pyright: ignore 
proDUCKtion.validify()
from EnneadTab.REVIT import REVIT_APPLICATION
from EnneadTab import ERROR_HANDLE, LOG
from EnneadTab import NOTIFICATION

from Autodesk.Revit import DB # pyright: ignore 
from Autodesk.Revit import UI # pyright: ignore
uidoc = REVIT_APPLICATION.get_uidoc()
doc = REVIT_APPLICATION.get_doc()

def nearest_Z_from_zList(my_Z, zList):
    """Find the nearest Z value from a list of Z coordinates"""
    zList.sort(key = lambda x: abs(my_Z - x))
    return zList[0]


def process_wall(wall, crvs):
    """Process a wall and align its horizontal curtain grids to intersecting elements"""
    print("Processing wall: {}".format(output.linkify(wall.Id)))

    intersect_pts_Z = []

    # Collect Z coordinates from reference elements
    for crv in crvs:
        if isinstance(crv, DB.Level):
            # Use level's project elevation as reference
            intersect_pts_Z.append(crv.ProjectElevation)
        elif isinstance(crv, DB.DetailLine):
            # Use detail line's Z coordinate as reference
            abstract_crv = crv.GeometryCurve
            intersect_pts_Z.append(abstract_crv.GetEndPoint(0).Z)

    # Get all horizontal grid Z coordinates for reference
    all_grid_zList = [doc.GetElement(x).FullCurve.GetEndPoint(0).Z for x in wall.CurtainGrid.GetUGridLineIds ()]
    all_grid_zList.sort()

    # Process each horizontal grid line
    for grid in [doc.GetElement(x) for x in wall.CurtainGrid.GetUGridLineIds ()]:
        pt_Z = grid.FullCurve.GetEndPoint(0).Z
        
        # Find the nearest target Z coordinate
        target_pt_Z = nearest_Z_from_zList(pt_Z, intersect_pts_Z)
        
        # Calculate movement vector (only Z direction for horizontal grids)
        movement_vector = DB.XYZ(0, 0, target_pt_Z - pt_Z)
        
        # Move the grid element
        DB.ElementTransformUtils.MoveElement(doc, grid.Id, movement_vector)




@LOG.log(__file__, __title__)
@ERROR_HANDLE.try_catch_error()
def move_curtain_grid():

    walls = uidoc.Selection.PickObjects(UI.Selection.ObjectType.Element, "Pick walls")
    walls = [doc.GetElement(x) for x in walls]
    walls = [x for x in walls if isinstance(x, DB.Wall)]
    if len(walls) == 0:
        NOTIFICATION.messenger("No walls selected.")
        return

    try:
        crvs = uidoc.Selection.PickObjects(UI.Selection.ObjectType.Subelement, "Pick detail crvs or levels that will intersect your wall")
    except:
        NOTIFICATION.messenger("NO intersection content picked.")
        return
    if len(crvs) == 0:
        NOTIFICATION.messenger("No detail crvs or levels selected.")
        return

    crvs = [doc.GetElement(x) for x in crvs]



    t = DB.Transaction(doc, __title__)
    t.Start()

    map(lambda x: process_wall(x, crvs), walls)
    t.Commit()


################## main code below #####################
output = script.get_output()
output.close_others()


if __name__ == "__main__":
    move_curtain_grid()
    
