#!/usr/bin/python
# -*- coding: utf-8 -*-

__doc__ = "PlaceHolder Documentation, To Be Updated."
__title__ = "Monitor Area"


import os

import proDUCKtion # pyright: ignore 
proDUCKtion.validify()

from EnneadTab import ERROR_HANDLE, EXCEL, NOTIFICATION
from EnneadTab.REVIT import REVIT_APPLICATION, REVIT_FORMS
from Autodesk.Revit import DB # pyright: ignore 

UIDOC = REVIT_APPLICATION.get_uidoc()
DOC = REVIT_APPLICATION.get_doc()


# Import consolidated modules
from excel_data import get_excel_data
from revit_data import get_revit_area_data_by_scheme
from html_export import HTMLReportGenerator


@ERROR_HANDLE.try_catch_error()
def monitor_area(doc):
    """
    Main function to monitor areas and generate HTML report
    This function is designed to run in Revit environment
    """
    
    # Get data from Excel and Revit
    excel_data = get_excel_data()
    revit_data_by_scheme = get_revit_area_data_by_scheme()

    # Generate HTML report and open automatically
    generator = HTMLReportGenerator()
    filepath, all_matches, all_unmatched = generator.generate_html_report(excel_data, revit_data_by_scheme)
    generator.open_report_in_browser(filepath)
    
    # Calculate total fulfilled across all schemes
    total_fulfilled = 0
    total_requirements = 0
    for scheme_name, scheme_data in all_matches.items():
        matches = scheme_data.get('matches', [])
        total_requirements += len(matches)
        total_fulfilled += sum(1 for m in matches if m['status'] == 'Fulfilled')
    
    NOTIFICATION.messenger(main_text="HTML Report Generated and Opened!\nFile: {}\nSchemes: {}\nFulfilled: {}/{}".format(
        os.path.basename(filepath), len(all_matches), total_fulfilled, total_requirements))









################## main code below #####################
if __name__ == "__main__":
    monitor_area(DOC)







