#!/usr/bin/python
# -*- coding: utf-8 -*-



__doc__ = """Convert the old text-based area value on every area into a real number.

The old proposed-data text has its SF suffix stripped and is written into
the numeric proposed-data parameter, so the value can be scheduled and
totalled instead of sitting in the model as plain text."""
__title__ = "Text Area --> Area"

# from pyrevit import forms #
from pyrevit import script #


import proDUCKtion # pyright: ignore 
proDUCKtion.validify()
from Autodesk.Revit import DB # pyright: ignore 
# from Autodesk.Revit import UI # pyright: ignore
# uidoc = EnneadTab.REVIT.REVIT_APPLICATION.get_uidoc()
doc = EnneadTab.REVIT.REVIT_APPLICATION.get_doc()
            
@ERROR_HANDLE.try_catch_error()
def text_area_to_area():
    for area in DB.FileredElementCollector(doc).OfCategory(DB.BuiltInCategory.OST_Areas).WhereElementIsNotElementType().ToElements():
        bad_data = area.LookupParameter("Proposed Data_old").AsString().replace("SF", "")
        area.LookupParameter("Proposed Data").Set(float(bad_data))


################## main code below #####################


if __name__ == "__main__":
    output = script.get_output()
    output.close_others()
    text_area_to_area()
    







