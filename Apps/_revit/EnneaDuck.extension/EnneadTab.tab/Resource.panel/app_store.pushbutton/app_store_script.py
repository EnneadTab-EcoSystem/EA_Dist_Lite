#!/usr/bin/python
# -*- coding: utf-8 -*-

__doc__ = """Open the EnneadTab App Store to browse and install extra tools.

Shows the curated catalog of EnneadTab utilities and add-ons, with installing and
updating handled for you. Use it to pick up a tool you do not have yet, or to
refresh one that has a newer version waiting."""
__title__ = "App Store"
__context__ = "zero-doc"

import proDUCKtion # pyright: ignore 
proDUCKtion.validify()

from EnneadTab import ERROR_HANDLE, LOG, EXE
# from EnneadTab.REVIT import REVIT_APPLICATION
from Autodesk.Revit import DB # pyright: ignore 

# UIDOC = REVIT_APPLICATION.get_uidoc()
# DOC = REVIT_APPLICATION.get_doc()


@LOG.log(__file__, __title__)
@ERROR_HANDLE.try_catch_error()
def app_store():
    EXE.try_open_app("AppStore", safe_open=True)


    # t = DB.Transaction(doc, __title__)
    # t.Start()
    # pass
    # t.Commit()



################## main code below #####################
if __name__ == "__main__":
    app_store()







