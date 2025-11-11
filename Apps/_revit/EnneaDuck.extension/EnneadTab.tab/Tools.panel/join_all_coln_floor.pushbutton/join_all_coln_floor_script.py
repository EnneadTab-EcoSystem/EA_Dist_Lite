#!/usr/bin/python
# -*- coding: utf-8 -*-

__doc__ = """Automates the tedious task of joining vertical and horizontal elements throughout your model.\n\nThis utility now allows you to select which categories to join:\n- Horizontal elements: multi-pick from Floor, Ceiling\n- Vertical elements: multi-pick from Column, Structural Column\n\nThe tool will join all selected vertical elements to all selected horizontal elements, and provide a detailed completion report of successful and failed joins."""
__title__ = "Join Selected\nElements"

import proDUCKtion # pyright: ignore 
proDUCKtion.validify()

from EnneadTab import ERROR_HANDLE, LOG, NOTIFICATION
from EnneadTab.REVIT import REVIT_APPLICATION
from Autodesk.Revit import DB # pyright: ignore 
from pyrevit import forms

UIDOC = REVIT_APPLICATION.get_uidoc()
DOC = REVIT_APPLICATION.get_doc()


@LOG.log(__file__, __title__)
@ERROR_HANDLE.try_catch_error()
def join_all_coln_floor(doc):
    # Define join pairs (better ordering and naming)
    join_pairs = sorted([
        ("Architectural Column + Architectural Floor", DB.BuiltInCategory.OST_Columns, DB.BuiltInCategory.OST_Floors),
        ("Architectural Wall + Architectural Floor", DB.BuiltInCategory.OST_Walls, DB.BuiltInCategory.OST_Floors),
        ("Architectural Column + Ceiling", DB.BuiltInCategory.OST_Columns, DB.BuiltInCategory.OST_Ceilings),
        ("Architectural Wall + Ceiling", DB.BuiltInCategory.OST_Walls, DB.BuiltInCategory.OST_Ceilings),
        ("Structural Column + Architectural Floor", DB.BuiltInCategory.OST_StructuralColumns, DB.BuiltInCategory.OST_Floors),
        ("Structural Beam + Architectural Floor", DB.BuiltInCategory.OST_StructuralFraming, DB.BuiltInCategory.OST_Floors),
        ("Structural Column + Ceiling", DB.BuiltInCategory.OST_StructuralColumns, DB.BuiltInCategory.OST_Ceilings),
        ("Structural Beam + Ceiling", DB.BuiltInCategory.OST_StructuralFraming, DB.BuiltInCategory.OST_Ceilings),
        ("Structural Beam + Architectural Wall", DB.BuiltInCategory.OST_StructuralFraming, DB.BuiltInCategory.OST_Walls),
        ("Structural Beam + Structural Column", DB.BuiltInCategory.OST_StructuralFraming, DB.BuiltInCategory.OST_StructuralColumns),
        ("Structural Beam + Structural Beam", DB.BuiltInCategory.OST_StructuralFraming, DB.BuiltInCategory.OST_StructuralFraming),
        ("Architectural Wall + Architectural Wall", DB.BuiltInCategory.OST_Walls, DB.BuiltInCategory.OST_Walls),
        ("Architectural Floor + Architectural Floor", DB.BuiltInCategory.OST_Floors, DB.BuiltInCategory.OST_Floors),
    ], key=lambda x: x[0])
    pair_names = [x[0] for x in join_pairs]

    selected_pairs = forms.SelectFromList.show(pair_names, multiselect=True, title="Pick element pairs to join")
    if not selected_pairs:
        NOTIFICATION.messenger("No join pairs selected. Aborting.")
        return

    t = DB.Transaction(doc, __title__)
    t.Start()
    join_count = 0
    fail_count = 0

    for pair in join_pairs:
        name, cat1, cat2 = pair
        if name not in selected_pairs:
            continue
        elems1 = list(DB.FilteredElementCollector(doc).OfCategory(cat1).WhereElementIsNotElementType().ToElements())
        elems2 = list(DB.FilteredElementCollector(doc).OfCategory(cat2).WhereElementIsNotElementType().ToElements())
        # Remove duplicates for self-join (e.g., wall+wall or floor+floor)
        if cat1 == cat2:
            elems1 = list({el.Id: el for el in elems1}.values())
            elems2 = elems1
        for e1 in elems1:
            for e2 in elems2:
                # For self-join, skip same element
                if cat1 == cat2 and e1.Id == e2.Id:
                    continue
                try:
                    DB.JoinGeometryUtils.JoinGeometry(doc, e1, e2)
                    join_count += 1
                except Exception as e:
                    fail_count += 1

    NOTIFICATION.messenger("Joined {} pairs, failed {}\nTotal: {}".format(join_count, fail_count, join_count + fail_count))
    t.Commit()



################## main code below #####################
if __name__ == "__main__":
    join_all_coln_floor(DOC)







