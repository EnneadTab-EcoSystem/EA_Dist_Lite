#!/usr/bin/python
# -*- coding: utf-8 -*-

"""
Export logic for NYU HQ Auto Export
Handles folder structure creation and export operations
"""

import os
from datetime import datetime
from Autodesk.Revit import DB # pyright: ignore
import System # pyright: ignore

# =============================================================================
# GLOBAL CONSTANTS - CONFIGURATION
# =============================================================================

# Global output path for auto-published files
import os
USERNAME = os.environ.get("USERNAME", "unknown")
OUTPUT_BASE_PATH = os.path.join(
    r"C:\Users", USERNAME, "DC", "ACCDocs", "Ennead Architects LLP",
    "2534_NYUL Long Island HQ", "Project Files",
    "[EXTERNAL] File Exchange Hub", "B-10_Architecture_EA", "EA Auto Publish"
)

# Parameter name to filter sheets for export (sheets with non-empty value will be exported)
SHEET_FILTER_PARAMETER = "Sheet_$Issue_AutoPublish"

# DWG export setting name
DWG_SETTING_NAME = "to NYU dwg"

# PDF color parameter name
PDF_COLOR_PARAMETER = "Print_In_Color"


# Subfolder names
SUBFOLDERS = ["pdf", "dwg", "jpg"]


def get_weekly_folder_path():
    """Get the path for this week's export folder (yyyy-mm-dd format)
    
    Returns:
        str: Full path to weekly folder (e.g., .../2025-10-21)
    """
    date_stamp = datetime.now().strftime("%Y-%m-%d")
    weekly_folder = os.path.join(OUTPUT_BASE_PATH, date_stamp)
    return weekly_folder


def get_pim_number(doc):
    """Extract PIM_Number from project info
    
    Args:
        doc: Revit Document object
    
    Returns:
        str: PIM_Number value or empty string if not found
    """
    try:
        # Ensure we have a Document object, not UIDocumentFile
        if hasattr(doc, 'Document'):
            doc = doc.Document
            
        # Get project info
        project_info = doc.ProjectInformation
        if project_info:
            pim_param = project_info.LookupParameter("PIM_Number")
            if pim_param and pim_param.AsString():
                pim_value = pim_param.AsString().strip()
                print("Found PIM_Number: '{}'".format(pim_value))
                return pim_value
        print("PIM_Number not found in project info")
        return ""
    except Exception as e:
        print("Error extracting PIM_Number: {}".format(e))
        return ""


def get_sheets_to_export(doc, heartbeat_callback=None):
    """Get sheets that have the filter parameter with non-empty value
    
    Args:
        doc: Revit Document object
        heartbeat_callback: Optional function to call for logging progress
    
    Returns:
        list: List of ViewSheet objects to export
    """
    sheets_to_export = []
    
    # Ensure we have a Document object, not UIDocumentFile
    if hasattr(doc, 'Document'):
        doc = doc.Document
    
    # Get all sheets in the document
    sheet_collector = DB.FilteredElementCollector(doc).OfClass(DB.ViewSheet)
    all_sheets = list(sheet_collector)
    
    print("Found {} total sheets in document".format(len(all_sheets)))
    
    # Debug document info
    print("Document info:")
    print("  Title: '{}'".format(doc.Title))
    print("  IsWorkshared: {}".format(doc.IsWorkshared))
    
    # List all sheets for debugging
    print("All sheets in document:")
    for i, sheet in enumerate(all_sheets[:10]):  # Show first 10 sheets
        print("  {}. Sheet: '{}' (Number: '{}')".format(i+1, sheet.Name, sheet.SheetNumber))
    
    # Log to heartbeat for debugging
    if heartbeat_callback:
        heartbeat_callback("DEBUG", "Found {} total sheets in document".format(len(all_sheets)))
        heartbeat_callback("DEBUG", "Document title: {}".format(doc.Title))
        for i, sheet in enumerate(all_sheets[:5]):  # Show first 5 sheets in heartbeat
            heartbeat_callback("DEBUG", "Sheet {}: '{}' (Number: '{}')".format(i+1, sheet.Name, sheet.SheetNumber))
    
    # Filter sheets by parameter
    print("Checking sheets for parameter '{}':".format(SHEET_FILTER_PARAMETER))
    
    # TEMPORARY: Export all sheets for testing (remove this when parameter values are set)
    print("TEMPORARY: Exporting all sheets for testing purposes")
    sheets_to_export = all_sheets[:5]  # Export first 5 sheets for testing
    print("Found {} sheets to export (testing mode)".format(len(sheets_to_export)))
    return sheets_to_export
    
    # Original filtering logic (commented out for testing)
    for sheet in all_sheets:
        try:
            # Get the parameter value
            param = sheet.LookupParameter(SHEET_FILTER_PARAMETER)
            if param:
                # Debug parameter info
                print("  Sheet '{}': parameter exists".format(sheet.Name))
                print("    Parameter type: {}".format(param.StorageType))
                print("    Parameter definition: {}".format(param.Definition.Name))
                
                # Try different ways to read the value
                if param.StorageType == DB.StorageType.String:
                    param_value = param.AsString()
                    print("    String value: '{}'".format(param_value))
                elif param.StorageType == DB.StorageType.Integer:
                    param_value = param.AsInteger()
                    print("    Integer value: {}".format(param_value))
                elif param.StorageType == DB.StorageType.Double:
                    param_value = param.AsDouble()
                    print("    Double value: {}".format(param_value))
                elif param.StorageType == DB.StorageType.ElementId:
                    param_value = param.AsElementId()
                    print("    ElementId value: {}".format(param_value))
                else:
                    param_value = param.AsString()
                    print("    Default string value: '{}'".format(param_value))
                
                # Check if parameter has any meaningful value
                # Any non-empty value should be treated as True for export
                has_value = False
                if param.StorageType == DB.StorageType.String:
                    # String: any non-empty string (including spaces, symbols, etc.)
                    # But exclude 'None' string which represents empty values
                    has_value = (param_value and 
                               param_value.strip() != "" and 
                               param_value.strip().lower() != "none")
                elif param.StorageType == DB.StorageType.Integer:
                    # Integer: any non-zero value
                    has_value = param_value != 0
                elif param.StorageType == DB.StorageType.Double:
                    # Double: any non-zero value
                    has_value = param_value != 0.0
                elif param.StorageType == DB.StorageType.ElementId:
                    # ElementId: any valid element ID
                    has_value = param_value and param_value.IntegerValue != -1
                else:
                    # Default: any non-empty value, but exclude 'None'
                    has_value = (param_value and 
                               str(param_value).strip() != "" and 
                               str(param_value).strip().lower() != "none")
                
                if has_value:
                    sheets_to_export.append(sheet)
                    print("    -> MARKED FOR EXPORT (has value: '{}')".format(param_value))
                    if heartbeat_callback:
                        heartbeat_callback("DEBUG", "Sheet '{}' MARKED FOR EXPORT (value: '{}')".format(sheet.Name, param_value))
                else:
                    print("    -> SKIPPED (no meaningful value)")
                    if heartbeat_callback:
                        heartbeat_callback("DEBUG", "Sheet '{}' SKIPPED (no meaningful value: '{}')".format(sheet.Name, param_value))
            else:
                print("  Sheet '{}': parameter '{}' not found".format(sheet.Name, SHEET_FILTER_PARAMETER))
        except Exception as e:
            print("  Sheet '{}': ERROR - {}".format(sheet.Name, e))
    
    print("Found {} sheets to export".format(len(sheets_to_export)))
    return sheets_to_export


def create_export_folders():
    """Create the weekly folder structure with pdf, dwg, jpg subfolders
    
    Returns:
        dict: Dictionary with paths for each export type
            {"weekly": "path/to/2025-10-21",
             "pdf": "path/to/2025-10-21/pdf",
             "dwg": "path/to/2025-10-21/dwg",
             "jpg": "path/to/2025-10-21/jpg"}
    """
    weekly_folder = get_weekly_folder_path()
    
    # Create weekly folder if it doesn't exist
    if not os.path.exists(weekly_folder):
        os.makedirs(weekly_folder)
        print("Created weekly folder: {}".format(weekly_folder))
    else:
        print("Weekly folder already exists: {}".format(weekly_folder))
    
    # Create subfolders
    folder_paths = {"weekly": weekly_folder}
    for subfolder in SUBFOLDERS:
        subfolder_path = os.path.join(weekly_folder, subfolder)
        if not os.path.exists(subfolder_path):
            os.makedirs(subfolder_path)
            print("Created subfolder: {}".format(subfolder))
        else:
            print("Subfolder already exists: {}".format(subfolder))
        folder_paths[subfolder] = subfolder_path
    
    return folder_paths


def export_pdf(doc, folder_paths, heartbeat_callback=None):
    """Export PDF files to the pdf subfolder
    
    Args:
        doc: Revit Document object
        folder_paths: Dictionary of folder paths from create_export_folders()
        heartbeat_callback: Optional function to call for logging progress
    
    Returns:
        list: List of exported PDF file paths
    """
    pdf_folder = folder_paths["pdf"]
    print("Exporting PDFs to: {}".format(pdf_folder))
    
    # Get PIM_Number for filename prefix
    pim_number = get_pim_number(doc)
    
    # Get sheets to export
    sheets_to_export = get_sheets_to_export(doc, heartbeat_callback)
    exported_files = []
    
    if not sheets_to_export:
        print("No sheets found with parameter '{}' - skipping PDF export".format(SHEET_FILTER_PARAMETER))
        return exported_files
    
    # Export each sheet as PDF
    for sheet in sheets_to_export:
        try:
            # Create filename in format: {pim}_{sheetnum}_{sheetname}.pdf
            sheet_number = sheet.SheetNumber
            safe_name = "".join(c for c in sheet.Name if c.isalnum() or c in (' ', '-', '_')).rstrip()
            
            if pim_number:
                pdf_filename = "{}-{}_{}.pdf".format(pim_number, sheet_number, safe_name)
            else:
                pdf_filename = "{}_{}.pdf".format(sheet_number, safe_name)
            
            pdf_path = os.path.join(pdf_folder, pdf_filename)
            
            # Export sheet as PDF
            print("Exporting sheet '{}' to PDF...".format(sheet.Name))
            
            # Create export options
            export_options = DB.PDFExportOptions()
            export_options.HideCropBoundaries = True
            export_options.HideScopeBoxes = True
            export_options.HideReferencePlane = True
            
            # Check sheet's color parameter
            color_param = sheet.LookupParameter(PDF_COLOR_PARAMETER)
            if color_param and color_param.AsString():
                # Use color if parameter is set
                export_options.ColorDepth = DB.ColorDepth.Color
                print("  Using color export for sheet '{}'".format(sheet.Name))
            else:
                # Use grayscale if no color parameter
                export_options.ColorDepth = DB.ColorDepth.Grayscale
                print("  Using grayscale export for sheet '{}'".format(sheet.Name))
            
            # Export the sheet
            doc.Export(pdf_folder, pdf_filename, [sheet.Id], export_options)
            
            exported_files.append(pdf_path)
            print("Exported: {}".format(pdf_filename))
            
        except Exception as e:
            print("Error exporting sheet '{}': {}".format(sheet.Name, e))
    
    return exported_files


def export_dwg(doc, folder_paths, heartbeat_callback=None):
    """Export DWG files to the dwg subfolder
    
    Args:
        doc: Revit Document object
        folder_paths: Dictionary of folder paths from create_export_folders()
        heartbeat_callback: Optional function to call for logging progress
    
    Returns:
        list: List of exported DWG file paths
    """
    dwg_folder = folder_paths["dwg"]
    print("Exporting DWGs to: {}".format(dwg_folder))
    
    # Get PIM_Number for filename prefix
    pim_number = get_pim_number(doc)
    
    # Get sheets to export
    sheets_to_export = get_sheets_to_export(doc, heartbeat_callback)
    exported_files = []
    
    if not sheets_to_export:
        print("No sheets found with parameter '{}' - skipping DWG export".format(SHEET_FILTER_PARAMETER))
        return exported_files
    
    # Export each sheet as DWG
    for sheet in sheets_to_export:
        try:
            # Create filename in format: {pim}_{sheetnum}_{sheetname}.dwg
            sheet_number = sheet.SheetNumber
            safe_name = "".join(c for c in sheet.Name if c.isalnum() or c in (' ', '-', '_')).rstrip()
            
            if pim_number:
                dwg_filename = "{}-{}_{}.dwg".format(pim_number, sheet_number, safe_name)
            else:
                dwg_filename = "{}_{}.dwg".format(sheet_number, safe_name)
            
            dwg_path = os.path.join(dwg_folder, dwg_filename)
            
            # Export sheet as DWG
            print("Exporting sheet '{}' to DWG...".format(sheet.Name))
            
            # Create DWG export options
            export_options = DB.DWGExportOptions()
            export_options.MergedViews = False
            export_options.ExportingAreas = False
            
            # Use the specified DWG setting
            try:
                # Get the DWG export setting by name
                dwg_settings = DB.DWGExportOptions.GetPredefinedOptions(doc)
                for setting in dwg_settings:
                    if setting.Name == DWG_SETTING_NAME:
                        export_options = setting
                        print("  Using DWG setting '{}' for sheet '{}'".format(DWG_SETTING_NAME, sheet.Name))
                        break
                else:
                    print("  DWG setting '{}' not found, using default for sheet '{}'".format(DWG_SETTING_NAME, sheet.Name))
            except Exception as e:
                print("  Error loading DWG setting '{}': {}, using default for sheet '{}'".format(DWG_SETTING_NAME, e, sheet.Name))
            
            # Export the sheet
            doc.Export(dwg_folder, dwg_filename, [sheet.Id], export_options)
            
            exported_files.append(dwg_path)
            print("Exported: {}".format(dwg_filename))
            
        except Exception as e:
            print("Error exporting sheet '{}': {}".format(sheet.Name, e))
    
    return exported_files


def export_jpg(doc, folder_paths, heartbeat_callback=None):
    """Export JPG images to the jpg subfolder
    
    Args:
        doc: Revit Document object
        folder_paths: Dictionary of folder paths from create_export_folders()
        heartbeat_callback: Optional function to call for logging progress
    
    Returns:
        list: List of exported JPG file paths
    """
    jpg_folder = folder_paths["jpg"]
    print("Exporting JPGs to: {}".format(jpg_folder))
    
    # Get PIM_Number for filename prefix
    pim_number = get_pim_number(doc)
    
    # Get sheets to export
    sheets_to_export = get_sheets_to_export(doc, heartbeat_callback)
    exported_files = []
    
    if not sheets_to_export:
        print("No sheets found with parameter '{}' - skipping JPG export".format(SHEET_FILTER_PARAMETER))
        return exported_files
    
    # Export each sheet as JPG
    for sheet in sheets_to_export:
        try:
            # Create filename in format: {pim}_{sheetnum}_{sheetname}.jpg
            sheet_number = sheet.SheetNumber
            safe_name = "".join(c for c in sheet.Name if c.isalnum() or c in (' ', '-', '_')).rstrip()
            
            if pim_number:
                jpg_filename = "{}-{}_{}.jpg".format(pim_number, sheet_number, safe_name)
            else:
                jpg_filename = "{}_{}.jpg".format(sheet_number, safe_name)
            
            jpg_path = os.path.join(jpg_folder, jpg_filename)
            
            # Export sheet as JPG
            print("Exporting sheet '{}' to JPG...".format(sheet.Name))
            
            # Create image export options
            export_options = DB.ImageExportOptions()
            export_options.FilePath = jpg_path
            export_options.ImageResolution = DB.ImageResolution.DPI_150
            export_options.ZoomType = DB.ZoomType.FitToPage
            export_options.PixelType = DB.PixelType.RGB
            
            # Export the sheet
            doc.ExportImage(export_options)
            
            exported_files.append(jpg_path)
            print("Exported: {}".format(jpg_filename))
            
        except Exception as e:
            print("Error exporting sheet '{}': {}".format(sheet.Name, e))
    
    return exported_files


def run_all_exports(doc, heartbeat_callback=None):
    """Run all export operations
    
    Args:
        doc: Revit Document object
        heartbeat_callback: Optional function to call for logging progress
            Should accept (step, message, is_error=False)
    
    Returns:
        dict: Dictionary with export results
            {"folder_paths": {...},
             "pdf_files": [...],
             "dwg_files": [...],
             "jpg_files": [...]}
    """
    def log(message, is_error=False):
        """Helper to log messages"""
        print(message)
        if heartbeat_callback:
            heartbeat_callback("EXPORT", message, is_error=is_error)
    
    try:
        # Create folder structure
        log("Creating export folder structure...")
        folder_paths = create_export_folders()
        log("Folders created: {}".format(folder_paths["weekly"]))
        
        # Export PDFs
        log("Starting PDF export...")
        pdf_files = export_pdf(doc, folder_paths, heartbeat_callback)
        log("PDF export completed: {} files".format(len(pdf_files)))
        
        # Export DWGs
        log("Starting DWG export...")
        dwg_files = export_dwg(doc, folder_paths, heartbeat_callback)
        log("DWG export completed: {} files".format(len(dwg_files)))
        
        # Export JPGs
        log("Starting JPG export...")
        jpg_files = export_jpg(doc, folder_paths, heartbeat_callback)
        log("JPG export completed: {} files".format(len(jpg_files)))
        
        export_results = {
            "folder_paths": folder_paths,
            "pdf_files": pdf_files,
            "dwg_files": dwg_files,
            "jpg_files": jpg_files
        }
        
        return export_results
        
    except Exception as e:
        log("Export error: {}".format(str(e)), is_error=True)
        raise

