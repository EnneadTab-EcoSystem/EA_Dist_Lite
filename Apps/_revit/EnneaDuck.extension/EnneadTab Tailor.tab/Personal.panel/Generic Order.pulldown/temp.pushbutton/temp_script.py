#!/usr/bin/python
# -*- coding: utf-8 -*-

__doc__ = """Run the in-house scratch button used to try out new Revit automation ideas.

Reserved for quick experiments and workflow checks so that production
tools never have to be used as a testing ground."""
__title__ = "Temp"

import proDUCKtion # pyright: ignore 
proDUCKtion.validify()

from EnneadTab import ERROR_HANDLE, LOG, EXE
from EnneadTab.REVIT import REVIT_APPLICATION, REVIT_FAMILY
from Autodesk.Revit import DB # pyright: ignore 

UIDOC = REVIT_APPLICATION.get_uidoc()
DOC = REVIT_APPLICATION.get_doc()


@LOG.log(__file__, __title__)
@ERROR_HANDLE.try_catch_error()
def temp(doc):
    pass


################## main code below #####################
if __name__ == "__main__":
    temp(DOC)







