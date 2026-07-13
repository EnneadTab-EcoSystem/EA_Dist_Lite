#!/usr/bin/python
# -*- coding: utf-8 -*-

__doc__ = """List every family currently open for editing in this Revit session.

A quick roll call of the open family editors, printed to the output window. Use it
to confirm the whole panel chain is open before running Chained Family Loading.
Nothing in the model is changed."""
__title__ = "Print All Family Name"

import proDUCKtion # pyright: ignore 
proDUCKtion.validify()

from EnneadTab import ERROR_HANDLE, LOG
from EnneadTab.REVIT import REVIT_APPLICATION
from Autodesk.Revit import DB # pyright: ignore 

UIDOC = REVIT_APPLICATION.get_uidoc()
DOC = REVIT_APPLICATION.get_doc()


@LOG.log(__file__, __title__)
@ERROR_HANDLE.try_catch_error()
def print_all_family_name(doc):


    for doc in REVIT_APPLICATION.get_app().Documents:
        if doc.IsFamilyDocument:
            print (doc.Title)


################## main code below #####################
if __name__ == "__main__":
    print_all_family_name(DOC)







