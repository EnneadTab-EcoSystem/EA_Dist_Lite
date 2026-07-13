#!/usr/bin/python
# -*- coding: utf-8 -*-

__doc__ = """Launch the Keynote Exporter app for editing the keynote spreadsheet outside Revit.

Opens the standalone Keynote Exporter, which reads and writes the older Excel keynote
format still used on some projects. Revit stays open and your model is untouched."""
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







