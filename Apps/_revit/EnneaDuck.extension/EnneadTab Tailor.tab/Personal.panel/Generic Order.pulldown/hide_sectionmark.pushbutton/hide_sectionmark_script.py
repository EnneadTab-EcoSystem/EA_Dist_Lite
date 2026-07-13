#!/usr/bin/python
# -*- coding: utf-8 -*-



__doc__ = """Hide wall section marks that face the wrong way in each selected elevation.

A section mark whose Orientation does not match the Orientation of the
elevation it appears in is hidden in that view, so you no longer see
section marks coming from the far side of the building. This solves the
problem without touching view depth. Views and sections with no
Orientation value assigned stay visible.

Usage:
1. Run the button and pick the elevation views to process
2. Review the hidden section marks listed in the output window"""
__title__ = "Hide Section in Elevation by Orientation"

from pyrevit import forms #
from pyrevit import script #
# from pyrevit import revit #

import proDUCKtion # pyright: ignore 
proDUCKtion.validify()

from Autodesk.Revit import DB # pyright: ignore 
# from Autodesk.Revit import UI # pyright: ignore
doc = __revit__.ActiveUIDocument.Document # pyright: ignore


ORIENTATION_PARA = "Orientation"

def process_view(view):
    print("\n##############")
    print("Processing view [{}]".format(view.Name))
    if view.LookupParameter(ORIENTATION_PARA) is None:
        print("No oritation parameter yet, skipping")
        return
    my_orientation = view.LookupParameter(ORIENTATION_PARA).AsString()
    if my_orientation == "" or not view.LookupParameter(ORIENTATION_PARA).HasValue:
        print("No oritation assigned to this view, skipping")
        return

    everything = DB.FilteredElementCollector(doc, view.Id).WhereElementIsNotElementType().ToElements()
    sections = filter(lambda x: x.Category is not None and x.Category.Name == "Views", everything)
    def is_same_orientation(section):
        #print section.Name
        #print doc.GetElement(section.Id).ViewType
        if section.LookupParameter(ORIENTATION_PARA).AsString() == "" or not section.LookupParameter(ORIENTATION_PARA).HasValue:
            return True# will keep unassigned view, so pretent no assigned view the same orienation as my view
        if section.Id == view.Id:
            return False
        if section.LookupParameter(ORIENTATION_PARA).AsString() == my_orientation:
            return True
        return False
    sections = filter(lambda x: not(is_same_orientation(x)), sections)

    count = len(sections)
    if count > 0:
        view.HideElements (ARCHI_UTILITY.list_to_system_list([x.Id for x in sections]))
        for section in sections:
            print("\tHiding [{}]".format(section.Name))



def hide_section_in_elev_by_orientation():
    views = forms.select_views(multiple = True,
                                title = "Views to process. Orientation para name = {}".format(ORIENTATION_PARA))
    if not views:
        return




    t = DB.Transaction(doc, __title__)
    t.Start()
    map(process_view, views)
    t.Commit()


################## main code below #####################
output = script.get_output()
output.close_others()


if __name__ == "__main__":
    hide_section_in_elev_by_orientation()
    
