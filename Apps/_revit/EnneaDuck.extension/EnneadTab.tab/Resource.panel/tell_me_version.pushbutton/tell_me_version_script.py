#!/usr/bin/python
# -*- coding: utf-8 -*-

__doc__ = """Show which EnneadTab version you are on and when it last updated successfully.

Worth checking when you file a bug, when you want to confirm a fix has reached
your machine, or when you and a teammate need to be sure you are running the
same build."""
__title__ = "Tell Me\nVersion"
__context__ = "zero-doc"
__tip__ = True
import proDUCKtion # pyright: ignore 
proDUCKtion.validify()

from EnneadTab import ERROR_HANDLE, LOG
from EnneadTab import VERSION_CONTROL
# from EnneadTab.REVIT import REVIT_APPLICATION
from Autodesk.Revit import DB # pyright: ignore 

# UIDOC = REVIT_APPLICATION.get_uidoc()
# DOC = REVIT_APPLICATION.get_doc()


@LOG.log(__file__, __title__)
@ERROR_HANDLE.try_catch_error()
def tell_me_version():
    VERSION_CONTROL.show_last_success_update_time()




################## main code below #####################
if __name__ == "__main__":
    tell_me_version()







