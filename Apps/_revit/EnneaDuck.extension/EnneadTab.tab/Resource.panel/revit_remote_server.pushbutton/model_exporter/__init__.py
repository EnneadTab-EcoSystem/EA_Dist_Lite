# -*- coding: utf-8 -*-
"""
Model Exporter Module - Standalone Revit Export System
"""

from Autodesk.Revit import DB # pyright: ignore
import os
import time
import traceback
import gc
from datetime import datetime


class ExportError:
    """Error classification constants for better debugging"""
    TIMEOUT = "timeout"
    ACCESS_DENIED = "access_denied"
    FILE_LOCKED = "file_locked"
    MEMORY_ERROR = "memory_error"
    REVIT_API_ERROR = "revit_api_error"
    VALIDATION_FAILED = "validation_failed"
    NO_PRINTSET = "no_printset"
    NO_SHEETS = "no_sheets"


class ModelExporter:
    """
    Main export coordinator for Revit models.
    Exports first 10 sheets from print-set to JPG, PDF, and DWG formats.
    
    Fixed Settings (hardcoded, same for all exports):
    - Image: 150 DPI, 1920px width
    - PDF: Individual PDFs per sheet
    - DWG: 2018 format, AIA layer standard
    - Timeout: 60s/image, 120s/PDF, 180s/DWG
    - Max sheets: 10 (from print-set)
    """
    
    # Fixed export settings - same for ALL projects
    IMAGE_RESOLUTION = DB.ImageResolution.DPI_150
    IMAGE_WIDTH = 1920
    PDF_COMBINE = False  # Individual PDFs per sheet
    DWG_VERSION = DB.ACADVersion.R2018
    MAX_SHEETS = 10  # Export first 10 sheets from print-set
    
    TIMEOUTS = {
        "image": 60,   # 60s per image
        "pdf": 120,    # 120s per PDF
        "dwg": 180     # 180s per DWG
    }
    
    MAX_RETRIES = 2
    RETRY_DELAY = 2  # seconds
    GC_EVERY_N_SHEETS = 5  # Force GC after every 5 sheets
    
    def __init__(self, doc, output_base_path):
        """
        Initialize exporter.
        
        Args:
            doc: Active Revit document
            output_base_path: Base directory for all exports
        """
        self.doc = doc
        self.output_base_path = output_base_path
        
        # Initialize report structure
        self.report = {
            "export_status": "not_started",
            "summary": {
                "total_sheets": 0,
                "successful_sheets": 0,
                "failed_sheets": 0,
                "partial_failures": 0
            },
            "sheets": [],
            "errors": [],
            "performance": {
                "total_duration_seconds": 0,
                "average_time_per_sheet": 0
            },
            "settings": {
                "image_resolution": "150 DPI",
                "image_width": self.IMAGE_WIDTH,
                "pdf_combine": self.PDF_COMBINE,
                "dwg_version": "2018",
                "max_sheets": self.MAX_SHEETS
            }
        }
    
    def _classify_error(self, exception):
        """Classify errors for better debugging"""
        error_msg = str(exception).lower()
        if "timeout" in error_msg:
            return ExportError.TIMEOUT
        elif "access denied" in error_msg or "permission" in error_msg:
            return ExportError.ACCESS_DENIED
        elif "file is locked" in error_msg or "being used by another" in error_msg:
            return ExportError.FILE_LOCKED
        elif "out of memory" in error_msg or "outofmemory" in error_msg:
            return ExportError.MEMORY_ERROR
        else:
            return ExportError.REVIT_API_ERROR
    
    def _get_printset_sheets(self):
        """
        Get first N sheets from the print-set.
        Returns (sheets_list, error_message)
        """
        try:
            print_manager = self.doc.PrintManager
            view_sheet_setting = print_manager.ViewSheetSetting
            
            # Check if print-set has sheets
            if view_sheet_setting.CurrentViewSheetSet.Size == 0:
                return [], "No sheets in print-set"
            
            # Get sheets from print-set
            sheet_ids = view_sheet_setting.CurrentViewSheetSet.Views
            if not sheet_ids or sheet_ids.Size == 0:
                return [], "Print-set is empty"
            
            sheets = []
            for sheet_id in sheet_ids:
                sheet = self.doc.GetElement(sheet_id)
                if sheet and isinstance(sheet, DB.ViewSheet):
                    sheets.append(sheet)
                    if len(sheets) >= self.MAX_SHEETS:
                        break
            
            if not sheets:
                return [], "No valid sheets found in print-set"
            
            return sheets, None
            
        except Exception as e:
            return [], "Failed to get print-set sheets: {}".format(str(e))
    
    def _get_fallback_sheets(self):
        """
        Fallback: Get first N sheets from document if print-set fails.
        Returns (sheets_list, error_message)
        """
        try:
            collector = DB.FilteredElementCollector(self.doc)
            all_sheets = collector.OfClass(DB.ViewSheet).ToElements()
            
            # Filter out placeholder sheets
            valid_sheets = [s for s in all_sheets if not s.IsPlaceholder]
            
            if not valid_sheets:
                return [], "No sheets found in document"
            
            # Take first N sheets
            sheets = valid_sheets[:self.MAX_SHEETS]
            return sheets, None
            
        except Exception as e:
            return [], "Failed to get fallback sheets: {}".format(str(e))
    
    def _get_sheets_to_export(self):
        """
        Get sheets to export (print-set first, fallback to first N sheets).
        Returns (sheets_list, source_description, error_message)
        """
        # Try print-set first
        sheets, error = self._get_printset_sheets()
        if sheets:
            return sheets, "print-set", None
        
        print("WARNING: Print-set unavailable ({}), using fallback...".format(error))
        
        # Fallback to first N sheets
        sheets, error = self._get_fallback_sheets()
        if sheets:
            return sheets, "first {} sheets (fallback)".format(len(sheets)), None
        
        # Both failed
        return [], None, "No sheets available: {}".format(error)
    
    def export_all(self):
        """
        Main export function - exports all formats sequentially.
        Returns: export report dictionary
        """
        start_time = time.time()
        
        try:
            self.report["export_status"] = "running"
            
            # Get sheets to export
            sheets, source, error = self._get_sheets_to_export()
            if error:
                self.report["export_status"] = "failed"
                self.report["errors"].append({
                    "error": error,
                    "error_class": ExportError.NO_SHEETS
                })
                print("STATUS: Export failed - {}".format(error))
                return self.report
            
            self.report["summary"]["total_sheets"] = len(sheets)
            print("STATUS: Starting export for {} sheets (from {})...".format(
                len(sheets), source))
            
            # Export each sheet sequentially
            for i, sheet in enumerate(sheets):
                self._export_single_sheet(sheet, i + 1, len(sheets))
                
                # Periodic garbage collection
                if (i + 1) % self.GC_EVERY_N_SHEETS == 0:
                    print("STATUS: Running garbage collection...")
                    gc.collect()
            
            # Calculate summary
            self.report["export_status"] = "completed"
            self.report["summary"]["successful_sheets"] = sum(
                1 for s in self.report["sheets"] 
                if s["overall_status"] in ["all_success", "partial"]
            )
            self.report["summary"]["failed_sheets"] = sum(
                1 for s in self.report["sheets"] 
                if s["overall_status"] == "all_failed"
            )
            self.report["summary"]["partial_failures"] = sum(
                1 for s in self.report["sheets"] 
                if s["overall_status"] == "partial"
            )
            
            # Calculate performance metrics
            total_duration = time.time() - start_time
            self.report["performance"]["total_duration_seconds"] = round(total_duration, 2)
            if self.report["summary"]["total_sheets"] > 0:
                self.report["performance"]["average_time_per_sheet"] = round(
                    total_duration / self.report["summary"]["total_sheets"], 2
                )
            
            print("STATUS: Export completed: {}/{} sheets successful".format(
                self.report["summary"]["successful_sheets"],
                self.report["summary"]["total_sheets"]
            ))
            
            return self.report
            
        except Exception as e:
            self.report["export_status"] = "failed"
            self.report["errors"].append({
                "error": str(e),
                "error_class": self._classify_error(e),
                "traceback": traceback.format_exc()
            })
            print("STATUS: Export failed with exception: {}".format(str(e)))
            return self.report
    
    def _export_single_sheet(self, sheet, current_num, total_num):
        """
        Export a single sheet to all formats.
        
        CRITICAL: Each format export is INDEPENDENT and ISOLATED.
        - If image export fails, PDF and DWG still attempt
        - If PDF export fails, DWG still attempts
        - Failures are caught and reported per-format, never propagated
        - All three formats always attempt, regardless of individual failures
        """
        sheet_result = {
            "sheet_name": sheet.Name,
            "sheet_number": sheet.SheetNumber,
            "exports": {},
            "overall_status": "all_failed"
        }
        
        print("STATUS: [{}/{}] Exporting {} - {}...".format(
            current_num, total_num, sheet.SheetNumber, sheet.Name
        ))
        
        success_count = 0
        fail_count = 0
        
        # Export to each format sequentially
        # Import here to avoid circular dependencies
        from .image_exporter import ImageExporter
        from .pdf_exporter import PDFExporter
        from .dwg_exporter import DWGExporter
        
        # ============================================================================
        # IMAGE EXPORT (JPG) - Independent, failure does NOT stop PDF or DWG
        # ============================================================================
        image_result = ImageExporter(self.doc, self.output_base_path, self).export_sheet(sheet)
        sheet_result["exports"]["image"] = image_result
        if image_result["status"] == "success":
            success_count += 1
            print("STATUS:   -> Image: Success ({:.1f}s)".format(image_result.get("duration", 0)))
        else:
            fail_count += 1
            print("STATUS:   -> Image: Failed ({})".format(image_result.get("error_class", "unknown")))
        
        # ============================================================================
        # PDF EXPORT - Independent, runs regardless of image result
        # ============================================================================
        pdf_result = PDFExporter(self.doc, self.output_base_path, self).export_sheet(sheet)
        sheet_result["exports"]["pdf"] = pdf_result
        if pdf_result["status"] == "success":
            success_count += 1
            print("STATUS:   -> PDF: Success ({:.1f}s)".format(pdf_result.get("duration", 0)))
        else:
            fail_count += 1
            print("STATUS:   -> PDF: Failed ({})".format(pdf_result.get("error_class", "unknown")))
        
        # ============================================================================
        # DWG EXPORT - Independent, runs regardless of image/PDF results
        # ============================================================================
        dwg_result = DWGExporter(self.doc, self.output_base_path, self).export_sheet(sheet)
        sheet_result["exports"]["dwg"] = dwg_result
        if dwg_result["status"] == "success":
            success_count += 1
            print("STATUS:   -> DWG: Success ({:.1f}s)".format(dwg_result.get("duration", 0)))
        else:
            fail_count += 1
            print("STATUS:   -> DWG: Failed ({})".format(dwg_result.get("error_class", "unknown")))
        
        # Determine overall status
        if success_count == 3:
            sheet_result["overall_status"] = "all_success"
        elif success_count > 0:
            sheet_result["overall_status"] = "partial"
        else:
            sheet_result["overall_status"] = "all_failed"
        
        self.report["sheets"].append(sheet_result)

