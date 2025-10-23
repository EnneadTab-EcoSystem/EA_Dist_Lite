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
import config_loader

# =============================================================================
# LOAD CONFIGURATION
# =============================================================================

# Load export settings from config.json
EXPORT_SETTINGS = config_loader.get_export_settings()
PROJECT_INFO = config_loader.get_project_info()

# Extract commonly used settings
OUTPUT_BASE_PATH = EXPORT_SETTINGS.get('output_base_path', '')
SHEET_FILTER_PARAMETER = EXPORT_SETTINGS.get('sheet_filter_parameter', 'Sheet_$Issue_AutoPublish')
DWG_SETTING_NAME = EXPORT_SETTINGS.get('dwg_setting_name', 'to NYU dwg')
PDF_COLOR_PARAMETER = EXPORT_SETTINGS.get('pdf_color_parameter', 'Print_In_Color')
SUBFOLDERS = EXPORT_SETTINGS.get('subfolders', ['pdf', 'dwg', 'jpg'])
DATE_FORMAT = EXPORT_SETTINGS.get('date_format', '%Y-%m-%d')
PDF_OPTIONS = EXPORT_SETTINGS.get('pdf_options', {})
JPG_OPTIONS = EXPORT_SETTINGS.get('jpg_options', {})


def get_weekly_folder_path():
    """Get the path for this week's export folder (yyyy-mm-dd {model_name} format)
    
    Returns:
        str: Full path to weekly folder (e.g., .../2025-10-21 2534_A_EA_NYU HQ_Shell)
    """
    date_stamp = datetime.now().strftime(DATE_FORMAT)
    model_name = config_loader.get_model_name()
    
    # Create folder name: "yyyy-mm-dd ModelName"
    folder_name = "{} {}".format(date_stamp, model_name)
    weekly_folder = os.path.join(OUTPUT_BASE_PATH, folder_name)
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
        
        # Get PIM parameter name from config
        pim_param_name = PROJECT_INFO.get('pim_parameter_name', 'PIM_Number')
        
        # If pim_parameter_name is None/null, don't use PIM prefix
        if pim_param_name is None:
            print("PIM parameter name is None - skipping PIM number in filename")
            return ""
        
        # Get project info
        project_info = doc.ProjectInformation
        if project_info:
            pim_param = project_info.LookupParameter(pim_param_name)
            if pim_param and pim_param.AsString():
                pim_value = pim_param.AsString().strip()
                print("Found {}: '{}'".format(pim_param_name, pim_value))
                return pim_value
        print("{} not found in project info".format(pim_param_name))
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
    
    if heartbeat_callback:
        heartbeat_callback("EXPORT", "Found {} total sheets in document".format(len(all_sheets)))
    
    # Production filtering logic - filter sheets by parameter value
    for sheet in all_sheets:
        try:
            param = sheet.LookupParameter(SHEET_FILTER_PARAMETER)
            if param:
                # Get parameter value based on storage type
                if param.StorageType == DB.StorageType.String:
                    param_value = param.AsString()
                elif param.StorageType == DB.StorageType.Integer:
                    param_value = param.AsInteger()
                elif param.StorageType == DB.StorageType.Double:
                    param_value = param.AsDouble()
                elif param.StorageType == DB.StorageType.ElementId:
                    param_value = param.AsElementId()
                else:
                    param_value = param.AsString()
                
                # Check if parameter has meaningful value (any non-empty, non-"None" value)
                has_value = False
                if param.StorageType == DB.StorageType.String:
                    has_value = (param_value and 
                               param_value.strip() != "" and 
                               param_value.strip().lower() != "none")
                elif param.StorageType == DB.StorageType.Integer:
                    has_value = param_value != 0
                elif param.StorageType == DB.StorageType.Double:
                    has_value = param_value != 0.0
                elif param.StorageType == DB.StorageType.ElementId:
                    has_value = param_value and param_value.IntegerValue != -1
                else:
                    has_value = (param_value and 
                               str(param_value).strip() != "" and 
                               str(param_value).strip().lower() != "none")
                
                if has_value:
                    sheets_to_export.append(sheet)
                    if heartbeat_callback:
                        heartbeat_callback("EXPORT", "Sheet '{}' marked for export".format(sheet.Name))
        except Exception as e:
            pass  # Skip sheets with errors
    
    if heartbeat_callback:
        heartbeat_callback("EXPORT", "Found {} sheets to export (out of {} total)".format(len(sheets_to_export), len(all_sheets)))
    
    return sheets_to_export


def create_export_folders():
    """Create the weekly folder structure with pdf, dwg, jpg subfolders
    
    Returns:
        dict: Dictionary with paths for each export type
            {"weekly": "path/to/2025-10-21",
             "pdf": "path/to/2025-10-21/PDF",
             "dwg": "path/to/2025-10-21/DWG",
             "jpg": "path/to/2025-10-21/JPG"}
        Note: Keys are lowercase for consistent access, values preserve config case
    """
    weekly_folder = get_weekly_folder_path()
    
    # Create weekly folder if it doesn't exist
    if not os.path.exists(weekly_folder):
        os.makedirs(weekly_folder)
    
    # Create subfolders
    folder_paths = {"weekly": weekly_folder}
    for subfolder in SUBFOLDERS:
        subfolder_path = os.path.join(weekly_folder, subfolder)
        if not os.path.exists(subfolder_path):
            os.makedirs(subfolder_path)
        # Use lowercase key for consistent access regardless of config case
        folder_paths[subfolder.lower()] = subfolder_path
    
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
    from System.Collections.Generic import List
    
    for sheet in sheets_to_export:
        try:
            # Create filename in format: {pim}-{sheetnum}_{sheetname}
            sheet_number = sheet.SheetNumber
            safe_name = "".join(c for c in sheet.Name if c.isalnum() or c in (' ', '-', '_')).rstrip()
            
            if pim_number:
                filename_base = "{}-{}_{}".format(pim_number, sheet_number, safe_name)
            else:
                filename_base = "{}_{}".format(sheet_number, safe_name)
            
            pdf_path = os.path.join(pdf_folder, filename_base + ".pdf")
            
            # Delete existing file to allow overwrite (Revit won't overwrite by default)
            if os.path.exists(pdf_path):
                try:
                    os.remove(pdf_path)
                except:
                    pass
            
            # Create export options from config
            export_options = DB.PDFExportOptions()
            export_options.HideCropBoundaries = PDF_OPTIONS.get('hide_crop_boundaries', True)
            export_options.HideScopeBoxes = PDF_OPTIONS.get('hide_scope_boxes', True)
            export_options.HideReferencePlane = PDF_OPTIONS.get('hide_reference_plane', True)
            export_options.Combine = PDF_OPTIONS.get('combine', False)
            export_options.StopOnError = PDF_OPTIONS.get('stop_on_error', False)
            
            # Set custom naming rule to match our filename format
            from EnneadTab import DATA_CONVERSION
            sheet_num_data = DB.TableCellCombinedParameterData.Create()
            sheet_num_data.ParamId = DB.ElementId(DB.BuiltInParameter.SHEET_NUMBER)
            if pim_number:
                sheet_num_data.Prefix = pim_number + "-"
            sheet_num_data.Separator = "_"
            
            sheet_name_data = DB.TableCellCombinedParameterData.Create()
            sheet_name_data.ParamId = DB.ElementId(DB.BuiltInParameter.SHEET_NAME)
            
            naming_rule = DATA_CONVERSION.list_to_system_list(
                [sheet_num_data, sheet_name_data], 
                type="TableCellCombinedParameterData", 
                use_IList=False
            )
            export_options.SetNamingRule(naming_rule)
            
            # Set color based on Print_In_Color parameter (boolean: 1=color, 0=grayscale)
            color_param = sheet.LookupParameter(PDF_COLOR_PARAMETER)
            if color_param and color_param.AsInteger() == 1:
                export_options.ColorDepth = DB.ColorDepthType.Color
            else:
                export_options.ColorDepth = DB.ColorDepthType.GrayScale
            
            # Create .NET List for view IDs
            view_ids = List[DB.ElementId]()
            view_ids.Add(sheet.Id)
            
            # Export the sheet
            doc.Export(pdf_folder, view_ids, export_options)
            
            # Verify export succeeded
            if os.path.exists(pdf_path):
                exported_files.append(pdf_path)
            
        except Exception as e:
            if heartbeat_callback:
                heartbeat_callback("EXPORT", "PDF export error for '{}': {}".format(sheet.Name, str(e)))
    
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
        return exported_files
    
    # Export each sheet as DWG
    from System.Collections.Generic import List
    
    for sheet in sheets_to_export:
        try:
            # Create filename in format: {pim}-{sheetnum}_{sheetname}
            sheet_number = sheet.SheetNumber
            safe_name = "".join(c for c in sheet.Name if c.isalnum() or c in (' ', '-', '_')).rstrip()
            
            if pim_number:
                filename_base = "{}-{}_{}".format(pim_number, sheet_number, safe_name)
            else:
                filename_base = "{}_{}".format(sheet_number, safe_name)
            
            dwg_path = os.path.join(dwg_folder, filename_base + ".dwg")
            
            # Delete existing file to allow overwrite
            if os.path.exists(dwg_path):
                try:
                    os.remove(dwg_path)
                except:
                    pass
            
            # Get DWG export options
            try:
                export_options = DB.DWGExportOptions.GetPredefinedOptions(doc, DWG_SETTING_NAME)
                if not export_options:
                    export_options = DB.DWGExportOptions()
                    export_options.MergedViews = False
                    export_options.ExportingAreas = False
            except:
                export_options = DB.DWGExportOptions()
                export_options.MergedViews = False
                export_options.ExportingAreas = False
            
            # Create .NET List for view IDs
            view_ids = List[DB.ElementId]()
            view_ids.Add(sheet.Id)
            
            # Export the sheet (filename without extension)
            doc.Export(dwg_folder, filename_base, view_ids, export_options)
            
            # Verify export succeeded
            if os.path.exists(dwg_path):
                exported_files.append(dwg_path)
            
        except Exception as e:
            if heartbeat_callback:
                heartbeat_callback("EXPORT", "DWG export error for '{}': {}".format(sheet.Name, str(e)))
    
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
        return exported_files
    
    # Export each sheet as JPG
    from System.Collections.Generic import List
    
    for sheet in sheets_to_export:
        try:
            # Create filename in format: {pim}-{sheetnum}_{sheetname}
            sheet_number = sheet.SheetNumber
            safe_name = "".join(c for c in sheet.Name if c.isalnum() or c in (' ', '-', '_')).rstrip()
            
            if pim_number:
                filename_base = "{}-{}_{}".format(pim_number, sheet_number, safe_name)
            else:
                filename_base = "{}_{}".format(sheet_number, safe_name)
            
            jpg_path = os.path.join(jpg_folder, filename_base + ".jpg")
            
            # Delete existing file to allow overwrite
            if os.path.exists(jpg_path):
                try:
                    os.remove(jpg_path)
                except:
                    pass
            
            # Create image export options from config
            export_options = DB.ImageExportOptions()
            # FilePath must be full path to OUTPUT FILE without extension (Revit adds .jpg)
            file_path_no_ext = os.path.join(jpg_folder, filename_base)
            export_options.FilePath = file_path_no_ext
            export_options.FitDirection = DB.FitDirectionType.Horizontal
            
            # Map resolution DPI to ImageResolution enum
            resolution_dpi = JPG_OPTIONS.get('resolution_dpi', 150)
            if resolution_dpi == 72:
                export_options.ImageResolution = DB.ImageResolution.DPI_72
            elif resolution_dpi == 150:
                export_options.ImageResolution = DB.ImageResolution.DPI_150
            elif resolution_dpi == 300:
                export_options.ImageResolution = DB.ImageResolution.DPI_300
            elif resolution_dpi == 600:
                export_options.ImageResolution = DB.ImageResolution.DPI_600
            else:
                export_options.ImageResolution = DB.ImageResolution.DPI_150
            
            export_options.ZoomType = DB.ZoomFitType.FitToPage
            export_options.PixelSize = JPG_OPTIONS.get('pixel_size', 1920)
            export_options.ExportRange = DB.ExportRange.SetOfViews
            
            # Set the views/sheets to export
            view_ids = List[DB.ElementId]()
            view_ids.Add(sheet.Id)
            export_options.SetViewsAndSheets(view_ids)
            
            # Export the sheet
            # NOTE: Revit adds " - Sheet - " to the filename automatically!
            # We'll search for the exported file and rename it
            doc.ExportImage(export_options)
            
            # Find and rename the exported file
            # Revit exports with pattern: "filename - Sheet - sheetname.jpg"
            # We need to find it and rename to our desired format
            found_file = None
            
            # Search for files in the folder that match our base filename
            if os.path.exists(jpg_folder):
                for file in os.listdir(jpg_folder):
                    if filename_base in file and file.lower().endswith('.jpg'):
                        # Found a file with our base name
                        found_path = os.path.join(jpg_folder, file)
                        if found_path != jpg_path:
                            # Need to rename
                            try:
                                if os.path.exists(jpg_path):
                                    os.remove(jpg_path)
                                os.rename(found_path, jpg_path)
                                found_file = jpg_path
                                if heartbeat_callback:
                                    heartbeat_callback("EXPORT", "JPG exported and renamed: {} -> {}".format(
                                        file, os.path.basename(jpg_path)))
                                break
                            except Exception as rename_error:
                                # Rename failed, use the original filename
                                found_file = found_path
                                if heartbeat_callback:
                                    heartbeat_callback("EXPORT", "JPG exported but rename failed, using: {}".format(file))
                                break
                        else:
                            # File already has correct name
                            found_file = jpg_path
                            break
            
            if found_file:
                exported_files.append(found_file)
            elif heartbeat_callback:
                heartbeat_callback("EXPORT", "JPG not found for '{}' after export (searched for: {})".format(
                    sheet.Name, filename_base)
                )
            
        except Exception as e:
            if heartbeat_callback:
                heartbeat_callback("EXPORT", "JPG export error for '{}': {}".format(sheet.Name, str(e)))
    
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

