#!/usr/bin/python
# -*- coding: utf-8 -*-

__doc__ = "PlaceHolder Documentation, To Be Updated."
__title__ = "Monitor Area"


import os
import traceback
import time

import proDUCKtion # pyright: ignore 
proDUCKtion.validify()

from EnneadTab import ERROR_HANDLE, NOTIFICATION, EXE, USER, FOLDER

try:
    import pythoncom
    from win32com.client import DispatchEx, constants
    _HAS_EXCEL_AUTOMATION = True
except Exception:
    _HAS_EXCEL_AUTOMATION = False

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
import department_matrix
import config


def _get_matrix_export_directory():
    username = os.environ.get('USERNAME')
    if not username:
        try:
            username = USER.get_user_name()
        except Exception:
            username = None

    if not username:
        return None

    base_dir = os.path.join(
        "C:\\Users",
        username,
        "DC",
        "ACCDocs",
        "Ennead Architects LLP",
        "2534_NYUL Long Island HQ",
        "Project Files",
        "[EXTERNAL] File Exchange Hub",
        "B-10_Architecture_EA",
        "EA Linked Schedule"
    )

    if os.path.isdir(base_dir):
        return base_dir

    print("Matrix export skipped - directory not found: {}".format(base_dir))
    return None


def _force_excel_resave(filepath):
    if _HAS_EXCEL_AUTOMATION:
        pythoncom.CoInitialize()
        excel = DispatchEx("Excel.Application")
        excel.Visible = False
        excel.DisplayAlerts = False
        try:
            time.sleep(0.25)
            workbook = excel.Workbooks.Open(
                filepath,
                UpdateLinks=constants.xlUpdateLinksNever,
                ReadOnly=False,
                IgnoreReadOnlyRecommended=True
            )
            workbook.Save()
            workbook.Close(SaveChanges=True)
            return True
        except Exception:
            traceback.print_exc()
            return False
        finally:
            excel.Quit()
            pythoncom.CoUninitialize()

    try:
        import clr  # type: ignore
        clr.AddReference("Microsoft.Office.Interop.Excel")
        from Microsoft.Office.Interop import Excel  # type: ignore
        from System.Runtime.InteropServices import Marshal  # type: ignore
    except Exception:
        traceback.print_exc()
        return None

    excel = Excel.ApplicationClass()
    excel.Visible = False
    excel.DisplayAlerts = False
    try:
        time.sleep(0.25)
        workbook = excel.Workbooks.Open(filepath)
        workbook.Save()
        workbook.Close(True)
        return True
    except Exception:
        traceback.print_exc()
        return False
    finally:
        excel.Quit()
        Marshal.ReleaseComObject(excel)


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
    
    excel_export_dir = _get_matrix_export_directory()
    matrix_exports = []
    matrix_failures = []

    if excel_export_dir:
        staging_dir = FOLDER.get_local_dump_folder_folder("MonitorAreaMatrix")
        FOLDER.secure_folder(staging_dir)
        for scheme_name, scheme_data in all_matches.items():
            matches = scheme_data.get('matches', [])
            scheme_areas = revit_data_by_scheme.get(scheme_name, [])
            matrix_data = department_matrix.build_matrix(matches, scheme_areas, color_hierarchy)
            staged_path = department_matrix.write_excel(matrix_data, scheme_name, staging_dir)
            if staged_path:
                wait_attempts = 0
                while not os.path.exists(staged_path) and wait_attempts < 50:
                    time.sleep(0.2)
                    wait_attempts += 1

                if not os.path.exists(staged_path):
                    print("WARNING: Staged matrix not created at {}".format(staged_path))
                    matrix_failures.append(scheme_name)
                    continue

                auto_resave = _force_excel_resave(staged_path)
                if auto_resave:
                    print("Excel auto-resaved: {}".format(staged_path))
                elif auto_resave is False:
                    print("WARNING: Excel auto-resave skipped or failed for {}".format(staged_path))

                final_filename = os.path.basename(staged_path)
                final_path = os.path.join(excel_export_dir, final_filename)
                if os.path.exists(staged_path):
                    try:
                        FOLDER.copy_file(staged_path, final_path)
                    except Exception:
                        print("WARNING: Failed to move staged matrix to {}".format(final_path))
                        final_path = staged_path
                else:
                    print("WARNING: Staged matrix missing at {}".format(staged_path))
                    final_path = staged_path
                matrix_exports.append(final_path)
                print("Department-level matrix exported: {}".format(final_path))
            else:
                matrix_failures.append(scheme_name)
    elif all_matches:
        matrix_failures = list(all_matches.keys())

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

    if excel_export_dir and matrix_exports:
        latest_path = matrix_exports[-1]
        matrix_summary = "\n\nLevel Matrix Export:\n  Saved {} file(s)\n  Latest: {}".format(len(matrix_exports), latest_path)
    elif excel_export_dir and matrix_failures:
        matrix_summary = "\n\nLevel Matrix Export:\n  WARNING: Failed to save for: {}".format(", ".join(matrix_failures))
    else:
        matrix_summary = "\n\nLevel Matrix Export:\n  Target folder unavailable. Skipped."
    
    # Create notification message
    schemes_text = ", ".join(scheme_names) if len(scheme_names) <= 3 else "{} schemes".format(len(scheme_names))
    msg = (
        "Consolidated HTML Report Generated and Opened!\n"
        "File: {file_name}\n"
        "Schemes: {schemes}\n"
        "Fulfilled: {fulfilled}/{total}"
        "{param_summary}"
        "{writeback_summary}"
        "{matrix_summary}"
    ).format(
        file_name=os.path.basename(filepaths[0]) if filepaths else "N/A",
        schemes=schemes_text,
        fulfilled=total_fulfilled,
        total=total_requirements,
        param_summary=param_summary,
        writeback_summary=writeback_summary,
        matrix_summary=matrix_summary
    )
    
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







