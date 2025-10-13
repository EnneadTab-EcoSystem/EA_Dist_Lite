__context__ = "zero-doc"
#!/usr/bin/python
# -*- coding: utf-8 -*-

__doc__ = "Standalone Remote Server Script (no EnneadTab/proDUCKtion dependency)."
__title__ = "Revit Remote Server"

from Autodesk.Revit import DB # pyright: ignore 
import os
import json
import time
import traceback
from datetime import datetime
from datetime import timedelta



"""
VERY IMPOETANT TO NOT INTRODUCE 
ANY ENNEADTAB DEPENDENCY and production module at import time HERE.

AND we should never silent any except, so the rasie exception can be bubble up to the TASKOUTPUT output and be visible to user outside revit evn

"""


# NOTE: Remote server design
# - This script is intentionally lightweight and focused on interaction only:
#   read current_job, update status, open model, call metric function, write result, finalize status.
# - The current "get wall count" is a placeholder metric. It must be abstracted
#   behind a function interface so future metrics can be plugged in with minimal changes.
#   Suggested interface: run_metric(doc, job_payload) -> result_data (dict-like)

CURRENT_JOB_FILENAME = "current_job.sexyDuck"

def _join(*parts):
    return os.path.join(*parts)

def _script_dir():
    """Get script directory - ONLY used to locate current_job.sexyDuck"""
    return os.path.dirname(os.path.abspath(__file__))

def _job_path():
    """Get path to current_job.sexyDuck (always next to this script)"""
    return _join(_script_dir(), CURRENT_JOB_FILENAME)

def _load_json(path):
    try:
        with open(path, 'r') as f:
            return json.load(f)
    except Exception as e:
        return None

def _save_json(path, data):
    with open(path, 'w') as f:
        json.dump(data, f, indent=4)

def _ensure_output_dir(paths):
    """
    Get task output directory from job file paths.
    ALL output files (.sexyDuck results) are written here.
    Path is controlled entirely by current_job.sexyDuck.
    
    Args:
        paths: Dictionary of paths from job file
    """
    if not paths or not paths.get('task_output_dir'):
        raise Exception("task_output_dir not found in job paths - job file must include 'paths' section")
    
    out_dir = paths['task_output_dir']
    if not os.path.exists(out_dir):
        os.makedirs(out_dir)
    return out_dir

def _ensure_debug_dir(paths):
    """
    Get debug directory from job file paths.
    ALL debug files (errors, logs, heartbeat) are written here.
    Path is controlled entirely by current_job.sexyDuck.
    
    Args:
        paths: Dictionary of paths from job file
    """
    if not paths or not paths.get('debug_dir'):
        raise Exception("debug_dir not found in job paths - job file must include 'paths' section")
    
    dbg_dir = paths['debug_dir']
    if not os.path.exists(dbg_dir):
        try:
            os.makedirs(dbg_dir)
        except Exception as e:
            # Can't call _append_debug here as it would cause recursion
            print("Failed to create debug directory: {}".format(traceback.format_exc()))
    return dbg_dir

def _append_debug(message, paths=None):
    """
    Write debug message to debug.txt with multiple fallback locations.
    NEVER raises exceptions - always fails silently after trying all options.
    
    Args:
        message: Debug message to write
        paths: Optional dictionary of paths from job file
    """
    timestamp = datetime.now().isoformat()
    formatted_msg = "[{}] {}\n".format(timestamp, message)
    
    # Try primary location (from job file paths)
    if paths:
        try:
            dbg_dir = _ensure_debug_dir(paths)
            with open(_join(dbg_dir, "debug.txt"), 'a') as f:
                f.write(formatted_msg)
            return  # Success
        except Exception:
            pass  # Try fallback
    
    # Fallback 1: Try script directory
    try:
        script_debug = _join(_script_dir(), "debug_fallback.txt")
        with open(script_debug, 'a') as f:
            f.write(formatted_msg)
        return  # Success
    except Exception:
        pass  # Try next fallback
    
    # Fallback 2: Print to console (last resort)
    try:
        print("[DEBUG] {}".format(message))
    except Exception:
        pass  # Give up silently

def _log_unique_error(error_type, error_msg, tb_text, module_path, paths=None):
    """
    Log unique errors to a structured JSON file for easy analysis.
    Deduplicates by error type - only stores one entry per unique error.
    
    Args:
        error_type: Type/category of error (e.g., "NameError", "FileNotFoundError")
        error_msg: Brief error message
        tb_text: Full traceback text
        module_path: Full path to the module where error occurred
        paths: Optional dictionary of paths from job file
    """
    try:
        # Get debug directory
        if paths:
            dbg_dir = _ensure_debug_dir(paths)
        else:
            dbg_dir = _script_dir()
        
        error_log_path = _join(dbg_dir, "error_registry.json")
        
        # Load existing error registry
        error_registry = {}
        if os.path.exists(error_log_path):
            try:
                with open(error_log_path, 'r') as f:
                    error_registry = json.load(f)
            except Exception:
                # If file is corrupted, start fresh
                error_registry = {}
        
        timestamp = datetime.now().isoformat()
        
        # Check if this error type already exists
        if error_type in error_registry:
            # Update existing entry
            error_registry[error_type]["last_seen"] = timestamp
            error_registry[error_type]["count"] = error_registry[error_type].get("count", 1) + 1
        else:
            # Create new entry
            error_registry[error_type] = {
                "first_seen": timestamp,
                "last_seen": timestamp,
                "count": 1,
                "module_path": module_path,
                "traceback": tb_text,
                "error_message": error_msg
            }
        
        # Write back to file
        with open(error_log_path, 'w') as f:
            json.dump(error_registry, f, indent=2)
    
    except Exception:
        # Never crash due to logging failure
        pass

def _write_heartbeat(stage, paths=None):
    """
    Write heartbeat file to indicate progress.
    This prevents timeout during long-running operations.
    
    Args:
        stage: Current stage description
        paths: Optional dictionary of paths from job file
    """
    try:
        if paths:
            dbg_dir = _ensure_debug_dir(paths)
        else:
            # Fallback to script directory if paths not available
            dbg_dir = _script_dir()
        heartbeat_file = _join(dbg_dir, "_heartbeat.txt")
        with open(heartbeat_file, 'a') as f:
            f.write("[{}] {}\n".format(datetime.now().isoformat(), stage))
    except Exception as e:
        # Non-critical: Don't fail job if heartbeat write fails
        print("Failed to write heartbeat: {}".format(traceback.format_exc()))

# DEPRECATED: Replaced by _log_unique_error() for centralized error tracking
# All errors are now logged to error_registry.json as the single source of truth
# def _write_failure_payload(title, exc, job=None, paths=None):
#     """
#     DEPRECATED: Use _log_unique_error() instead.
#     This function has been removed to consolidate error logging to error_registry.json
#     """
#     pass

def _get_monday_date_prefix():
    """Get Monday of current week as yyyy-mm-dd string (Monday = start of week)"""
    today = datetime.now()
    days_since_monday = today.weekday()  # Monday = 0, Sunday = 6
    monday_of_week = today - timedelta(days=days_since_monday)
    return monday_of_week.strftime("%Y-%m-%d")

def _format_output_filename(job_payload):
    # {yyyy-mm-dd}_hub_project_model.sexyDuck (Monday = start of week)
    ts = _get_monday_date_prefix()
    hub = (job_payload.get("hub_name") or "hub")
    proj = (job_payload.get("project_name") or "project")
    model = (job_payload.get("model_name") or "model")
    return "{}_{}_{}_{}.sexyDuck".format(ts, hub, proj, model)

def _update_job_status(job, new_status, extra_fields=None):
    job["status"] = new_status
    if extra_fields:
        for k in extra_fields:
            job[k] = extra_fields[k]
    _save_json(_job_path(), job)

def _get_app():
    # Optimized: Use only the successful pyrevit.HOST_APP.app path
    from pyrevit import HOST_APP as _HOST_APP # pyright: ignore
    if hasattr(_HOST_APP, 'app') and _HOST_APP.app is not None:
        return _HOST_APP.app
    raise Exception("pyRevit HOST_APP.app not available")

def _validate_file_before_open(model_path, paths=None):
    """
    Validate file exists and is accessible before attempting to open with Revit.
    Provides detailed diagnostics for local files, ACC, and BIM360 files.
    Returns detailed error message if validation fails, None if valid.
    """
    try:
        # Detect file type (local, ACC, BIM360)
        is_acc = "ACCDocs" in model_path or "ACC" in model_path.upper()
        is_bim360 = "BIM360" in model_path or "DC:" in model_path
        is_cloud = is_acc or is_bim360
        
        file_type = "ACC" if is_acc else ("BIM360" if is_bim360 else "Local")
        _append_debug("File type detected: {} - {}".format(file_type, model_path), paths)
        
        # Check if file exists
        if not os.path.exists(model_path):
            if is_cloud:
                return "Cloud file not accessible (may not be synced): {} - Try: 1) Check Autodesk Desktop Connector is running, 2) Verify file is synced locally, 3) Check network connection".format(model_path)
            else:
                return "File does not exist: {} - Verify the file path is correct".format(model_path)
        
        # Check if file is accessible (not locked)
        try:
            with open(model_path, 'rb') as f:
                f.read(1024)  # Try to read 1KB to better detect issues
                _append_debug("File read test successful (1KB)", paths)
        except IOError as e:
            error_code = getattr(e, 'errno', None)
            if error_code == 13 or "Permission" in str(e):
                return "File is locked or permission denied: {} - Possible causes: 1) Another user has file open, 2) Insufficient permissions, 3) Antivirus blocking access".format(model_path)
            else:
                return "File I/O error (code {}): {} - {}".format(error_code, model_path, str(e))
        except Exception as e:
            return "File access error: {} - {}".format(model_path, str(e))
        
        # Check file size (very small files might be corrupted)
        file_size = os.path.getsize(model_path)
        if file_size < 1024:  # Less than 1KB
            return "File too small ({} bytes), likely corrupted or placeholder: {}".format(file_size, model_path)
        
        # For cloud files, add additional diagnostics using BasicFileInfo
        if is_cloud:
            try:
                bfi = DB.BasicFileInfo.Extract(model_path)
                _append_debug("BasicFileInfo extraction successful for cloud file", paths)
                
                # Check if file is workshared and central available
                if hasattr(bfi, 'IsWorkshared') and bfi.IsWorkshared:
                    _append_debug("Cloud file is workshared", paths)
                    if hasattr(bfi, 'CentralPath'):
                        _append_debug("Central path: {}".format(bfi.CentralPath), paths)
                
                # Log format and version for diagnostics
                if hasattr(bfi, 'Format'):
                    _append_debug("File format: {}".format(bfi.Format), paths)
                if hasattr(bfi, 'SavedInVersion'):
                    _append_debug("Saved in Revit version: {}".format(bfi.SavedInVersion), paths)
                    
            except Exception as bfi_ex:
                # BasicFileInfo extraction failed - this is a red flag for cloud files
                return "Cloud file validation failed - BasicFileInfo cannot be extracted: {} - Error: {} - Possible causes: 1) File not fully synced from cloud, 2) File corruption, 3) Network interruption during sync, 4) Autodesk services unavailable".format(model_path, str(bfi_ex))
        
        _append_debug("File validation passed: {} ({} bytes, {})".format(model_path, file_size, file_type), paths)
        return None  # Validation passed
        
    except Exception as e:
        return "File validation error: {} - {} - Unexpected error during validation".format(model_path, str(e))

def get_doc(job_payload, paths=None):
    """
    Obtain a Revit Document by opening the model_path specified in the job payload.
    Returns (doc, must_close):
      - doc: the active document reference (or None on failure)
      - must_close (bool): True if this function opened the document and caller should close it
    
    Args:
        job_payload: Job dictionary with model_path
        paths: Paths dictionary from job file (optional)
    """
    opened_doc = None
    try:
        model_path = job_payload.get('model_path') if isinstance(job_payload, dict) else None
        if not model_path:
            raise Exception("Missing model_path in job payload")
        
        # Validate file before attempting to open
        validation_error = _validate_file_before_open(model_path, paths)
        if validation_error:
            raise Exception("File validation failed: {}".format(validation_error))
        
        app = _get_app()
        _append_debug("Attempting to open file: {}".format(model_path), paths)
        
        # Best-effort version/worksharing probe; do not block open on mismatch here
        bfi = None
        bfi_details = {}
        try:
            bfi = DB.BasicFileInfo.Extract(model_path)
            _append_debug("BasicFileInfo extracted successfully", paths)
            
            # Capture file details for diagnostics
            if hasattr(bfi, 'IsWorkshared'):
                bfi_details['is_workshared'] = str(bfi.IsWorkshared)
            if hasattr(bfi, 'Format'):
                bfi_details['format'] = str(bfi.Format)
            if hasattr(bfi, 'SavedInVersion'):
                bfi_details['saved_version'] = str(bfi.SavedInVersion)
            if hasattr(bfi, 'AllLocalChangesSavedToCentral'):
                bfi_details['all_changes_saved'] = str(bfi.AllLocalChangesSavedToCentral)
                
            _append_debug("File details: {}".format(bfi_details), paths)
        except Exception as ex:
            _append_debug("BasicFileInfo.Extract failed (continuing anyway): {}".format(ex), paths)
            bfi = None
        
        mpath = DB.ModelPathUtils.ConvertUserVisiblePathToModelPath(model_path)
        opts = DB.OpenOptions()
        
        # If the file is workshared, prefer to detach to avoid central locks
        try:
            if bfi is not None and bfi.IsWorkshared:
                opts.DetachFromCentralOption = DB.DetachFromCentralOption.DetachAndPreserveWorksets
                _append_debug("File is workshared, using detach option", paths)
        except Exception as ex:
            _append_debug("Setting DetachFromCentralOption failed: {}".format(ex), paths)
        
        # Configure workset loading based on whether exporter will run
        # If exporter enabled: Open all worksets (sheets need content visible for export)
        # If health metrics only: Close all worksets (faster, more reliable)
        run_exporter = job_payload.get("run_exporter", False)
        if run_exporter:
            # Open all worksets so sheet content is visible for export
            wsconfig = DB.WorksetConfiguration(DB.WorksetConfigurationOption.OpenAllWorksets)
            _append_debug("Exporter enabled - opening ALL worksets for sheet export", paths)
        else:
            # Close all worksets for faster, more reliable health metrics
            wsconfig = DB.WorksetConfiguration(DB.WorksetConfigurationOption.CloseAllWorksets)
            _append_debug("Health metrics only - closing all worksets for performance", paths)
        opts.SetOpenWorksetsConfiguration(wsconfig)
        
        _append_debug("Opening document with Revit API...", paths)
        
        # Enhanced error handling for OpenDocumentFile
        try:
            opened_doc = app.OpenDocumentFile(mpath, opts)
        except Exception as open_ex:
            # Capture detailed error information
            error_type = type(open_ex).__name__
            error_msg = str(open_ex)
            
            # Build detailed diagnostic message
            diagnostic_parts = [
                "OpenDocumentFile failed",
                "Error type: {}".format(error_type),
                "Error message: {}".format(error_msg),
                "File: {}".format(model_path)
            ]
            
            # Add file details if available
            if bfi_details:
                diagnostic_parts.append("File details: {}".format(bfi_details))
            
            # Add specific troubleshooting based on error
            if "COleException" in error_msg or "0x80004005" in error_msg:
                diagnostic_parts.append("DIAGNOSIS: COM/OLE error - often caused by cloud sync issues, file locks, or Autodesk services")
                diagnostic_parts.append("SOLUTIONS: 1) Wait 1-2 minutes for cloud sync to complete, 2) Check Autodesk Desktop Connector status, 3) Verify no other user has file open, 4) Restart Revit if issue persists")
            elif "Permission" in error_msg or "Access" in error_msg:
                diagnostic_parts.append("DIAGNOSIS: Permission/access denied")
                diagnostic_parts.append("SOLUTIONS: 1) Check file permissions, 2) Ensure not open in another session, 3) Verify user has project access")
            elif "corrupt" in error_msg.lower():
                diagnostic_parts.append("DIAGNOSIS: File corruption detected")
                diagnostic_parts.append("SOLUTIONS: 1) Restore from backup, 2) Contact project admin, 3) Try opening in Revit manually")
            
            detailed_error = " | ".join(diagnostic_parts)
            _append_debug(detailed_error, paths)
            raise Exception(detailed_error)
        
        if opened_doc is None:
            error_parts = [
                "OpenDocumentFile returned None - file may be corrupted or incompatible",
                "File: {}".format(model_path)
            ]
            if bfi_details:
                error_parts.append("File details: {}".format(bfi_details))
            raise Exception(" | ".join(error_parts))
        
        _append_debug("Document opened successfully", paths)
        return opened_doc, True
        
    except Exception as e:
        error_msg = "get_doc failed for '{}': {}".format(model_path if 'model_path' in locals() else 'unknown', str(e))
        _append_debug(error_msg, paths)
        
        # Log to structured error registry (single source of truth)
        _log_unique_error(
            error_type="DocumentOpen_Exception",
            error_msg=error_msg,
            tb_text=traceback.format_exc(),
            module_path=__file__,
            paths=paths
        )
        
        raise Exception(error_msg)

def run_metric(doc, job_payload, paths=None):
    """
    Dedicated metric function interface with automatic fallback to mock data.
    - doc: active Revit document
    - job_payload: dict-like payload read from current_job (parsed JSON)
    - paths: Paths dictionary from job file (optional)

    Returns health metrics data.
    
    RESILIENT DESIGN: 
    - Always tries to run real HealthMetric first
    - If ANYTHING fails (import, version, API), automatically falls back to mock data
    - This ensures status transitions complete even when Revit/metrics crash
    """
    
    # Try to run real health metrics
    try:
        if doc is None:
            raise Exception("No active document available - will use mock data")
        
        # Try importing HealthMetric with detailed error handling
        _append_debug("Attempting to import HealthMetric...", paths)
        try:
            from health_metric import HealthMetric
            _append_debug("HealthMetric import successful", paths)
        except ImportError as import_ex:
            raise Exception("Failed to import HealthMetric: {}".format(str(import_ex)))
        except Exception as import_ex:
            raise Exception("Unexpected error importing HealthMetric: {}".format(str(import_ex)))
        
        _append_debug("Attempting to run real HealthMetric.check()...", paths)
        print("STATUS: Running real health metrics...")
        
        try:
            health_metric = HealthMetric(doc)
            _append_debug("HealthMetric instance created successfully", paths)
        except Exception as init_ex:
            raise Exception("Failed to create HealthMetric instance: {}".format(str(init_ex)))
        
        try:
            # HealthMetric.check() can hang on large complex models, so we'll let it run
            # but provide detailed logging to help identify where it might be hanging
            _append_debug("Starting HealthMetric.check() - this may take time on large models...", paths)
            print("STATUS: Running comprehensive health metrics (may take 1-2 minutes for large models)...")
            
            reports = health_metric.check()
            _append_debug("Real HealthMetric completed successfully", paths)
            print("STATUS: Real health metrics completed successfully")
            return reports, None
                
        except Exception as check_ex:
            raise Exception("HealthMetric.check() failed: {}".format(str(check_ex)))
        
    except Exception as ex:
        # AUTOMATIC FALLBACK: Any failure triggers mock data
        error_msg = str(ex)
        tb = traceback.format_exc()
        
        _append_debug("Real HealthMetric failed, falling back to mock data", paths)
        _append_debug("Error: {}".format(error_msg), paths)
        _append_debug("Traceback: {}".format(tb), paths)
        
        print("STATUS: FALLBACK - Real metrics failed, using mock data")
        print("Error: {}".format(error_msg[:200]))  # Truncate long errors
        
        # Return mock data so job can complete successfully
        return {}, error_msg[:500] # Include error for debugging
        

def _format_time(seconds):
    """Format time in readable format"""
    if seconds < 1:
        return "{:.2f} seconds".format(seconds)
    elif seconds < 60:
        return "{} seconds".format(int(round(seconds)))
    elif seconds < 3600:
        minutes = int(seconds // 60)
        secs = int(seconds % 60)
        return "{} minutes {} seconds".format(minutes, secs)
    else:
        hours = int(seconds // 3600)
        minutes = int((seconds % 3600) // 60)
        return "{} hours {} minutes".format(hours, minutes)

def _format_file_size(bytes_size):
    """Format file size in readable format (KB, MB, GB)"""
    if bytes_size < 1024:
        return "{} bytes".format(bytes_size)
    elif bytes_size < 1024 * 1024:
        kb = bytes_size / 1024.0
        return "{:.2f} KB".format(kb)
    elif bytes_size < 1024 * 1024 * 1024:
        mb = bytes_size / (1024.0 * 1024.0)
        return "{:.2f} MB".format(mb)
    else:
        gb = bytes_size / (1024.0 * 1024.0 * 1024.0)
        return "{:.2f} GB".format(gb)

def _get_file_size_info(file_path):
    """Get file size information as both bytes and readable format"""
    try:
        if not file_path or not os.path.exists(file_path):
            return {
                "size_bytes": 0,
                "size_readable": "File not found"
            }
        
        size_bytes = os.path.getsize(file_path)
        return {
            "size_bytes": size_bytes,
            "size_readable": _format_file_size(size_bytes)
        }
    except Exception as e:
        return {
            "size_bytes": 0,
            "size_readable": "Error getting size: {}".format(str(e))
        }

def _handle_job_failure(job, logs, exception, traceback_str, paths=None):
    """
    Handle job failure with comprehensive error reporting
    
    Args:
        job: Job dictionary
        logs: List of log messages
        exception: Exception object
        traceback_str: Traceback string
        paths: Paths dictionary from job file (optional)
    """
    logs.append("Exception: " + str(exception))
    
    # Ensure job is a dict for safe access
    if not isinstance(job, dict):
        job = {
            "job_id": "unknown_job",
            "hub_name": "unknown_hub", 
            "project_name": "unknown_project",
            "model_name": "unknown_model",
            "revit_version": "Unknown",
            "timestamp": datetime.now().isoformat(),
            "status": "failed"
        }
    
    # Update job status with failure info
    try:
        _append_debug("=== JOB STATUS TRANSITION: running -> failed ===", paths)
        print("STATUS: Changing job status from 'running' to 'failed'")
        _update_job_status(job, "failed", {"logs": "\n".join(logs), "error_msg": traceback_str})
        print("STATUS: Job is now 'failed' - See error details in error_registry.json")
    except Exception as e:
        print("Failed to update job status: {}".format(traceback.format_exc()))
    
    # Log to structured error registry (single source of truth)
    try:
        error_type = "JobFailure_{}".format(type(exception).__name__)
        error_msg = "Job {} failed: {}".format(job.get("job_id", "unknown"), str(exception))
        
        _log_unique_error(
            error_type=error_type,
            error_msg=error_msg,
            tb_text=traceback_str,
            module_path=__file__,
            paths=paths
        )
        _append_debug("Error logged to error_registry.json: {}".format(error_type), paths)
    except Exception as ex:
        _append_debug("Failed to log to error registry: {}".format(traceback.format_exc()), paths)
    
    print("Job failed. See error_registry.json for details.")




def revit_remote_server():
    """Main remote server function - NO GLOBAL VARIABLES"""
    logs = []
    job = None
    paths = None  # Local variable, not global
    
    try:
        job_path = _job_path()
        
        # Wait for job file to be available (fix race condition)
        max_wait_time = 10  # seconds
        wait_interval = 0.5  # seconds
        waited_time = 0
        
        while not os.path.exists(job_path) and waited_time < max_wait_time:
            time.sleep(wait_interval)
            waited_time += wait_interval
        
        if not os.path.exists(job_path):
            raise Exception("current_job.sexyDuck not found after {} seconds".format(max_wait_time))

        job = _load_json(job_path)
        if not isinstance(job, dict):
            raise Exception("Invalid job payload structure")
        
        # Extract paths from job file (required)
        if 'paths' not in job or not isinstance(job['paths'], dict):
            raise Exception("Job file must include 'paths' section with task_output_dir and debug_dir")
        
        paths = job['paths']  # Local variable
        
        # Validate that all required paths exist
        required_paths = ['task_output_dir', 'debug_dir']
        for path_key in required_paths:
            path_value = paths.get(path_key)
            if not path_value:
                raise Exception("Required path '{}' not found in job file".format(path_key))
            if not os.path.exists(path_value):
                raise Exception("Path '{}' does not exist: {}".format(path_key, path_value))
        
        logs.append("=== PATH CONFIGURATION ===")
        logs.append("  Database folder: {}".format(paths.get('database_folder', 'None')))
        logs.append("  Task output dir: {}".format(paths.get('task_output_dir', 'None')))
        logs.append("  Debug dir: {}".format(paths.get('debug_dir', 'None')))
        logs.append("  Log dir: {}".format(paths.get('log_dir', 'None')))
        
        # Heartbeat: prove script started and can write to debug directory
        _write_heartbeat("Script started", paths)
        _append_debug("=== JOB STATUS TRANSITION: job_created -> pending ===", paths)
        print("STATUS: Changing job status from 'job_created' to 'pending'")

        # 1) pending (taken)
        _update_job_status(job, "pending")
        _write_heartbeat("Job status: pending", paths)
        logs.append("Job set to pending")
        print("STATUS: Job is now 'pending' - Revit has taken the job")
        _append_debug("=== JOB STATUS TRANSITION: pending -> running ===", paths)
        print("STATUS: Changing job status from 'pending' to 'running'")

        # 2) running
        _update_job_status(job, "running")
        _write_heartbeat("Job status: running", paths)
        logs.append("Job set to running")
        print("STATUS: Job is now 'running' - Beginning document processing")

        # 3) get document and execute metric with timing
        _write_heartbeat("Opening document...", paths)
        _append_debug("About to open document: {}".format(job.get('model_path', 'None')), paths)
        
        # Try to open document - if it fails, doc will be None and run_metric will use mock data
        doc = None
        must_close = False
        try:
            doc, must_close = get_doc(job, paths)
            _write_heartbeat("Document opened successfully", paths)
        except Exception as doc_ex:
            _write_heartbeat("Document open failed - will use mock data", paths)
            tb_text = traceback.format_exc()
            _append_debug("Document open failed: {}".format(tb_text), paths)
            # Log to structured error registry
            error_type = "DocumentOpen_" + type(doc_ex).__name__
            _log_unique_error(
                error_type=error_type,
                error_msg=str(doc_ex),
                tb_text=tb_text,
                module_path=__file__,
                paths=paths
            )
            print("STATUS: Document open failed - metrics will use mock data")
            # Don't raise - let run_metric handle the None doc and return mock data
        
        begin_time = time.time()
        
        # Initialize variables in case of early exception
        result = None
        error_msg = None
        
        try:
            _write_heartbeat("Running health metrics...", paths)
            result, error_msg = run_metric(doc, job, paths)
            if result is None:
                _write_heartbeat("Health metrics completed with error", paths)
                _append_debug("Health metrics completed with error: {}".format(error_msg), paths)
                print("STATUS: Health metrics completed with error: {}".format(error_msg))
            else:
                _write_heartbeat("Health metrics completed", paths)
        except Exception as e:
            tb_text = traceback.format_exc()
            _append_debug("Health metrics exception: {}".format(tb_text), paths)
            # Log to structured error registry
            error_type = type(e).__name__
            _log_unique_error(
                error_type=error_type,
                error_msg=str(e),
                tb_text=tb_text,
                module_path=__file__,
                paths=paths
            )
            raise

        # Get file size information
        model_path = job.get('model_path', '')
        file_size_info = _get_file_size_info(model_path)

        # Try to run model exports (completely isolated from health metrics)
        # Export is controlled by run_exporter flag in job (set based on computer configuration)
        export_data = None
        export_error = None
        run_exporter = job.get("run_exporter", False)  # Default to False for backward compatibility
        
        if run_exporter:
            # Check if document is valid before attempting exports
            if doc is None:
                print("WARNING: Document is null - skipping model exports")
                export_data = {
                    "export_status": "skipped",
                    "error": "Document failed to open - exports skipped",
                    "summary": {
                        "total_sheets": 0,
                        "successful_sheets": 0,
                        "failed_sheets": 0,
                        "partial_failures": 0
                    }
                }
                _append_debug("Exporter skipped - document is null", paths)
            else:
                _write_heartbeat("Starting model exports...", paths)
                print("STATUS: Running model exporter (computer configured for both health metric + exporter)")
                try:
                    from model_exporter import ModelExporter
                    
                    # Create export output directory
                    # task_output_dir now points to model-specific directory: task_output/{project}/{model}/
                    model_output_dir = paths.get('task_output_dir')
                    export_base_path = _join(model_output_dir, "exports")
                    if not os.path.exists(export_base_path):
                        os.makedirs(export_base_path)
                    
                    exporter = ModelExporter(doc, export_base_path)
                    export_data = exporter.export_all()
                
                    print("STATUS: Model export completed - {}/{} sheets successful".format(
                        export_data["summary"]["successful_sheets"],
                        export_data["summary"]["total_sheets"]
                    ))
                    _write_heartbeat("Model exports completed", paths)
                except Exception as e:
                    # Export failure does NOT affect health metrics
                    export_error = str(e)
                    tb_text = traceback.format_exc()
                    export_data = {
                        "export_status": "failed",
                        "error": str(e),
                        "traceback": tb_text
                    }
                    print("WARNING: Model export failed: {}".format(str(e)))
                    _append_debug("Model export failed: {}".format(tb_text), paths)
                    # Log to structured error registry
                    error_type = "ModelExporter_" + type(e).__name__
                    _log_unique_error(
                        error_type=error_type,
                        error_msg=str(e),
                        tb_text=tb_text,
                        module_path="model_exporter",
                        paths=paths
                    )
                    _write_heartbeat("Model exports failed (continuing with health metrics)", paths)
                    # Continue to write output - health metrics are still valid
        else:
            print("STATUS: Skipping model exporter (computer configured for health metric only)")
            _append_debug("Exporter skipped based on computer configuration (run_exporter=False)", paths)

        # Close document AFTER both health metrics and exports complete
        try:
            if must_close and doc is not None:
                _write_heartbeat("Closing document...", paths)
                doc.Close(False)
                _write_heartbeat("Document closed", paths)
        except Exception as e:
            _append_debug("Failed to close document: {}".format(traceback.format_exc()), paths)

        # Calculate total execution time (includes health metrics + exports)
        execution_time = time.time() - begin_time

        # 4) write output file
        _write_heartbeat("Writing output file...", paths)
        out_name = _format_output_filename(job)
        
        # task_output_dir now points to model-specific directory: task_output/{project}/{model}/
        # Save .sexyDuck file directly in model directory (no additional project folder)
        model_output_dir = _ensure_output_dir(paths)
        out_path = _join(model_output_dir, out_name)
        output_payload = {
            "job_metadata": {
                "job_id": job.get("job_id"),
                "hub_name": job.get("hub_name"),
                "project_name": job.get("project_name"),
                "model_name": job.get("model_name"),
                "model_file_size_bytes": file_size_info["size_bytes"],
                "model_file_size_readable": file_size_info["size_readable"],
                "revit_version": job.get("revit_version"),
                "timestamp": datetime.now().isoformat(),
                "execution_time_seconds": round(execution_time, 2),
                "execution_time_readable": _format_time(execution_time)
            },
            "health_metric_result": result,  # Renamed from result_data
            "export_data": export_data,      # New field for export metadata
            "status": "completed" + (" with error" if error_msg else "")
        }
        _save_json(out_path, output_payload)
        logs.append("Output saved: " + out_path)
        _write_heartbeat("Output file written", paths)

        # 5) mark completed (success)
        _append_debug("=== JOB STATUS TRANSITION: running -> completed ===", paths)
        print("STATUS: Changing job status from 'running' to 'completed'")
        _update_job_status(job, "completed", {"result_data": result})
        _write_heartbeat("Job completed successfully", paths)
        logs.append("Job completed")
        print("STATUS: Job is now 'completed' - Remote server finished successfully")
    except Exception as e:
        tb = traceback.format_exc()
        _append_debug("EXCEPTION: {}".format(str(e)), paths)
        _append_debug("TRACEBACK: {}".format(tb), paths)
        # Log to structured error registry
        error_type = "Pipeline_" + type(e).__name__
        _log_unique_error(
            error_type=error_type,
            error_msg=str(e),
            tb_text=tb,
            module_path=__file__,
            paths=paths
        )
        _handle_job_failure(job, logs, e, tb, paths)



def _emergency_error_log(error_title, error_obj):
    """
    EMERGENCY logging when everything else fails.
    First tries error_registry.json (single source of truth).
    Only creates txt files if error_registry.json is completely inaccessible.
    Used for catastrophic failures before paths are initialized.
    """
    timestamp = datetime.now().isoformat()
    tb = traceback.format_exc()
    
    # Priority 1: Try to write to error_registry.json (single source of truth)
    try:
        error_type = "Emergency_{}".format(error_title.replace(" ", "_"))
        _log_unique_error(
            error_type=error_type,
            error_msg="EMERGENCY: {} - {}".format(error_title, str(error_obj)),
            tb_text=tb,
            module_path=__file__,
            paths=None  # No paths available in emergency
        )
        print("EMERGENCY error logged to error_registry.json: {}".format(error_type))
        return  # Success - no need for txt files
    except Exception:
        pass  # error_registry.json not accessible, try txt files
    
    # Fallback 1: Script directory txt file (only if error_registry.json fails)
    try:
        emergency_file = _join(_script_dir(), "EMERGENCY_ERROR_{}.txt".format(timestamp.replace(":", "-")))
        with open(emergency_file, 'w') as f:
            f.write("="*80 + "\n")
            f.write("EMERGENCY ERROR LOG - Remote Server Catastrophic Failure\n")
            f.write("(error_registry.json was not accessible)\n")
            f.write("="*80 + "\n")
            f.write("Title: {}\n".format(error_title))
            f.write("Timestamp: {}\n".format(timestamp))
            f.write("Error: {}\n".format(str(error_obj)))
            f.write("\n" + "="*80 + "\n")
            f.write("FULL TRACEBACK:\n")
            f.write("="*80 + "\n")
            f.write(tb)
            f.write("\n" + "="*80 + "\n")
        print("EMERGENCY error logged to txt (error_registry.json unavailable): {}".format(emergency_file))
        return  # Success
    except Exception:
        pass  # Try console as last resort
    
    # Fallback 2: Console output (absolute last resort)
    try:
        print("\n" + "="*80)
        print("!!! CATASTROPHIC ERROR IN REMOTE SERVER !!!")
        print("="*80)
        print("Title: {}".format(error_title))
        print("Error: {}".format(str(error_obj)))
        print("\nFull Traceback:")
        print(tb)
        print("="*80 + "\n")
    except Exception:
        pass


################## main code below #####################
if __name__ == "__main__":
    # TOP-LEVEL EXCEPTION HANDLER: Catch even catastrophic failures
    try:
        revit_remote_server()
    except Exception as catastrophic_error:
        # This catches failures that happen before paths are initialized
        # or failures in the main exception handler itself
        _emergency_error_log("CATASTROPHIC_FAILURE", catastrophic_error)
        # Re-raise so pyRevit can capture it
        raise







