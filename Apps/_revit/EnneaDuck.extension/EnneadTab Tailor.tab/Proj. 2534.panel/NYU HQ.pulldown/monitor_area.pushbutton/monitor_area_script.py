#!/usr/bin/python
# -*- coding: utf-8 -*-

__doc__ = "PlaceHolder Documentation, To Be Updated."
__title__ = "Monitor Area"


import os

import proDUCKtion # pyright: ignore 
proDUCKtion.validify()

from EnneadTab import ERROR_HANDLE, EXCEL, NOTIFICATION, EXE
from EnneadTab.REVIT import REVIT_APPLICATION, REVIT_FORMS
from Autodesk.Revit import DB # pyright: ignore 

UIDOC = REVIT_APPLICATION.get_uidoc()
DOC = REVIT_APPLICATION.get_doc()


# Import consolidated modules
from excel_data import get_excel_data
from revit_data import get_revit_area_data_by_scheme
from html_export import HTMLReportGenerator
from color_scheme_updater import update_all_color_schemes
from parameter_updater import update_area_parameters
from excel_writeback import write_design_values_to_test_excel
import config


@ERROR_HANDLE.try_catch_error()
def monitor_area(doc):
    """
    Main function to monitor areas and generate HTML report
    This function is designed to run in Revit environment
    """
    
    # Get data from Excel and Revit
    excel_data, color_hierarchy = get_excel_data()
    
    # Update color schemes from Excel color hierarchy
    update_all_color_schemes(doc, color_hierarchy)
    
    revit_data_by_scheme = get_revit_area_data_by_scheme()

    # Generate HTML reports (one per scheme) and open automatically
    generator = HTMLReportGenerator()
    filepaths, all_matches, all_unmatched = generator.generate_html_report(excel_data, revit_data_by_scheme, color_hierarchy)
    
    # Update Revit area parameters with suggestions
    param_stats = update_area_parameters(doc, all_matches, all_unmatched)
    
    # Write Revit area data to TEST Excel copy (original Excel is NOT changed)
    writeback_stats = write_design_values_to_test_excel(
        excel_data, 
        all_matches, 
        config.EXCEL_FILENAME, 
        config.EXCEL_WORKSHEET
    )
    
    # Open all generated reports
    for filepath in filepaths:
        generator.open_report_in_browser(filepath)
    
    # Calculate total fulfilled across all schemes
    total_fulfilled = 0
    total_requirements = 0
    for scheme_name, scheme_data in all_matches.items():
        matches = scheme_data.get('matches', [])
        total_requirements += len(matches)
        total_fulfilled += sum(1 for m in matches if m['status'] == 'Fulfilled')
    
    # Create notification message with parameter update stats
    param_summary = "\n\nParameter Updates:\n  Matched areas cleared: {}\n  Unmatched areas updated: {}\n  Skipped: {}".format(
        param_stats['matched_cleared'],
        param_stats['unmatched_updated'],
        param_stats['matched_skipped'] + param_stats['unmatched_skipped']
    )
    
    if param_stats['errors']:
        param_summary += "\n  Errors: {}".format(len(param_stats['errors']))
    
    # Add Excel writeback summary
    writeback_summary = "\n\nExcel Writeback (TEST file only):\n  Total cells updated: {}\n  DESIGN Column: {}".format(
        writeback_stats['total_updates'],
        writeback_stats.get('design_column', 'N/A')
    )
    
    test_file = writeback_stats.get('test_file_path', None)
    if test_file:
        writeback_summary += "\n  Test file: {}".format(os.path.basename(test_file))
    
    if writeback_stats.get('error'):
        writeback_summary += "\n  Error: {}".format(writeback_stats['error'])
    
    if len(filepaths) == 1:
        msg = "HTML Report Generated and Opened!\nFile: {}\nScheme: {}\nFulfilled: {}/{}{}{}".format(
            os.path.basename(filepaths[0]), list(all_matches.keys())[0], total_fulfilled, total_requirements, param_summary, writeback_summary)
    else:
        filenames = "\n  - ".join([os.path.basename(f) for f in filepaths])
        msg = "HTML Reports Generated and Opened!\nFiles:\n  - {}\nSchemes: {}\nFulfilled: {}/{}{}{}".format(
            filenames, len(all_matches), total_fulfilled, total_requirements, param_summary, writeback_summary)
    
    NOTIFICATION.messenger(main_text=msg)
    
    # Open NYU_HQ executable
    EXE.try_open_app("NYU_HQ")









################## main code below #####################
if __name__ == "__main__":
    monitor_area(DOC)







