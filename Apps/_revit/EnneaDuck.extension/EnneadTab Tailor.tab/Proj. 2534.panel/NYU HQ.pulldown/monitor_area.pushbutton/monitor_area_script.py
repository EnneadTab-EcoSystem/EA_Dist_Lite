#!/usr/bin/python
# -*- coding: utf-8 -*-

__doc__ = "PlaceHolder Documentation, To Be Updated."
__title__ = "Monitor Area"


import os

import proDUCKtion # pyright: ignore 
proDUCKtion.validify()

from EnneadTab import ERROR_HANDLE, EXCEL, NOTIFICATION, EXE, USER
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
from excel_writeback import write_design_values_to_excel
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

    # Generate consolidated HTML report with all schemes and open automatically
    generator = HTMLReportGenerator()
    filepaths, all_matches, all_unmatched = generator.generate_html_report(excel_data, revit_data_by_scheme, color_hierarchy)
    
    # Update Revit area parameters with suggestions
    param_stats = update_area_parameters(doc, all_matches, all_unmatched)
    
    # Ask user if they want to write back to Excel
    write_to_excel = REVIT_FORMS.dialogue(
        title="Excel Writeback",
        main_text="Write Revit area data back to Excel?",
        sub_text="This will update the DESIGN column in the Excel file with actual Revit area values.\n\nFile: {}\n\nNote: Skipping writeback will process faster (just view the report).".format(config.EXCEL_FILENAME),
        options=["Yes, write to Excel", "No, skip writeback (faster)"],
        icon="info"
    )
    
    # Write Revit area data back to original Excel file (only if user agrees)
    if write_to_excel == "Yes, write to Excel":
        writeback_stats = write_design_values_to_excel(
            excel_data, 
            all_matches, 
            config.EXCEL_FILENAME, 
            config.EXCEL_WORKSHEET
        )
    else:
        writeback_stats = {
            'total_updates': 0,
            'design_column': 'N/A',
            'skipped': True
        }
        print("Excel writeback skipped by user")
    
    # Open the consolidated report (single HTML with all schemes)
    if filepaths:
        generator.open_report_in_browser(filepaths[0])
    
    # Calculate total fulfilled across all schemes
    total_fulfilled = 0
    total_requirements = 0
    scheme_names = []
    for scheme_name, scheme_data in all_matches.items():
        matches = scheme_data.get('matches', [])
        total_requirements += len(matches)
        total_fulfilled += sum(1 for m in matches if m['status'] == 'Fulfilled')
        scheme_names.append(scheme_name)
    
    # Create notification message with parameter update stats
    param_summary = "\n\nParameter Updates:\n  Matched areas cleared: {}\n  Target DGSF set: {}\n  Unmatched areas updated: {}\n  Skipped: {}".format(
        param_stats['matched_cleared'],
        param_stats.get('target_dgsf_updated', 0),
        param_stats['unmatched_updated'],
        param_stats['matched_skipped'] + param_stats['unmatched_skipped']
    )
    
    if param_stats['errors']:
        param_summary += "\n  Errors: {}".format(len(param_stats['errors']))
    
    # Add Excel writeback summary
    if writeback_stats.get('skipped'):
        writeback_summary = "\n\nExcel Writeback:\n  Status: Skipped by user"
    else:
        writeback_summary = "\n\nExcel Writeback:\n  Total cells updated: {}\n  DESIGN Column: {}".format(
            writeback_stats['total_updates'],
            writeback_stats.get('design_column', 'N/A')
        )
        
        if writeback_stats.get('error'):
            writeback_summary += "\n  ERROR: Excel file cannot be written because you have it open in another program. Please close it and try again."
            # writeback_summary += "\n  Error: {}".format(writeback_stats['error'])
    
    # Create notification message
    schemes_text = ", ".join(scheme_names) if len(scheme_names) <= 3 else "{} schemes".format(len(scheme_names))
    msg = "Consolidated HTML Report Generated and Opened!\nFile: {}\nSchemes: {}\nFulfilled: {}/{}{}{}".format(
        os.path.basename(filepaths[0]) if filepaths else "N/A", 
        schemes_text, 
        total_fulfilled, 
        total_requirements, 
        param_summary, 
        writeback_summary)
    
    NOTIFICATION.messenger(main_text=msg)
    


    if os.path.exists(r"C:\Users\szhang"):
        try:
            dist_reports_dir = r"C:\Users\szhang\Documents\EnneadTab Ecosystem\EA_Dist\Apps\_revit\EnneaDuck.extension\EnneadTab Tailor.tab\Proj. 2534.panel\NYU HQ.pulldown\monitor_area.pushbutton\reports"
            if not os.path.exists(dist_reports_dir):
                os.makedirs(dist_reports_dir)

            # Copy generated HTML reports
            import shutil
            for filepath in filepaths:
                if not filepath.lower().endswith('.html'):
                    continue
                dst_path = os.path.join(dist_reports_dir, os.path.basename(filepath))
                shutil.copy2(filepath, dst_path)

            # Copy icon asset if present in the source reports folder
            if filepaths:
                src_reports_dir = os.path.dirname(filepaths[0])
                icon_name = 'icon_logo_dark_background.png'
                src_icon = os.path.join(src_reports_dir, icon_name)
                if os.path.exists(src_icon):
                    shutil.copy2(src_icon, os.path.join(dist_reports_dir, icon_name))
        except Exception:
            print ("Failed to copy reports to dist folder due to error: {}".format(traceback.format_exc()))


    # Open NYU_HQ executable
    EXE.try_open_app("NYU_HQ")









################## main code below #####################
if __name__ == "__main__":
    monitor_area(DOC)







