#!/usr/bin/python
# -*- coding: utf-8 -*-



__doc__ = "For selected views, update the Title on Sheet by replacing phase codes PH1 through PH5 with their Lenox Hill milestone names such as Existing and Milestone 1-3. Pick views from the current selection or a list."
__title__ = "Rename Views"

from pyrevit import forms #
from pyrevit import script #


from EnneadTab import ERROR_HANDLE
from EnneadTab.REVIT import REVIT_APPLICATION
from Autodesk.Revit import DB # pyright: ignore 
# from Autodesk.Revit import UI # pyright: ignore
# uidoc = EnneadTab.REVIT.REVIT_APPLICATION.get_uidoc()
doc = REVIT_APPLICATION.get_doc()

@ERROR_HANDLE.try_catch_error()
def surfix_views():
    pass

    t = DB.Transaction(doc, __title__)
    t.Start()
    views = forms.select_views(use_selection=True)
    for view in views:
        title_para_id = DB.BuiltInParameter.VIEW_DESCRIPTION
        original_title = view.Parameter[title_para_id].AsString()
        
        new_title = original_title.replace("PH1", "Existing")\
                            .replace("PH2", "Milestone 1")\
                            .replace("PH3", "Milestone 2")\
                            .replace("PH4", "Milestone 2.5")\
                            .replace("PH5", "Milestone 3")

        view.Parameter[title_para_id].Set(new_title)

        
    t.Commit()



################## main code below #####################


if __name__ == "__main__":
    output = script.get_output()
    output.close_others()
    surfix_views()
    







