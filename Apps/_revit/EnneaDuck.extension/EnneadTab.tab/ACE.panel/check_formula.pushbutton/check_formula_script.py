#!/usr/bin/python
# -*- coding: utf-8 -*-



__doc__ = """Reveal the hidden formulas in a spreadsheet before you trust its numbers.

A cell that looks like a plain number may be a formula pointing somewhere else. This
lists every formula in the worksheet you pick and marks those cells with a dashed
border in a local copy, so you can see at a glance which numbers are calculated and
which were typed. Worth doing before importing consultant data into Revit.

Features:
- Your original spreadsheet is not modified; the marked-up copy is a separate file
- Every formula is printed to the output window

Usage:
1. Run the button and pick the Excel file
2. Pick the worksheet to inspect"""
__title__ = "Inspect Excel\nFormula"
__tip__ = True
__is_popular__ = True
from pyrevit import forms #
from pyrevit import script #

import proDUCKtion # pyright: ignore 
proDUCKtion.validify()
from EnneadTab import ERROR_HANDLE, EXCEL, NOTIFICATION, LOG
from EnneadTab.REVIT import REVIT_APPLICATION
from Autodesk.Revit import DB # pyright: ignore 

doc = REVIT_APPLICATION.get_doc()

@LOG.log(__file__, __title__)
@ERROR_HANDLE.try_catch_error()
def check_formula():

    excel = forms.pick_excel_file()
    if not excel:
        return
    # if excel.endswith(".xlsx"):
    #     NOTIFICATION.messenger("Please saveas .xls")
    sheets = EXCEL.get_all_worksheets(excel)
    sheet = forms.SelectFromList.show(sheets, button_name="Select WorkSheet", multiselect=False, title="Which worksheet to check??")
    EXCEL.check_formula(excel, sheet)
    pass


    NOTIFICATION.messenger("Done! All formula printed!\nAll formula cell are highlighted in dash border in a local copy.")


################## main code below #####################


if __name__ == "__main__":
    output = script.get_output()
    output.close_others()
    check_formula()
    







