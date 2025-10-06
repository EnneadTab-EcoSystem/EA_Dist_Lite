#!/usr/bin/python
# -*- coding: utf-8 -*-

__doc__ = "Us the Keynote Exporter app to interact with the KeynoteExcel with legacy format."
__title__ = "Open Keynote Exporter"

import proDUCKtion # pyright: ignore 
proDUCKtion.validify()

from EnneadTab import ERROR_HANDLE, LOG, EXE
from EnneadTab.REVIT import REVIT_APPLICATION
from Autodesk.Revit import DB # pyright: ignore 

UIDOC = REVIT_APPLICATION.get_uidoc()
DOC = REVIT_APPLICATION.get_doc()


@LOG.log(__file__, __title__)
@ERROR_HANDLE.try_catch_error()
def open_keynote_exporter(doc):
    
    EXE.try_open_app("KeynoteExporter")



################## main code below #####################
if __name__ == "__main__":
    open_keynote_exporter(DOC)







