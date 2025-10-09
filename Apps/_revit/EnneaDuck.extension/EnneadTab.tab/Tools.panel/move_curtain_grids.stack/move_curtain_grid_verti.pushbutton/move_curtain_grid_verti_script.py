#!/usr/bin/python
# -*- coding: utf-8 -*-



__doc__ = "Precision curtain grid alignment tool that automatically snaps vertical curtain grids to intersecting detail lines and datum grids. Perfect for quickly coordinating facade layouts with architectural planning grids without tedious manual adjustments. Run this command in a plan view for best results."
__title__ = "Align V. Curtain Grid To Detail Lines/Grids(Plan)"
__youtube__ = "https://youtu.be/iiAy-Gxl5ZU"
__tip__ = True
# from pyrevit import forms #
import proDUCKtion # pyright: ignore 
proDUCKtion.validify()
from EnneadTab import NOTIFICATION
from pyrevit import script #

from EnneadTab.REVIT import REVIT_APPLICATION, REVIT_GEOMETRY
from EnneadTab import ERROR_HANDLE,LOG

from Autodesk.Revit import DB # pyright: ignore 
from Autodesk.Revit import UI # pyright: ignore
uidoc = REVIT_APPLICATION.get_uidoc()
doc = REVIT_APPLICATION.get_doc()



def process_wall(wall, crvs):
    """Process a wall and align its vertical curtain grids to intersecting elements"""
    print("Processing wall: {}".format(output.linkify(wall.Id)))
    wall_crv = wall.Location.Curve
    intersect_pts = []

    # Find intersection points between wall and reference elements
    for crv in crvs:
        if isinstance(crv, DB.Grid):
            abstract_crv = crv.Curve
        elif isinstance(crv, DB.DetailLine):
            abstract_crv = crv.GeometryCurve
        else:
            continue

        # Use EnneadTab's geometry utilities to find intersections
        res = REVIT_GEOMETRY.get_intersect_pt_from_crvs(abstract_crv, wall_crv)
        if res:
            intersect_pts.append(res)

    # Add wall endpoints as potential alignment targets
    intersect_pts.append(wall_crv.GetEndPoint(0))
    intersect_pts.append(wall_crv.GetEndPoint(1))

    # Process each vertical grid line
    for grid in [doc.GetElement(x) for x in wall.CurtainGrid.GetVGridLineIds()]:
        pt = grid.FullCurve.GetEndPoint(0)
        projected_pt = DB.XYZ(pt.X, pt.Y, 0)
        
        # Find the nearest intersection point using EnneadTab utilities
        target_pt = REVIT_GEOMETRY.nearest_pt_from_pts(projected_pt, intersect_pts)
        
        # Calculate movement vector and move the grid element
        movement_vector = target_pt - pt
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
        crvs = uidoc.Selection.PickObjects(UI.Selection.ObjectType.Subelement, "Pick detail crvs or grids that will intersect your wall")
    except:
        NOTIFICATION.messenger("NO intersection content picked.")
        return
    if len(crvs) == 0:
        NOTIFICATION.messenger("No detail crvs or grids selected.")
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
    
