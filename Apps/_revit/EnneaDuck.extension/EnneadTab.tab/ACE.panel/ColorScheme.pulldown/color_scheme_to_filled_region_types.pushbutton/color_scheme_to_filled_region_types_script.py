#!/usr/bin/python
# -*- coding: utf-8 -*-

__doc__ = """Turn a color scheme into filled region types so diagrams match your plan colors.

Pick a color scheme and every entry in it becomes a filled region type carrying that
entry's exact color, ready to draw with. Existing types are refreshed rather than
duplicated, so re-running after a color change keeps your diagrams in step with the
plans.

Features:
- Each type is named after its scheme entry so it is easy to find in the type list
- The whole conversion is one undo step

Usage:
1. Run the button and pick the color scheme to convert"""
__title__ = "ColorScheme To\nFilledRegion Types"

import proDUCKtion  # pyright: ignore
proDUCKtion.validify()

from EnneadTab import ERROR_HANDLE, LOG
from EnneadTab.REVIT import REVIT_APPLICATION, REVIT_COLOR_SCHEME, REVIT_SELECTION
from Autodesk.Revit import DB  # pyright: ignore

UIDOC = REVIT_APPLICATION.get_uidoc()
DOC = REVIT_APPLICATION.get_doc()


@LOG.log(__file__, __title__)
@ERROR_HANDLE.try_catch_error()
def color_scheme_to_filled_region_types(doc):
    # Step 1: Let user pick a color scheme
    scheme_name = REVIT_COLOR_SCHEME.pick_color_scheme(doc, title="Pick a color scheme to convert", button_name="Select")
    if not scheme_name:
        print("No color scheme selected. Exiting.")
        return

    color_scheme = REVIT_COLOR_SCHEME.get_color_scheme_by_name(scheme_name, doc)
    if not color_scheme:
        print("Could not find the selected color scheme in the document.")
        return

    # Step 2: For each entry, create/update filled region type
    t = DB.Transaction(doc, __title__)
    t.Start()
    for entry in color_scheme.GetEntries():
        entry_name = entry.GetStringValue()
        color = entry.Color
        region_type_name = "_ColorScheme_{}".format(entry_name)
        # Create or update filled region type
        REVIT_SELECTION.get_filledregion_type(
            doc,
            region_type_name,
            color_if_not_exist=(color.Red, color.Green, color.Blue)
        )
    t.Commit()
    print("Filled region types created/updated for color scheme '{}'!".format(scheme_name))


################## main code below #####################
if __name__ == "__main__":
    color_scheme_to_filled_region_types(DOC)







