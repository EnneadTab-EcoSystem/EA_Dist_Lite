#!/usr/bin/python
# -*- coding: utf-8 -*-


__doc__ = """Prime the room occupancy override parameter on every room in the model.

Rooms whose manual occupancy value is still unset are marked as having no
manual override, so the life safety count falls back to the area-per-person
rule instead of reading a stale zero. The whole pass is one undo step."""
__title__ = "Transfer Old Room Data"

# from pyrevit import forms #
from pyrevit import script
# from pyrevit import revit #
# 

import proDUCKtion # pyright: ignore 
proDUCKtion.validify()
from Autodesk.Revit import DB # pyright: ignore  
# from Autodesk.Revit import UI # pyright: ignore
doc = __revit__.ActiveUIDocument.Document # pyright: ignore


def transfer_old_room_data():
    pass
    t = DB.Transaction(doc, __title__)
    t.Start()
    all_rooms = DB.FilteredElementCollector(doc).OfCategory(
        DB.BuiltInCategory.OST_Rooms).WhereElementIsNotElementType().ToElements()

    for room in all_rooms:

        # make sure this parameter has at least 0.
        # old_para = room.LookupParameter("Rooms_$LS_Occupancy Manual")
        new_para = room.LookupParameter("Rooms_Occupancy Manual")
        if new_para.AsInteger() == 0:
           
            new_para.Set(-1)

    t.Commit()


################## main code below #####################
output = script.get_output()
output.close_others()


if __name__ == "__main__":
    transfer_old_room_data()
