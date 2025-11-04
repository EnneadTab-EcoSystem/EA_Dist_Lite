# -*- coding: utf-8 -*-
"""
PDF Exporter - PDF export functionality
"""

from Autodesk.Revit import DB # pyright: ignore
import os
import time
import traceback
from .export_helpers import (
    validate_export, ensure_export_directory,
    cleanup_failed_export, safe_filename
)


class PDFExporter:
    """Handles PDF export for sheets"""
    
    def __init__(self, doc, output_base_path, parent_exporter):
        self.doc = doc
        self.output_base_path = output_base_path
        self.parent = parent_exporter  # Access to parent's settings and methods
    
    def export_sheet(self, sheet):
        """
        Export a single sheet to PDF with retry logic.
        
        Args:
            sheet: ViewSheet to export
        
        Returns:
            Result dictionary with status, path, duration, or error info
        """
        for attempt in range(1, self.parent.MAX_RETRIES + 1):
            try:
                result = self._attempt_export(sheet, attempt)
                
                # Check if successful
                if result["status"] == "success":
                    return result
                
                # Check if should retry
                error_class = result.get("error_class")
                if error_class in ["file_locked", "memory_error"] and attempt < self.parent.MAX_RETRIES:
                    print("      PDF export attempt {} failed: {} - retrying...".format(
                        attempt, error_class
                    ))
                    time.sleep(self.parent.RETRY_DELAY)
                    continue
                
                # Non-retryable or final attempt
                return result
                
            except Exception as e:
                # Unexpected error during attempt
                result = {
                    "status": "failed",
                    "error": str(e),
                    "error_class": self.parent._classify_error(e),
                    "attempt": attempt,
                    "traceback": traceback.format_exc()
                }
                
                if attempt < self.parent.MAX_RETRIES:
                    time.sleep(self.parent.RETRY_DELAY)
                    continue
                
                return result
        
        # Should never reach here
        return {
            "status": "failed",
            "error": "Max retries exceeded"
        }
    
    def _attempt_export(self, sheet, attempt_num):
        """Single export attempt with validation"""
        start_time = time.time()
        output_path = None
        
        try:
            # Ensure output directory exists
            export_dir = ensure_export_directory(self.output_base_path, "pdfs")
            
            # Create safe filename
            filename = safe_filename(sheet.SheetNumber, sheet.Name)
            output_path = os.path.join(export_dir, "{}.pdf".format(filename))
            
            # Delete existing file to allow overwrite (Revit won't overwrite by default)
            if os.path.exists(output_path):
                try:
                    os.remove(output_path)
                    print("      Removed existing file: {}".format(output_path))
                except Exception as e:
                    print("      WARNING: Could not remove existing file: {}".format(e))
            
            # Configure PDF export options  
            options = DB.PDFExportOptions()
            options.StopOnError = False
            options.FileName = filename  # Set filename in options
            # Note: CombineMultipleSheets removed - not available in Revit 2024+
            
            # Create view ID list (using .NET List for API compatibility)
            from System.Collections.Generic import List  # pyright: ignore
            view_ids = List[DB.ElementId]()
            view_ids.Add(sheet.Id)
            
            # Export with timeout check
            export_start = time.time()
            # For PDF, use PrintManager-based export which is more reliable in 2024+
            self.doc.Export(export_dir, view_ids, options)
            export_duration = time.time() - export_start
            
            # PDF export auto-generates filename, find the actual output file
            import glob
            pdf_pattern = os.path.join(export_dir, "{}*.pdf".format(sheet.SheetNumber))
            pdf_files = glob.glob(pdf_pattern)
            if pdf_files:
                actual_output = pdf_files[0]  # Take first match
                # Rename to our desired filename if different
                if actual_output != output_path:
                    try:
                        if os.path.exists(output_path):
                            os.remove(output_path)
                        os.rename(actual_output, output_path)
                    except:
                        output_path = actual_output  # Use the auto-generated name
            
            # Check timeout (warning only, not failure)
            timeout = self.parent.TIMEOUTS["pdf"]
            if export_duration > timeout:
                print("      WARNING: PDF export took {:.1f}s (timeout: {}s)".format(
                    export_duration, timeout
                ))
            
            # Validate exported file
            is_valid, error_msg = validate_export(output_path, min_size_kb=5)
            if not is_valid:
                cleanup_failed_export(output_path)
                return {
                    "status": "failed",
                    "error": "Validation failed: {}".format(error_msg),
                    "error_class": "validation_failed",
                    "attempt": attempt_num,
                    "file_path": output_path
                }
            
            # Success
            file_size = os.path.getsize(output_path)
            total_duration = time.time() - start_time
            
            return {
                "status": "success",
                "path": output_path,
                "duration": round(total_duration, 2),
                "file_size_bytes": file_size,
                "attempt": attempt_num
            }
            
        except Exception as e:
            # Cleanup on failure
            if output_path:
                cleanup_failed_export(output_path)
            
            duration = time.time() - start_time
            return {
                "status": "failed",
                "error": str(e),
                "error_class": self.parent._classify_error(e),
                "attempt": attempt_num,
                "duration": round(duration, 2),
                "traceback": traceback.format_exc()
            }

