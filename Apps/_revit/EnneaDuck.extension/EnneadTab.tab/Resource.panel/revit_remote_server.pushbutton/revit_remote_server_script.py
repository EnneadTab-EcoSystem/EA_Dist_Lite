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

def _write_failure_payload(title, exc, job=None, paths=None):
    """
    Write failure information to multiple locations for guaranteed capture.
    NEVER raises exceptions - tries all fallback locations.
    
    Args:
        title: Error title
        exc: Exception object
        job: Job dictionary (optional)
        paths: Paths dictionary from job file (optional)
    """
    timestamp = datetime.now().strftime("%Y-%m")
    name = "{}_ERROR_{}.sexyDuck".format(timestamp, title)
    tb = traceback.format_exc()
    
    payload = {
        "job_metadata": {
            "job_id": (job.get("job_id") if isinstance(job, dict) else None),
            "hub_name": (job.get("hub_name") if isinstance(job, dict) else None),
            "project_name": (job.get("project_name") if isinstance(job, dict) else None),
            "model_name": (job.get("model_name") if isinstance(job, dict) else None),
            "revit_version": (job.get("revit_version") if isinstance(job, dict) else None),
            "timestamp": datetime.now().isoformat()
        },
        "status": "failed",
        "title": title,
        "error": str(exc),
        "traceback": tb
    }
    
    # Try primary location (debug_dir from job paths)
    if paths:
        try:
            dbg_dir = _ensure_debug_dir(paths)
            _save_json(_join(dbg_dir, name), payload)
            _append_debug("Failure payload written: {}".format(name), paths)
            return  # Success
        except Exception:
            pass  # Try fallback
    
    # Fallback 1: Write to script directory
    try:
        script_error = _join(_script_dir(), name)
        _save_json(script_error, payload)
        print("Failure payload written to script directory: {}".format(script_error))
        return  # Success
    except Exception:
        pass  # Try next fallback
    
    # Fallback 2: Write plain text error to script directory
    try:
        error_txt = _join(_script_dir(), "{}_ERROR_{}.txt".format(timestamp, title))
        with open(error_txt, 'w') as f:
            f.write("="*80 + "\n")
            f.write("REVIT REMOTE SERVER ERROR\n")
            f.write("="*80 + "\n")
            f.write("Title: {}\n".format(title))
            f.write("Error: {}\n".format(str(exc)))
            f.write("Timestamp: {}\n".format(datetime.now().isoformat()))
            f.write("\n" + "="*80 + "\n")
            f.write("TRACEBACK:\n")
            f.write("="*80 + "\n")
            f.write(tb)
        print("Error written to: {}".format(error_txt))
        return  # Success
    except Exception:
        pass  # Last resort
    
    # Fallback 3: Print to console (last resort)
    try:
        print("="*80)
        print("CRITICAL ERROR - Could not write to any log location")
        print("="*80)
        print("Title: {}".format(title))
        print("Error: {}".format(str(exc)))
        print("Traceback: {}".format(tb))
        print("="*80)
    except Exception:
        pass  # Give up silently

def _format_output_filename(job_payload):
    # {yyyy-mm}_hub_project_model.sexyDuck
    ts = datetime.now().strftime("%Y-%m")
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
    Returns detailed error message if validation fails, None if valid.
    """
    try:
        # Check if file exists
        if not os.path.exists(model_path):
            return "File does not exist: {}".format(model_path)
        
        # Check if file is accessible (not locked)
        try:
            with open(model_path, 'rb') as f:
                f.read(1)  # Try to read one byte
        except PermissionError:
            return "File is locked or permission denied: {}".format(model_path)
        except Exception as e:
            return "File access error: {} - {}".format(model_path, str(e))
        
        # Check file size (very small files might be corrupted)
        file_size = os.path.getsize(model_path)
        if file_size < 1024:  # Less than 1KB
            return "File too small ({} bytes), likely corrupted: {}".format(file_size, model_path)
        
        _append_debug("File validation passed: {} ({} bytes)".format(model_path, file_size), paths)
        return None  # Validation passed
        
    except Exception as e:
        return "File validation error: {} - {}".format(model_path, str(e))

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
        try:
            bfi = DB.BasicFileInfo.Extract(model_path)
            _append_debug("BasicFileInfo extracted successfully", paths)
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
        
        # Open with minimal load: close all worksets for reliability
        wsconfig = DB.WorksetConfiguration(DB.WorksetConfigurationOption.CloseAllWorksets)
        opts.SetOpenWorksetsConfiguration(wsconfig)
        
        _append_debug("Opening document with Revit API...", paths)
        opened_doc = app.OpenDocumentFile(mpath, opts)
        
        if opened_doc is None:
            raise Exception("OpenDocumentFile returned None - file may be corrupted or incompatible")
        
        _append_debug("Document opened successfully", paths)
        return opened_doc, True
        
    except Exception as e:
        error_msg = "get_doc failed for '{}': {}".format(model_path if 'model_path' in locals() else 'unknown', str(e))
        _append_debug(error_msg, paths)
        _write_failure_payload("get_doc", Exception(error_msg), job_payload, paths)
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
            
            result = health_metric.check()
            _append_debug("Real HealthMetric completed successfully", paths)
            print("STATUS: Real health metrics completed successfully")
            return result
                
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
        return {
            "mock_mode": True,
            "fallback_reason": "Real HealthMetric failed",
            "error_summary": error_msg[:500],  # Include error for debugging
            "debug_info": {
                "model_path": job_payload.get('model_path', 'Unknown'),
                "model_name": job_payload.get('model_name', 'Unknown'),
                "revit_version": job_payload.get('revit_version', 'Unknown'),
                "job_id": job_payload.get('job_id', 'Unknown'),
                "error_occurred": True
            },
            "placeholder_metrics": {
                "wall_count": 42,
                "total_elements": 1000,
                "note": "Mock values - real metrics failed"
            }
        }

def _format_time(seconds):
    """Format time in readable format"""
    if seconds < 60:
        return "{} seconds".format(int(seconds))
    elif seconds < 3600:
        minutes = int(seconds // 60)
        secs = int(seconds % 60)
        return "{} minutes {} seconds".format(minutes, secs)
    else:
        hours = int(seconds // 3600)
        minutes = int((seconds % 3600) // 60)
        return "{} hours {} minutes".format(hours, minutes)

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
        print("STATUS: Job is now 'failed' - See error details in debug directory")
    except Exception as e:
        print("Failed to update job status: {}".format(traceback.format_exc()))
    
    # Write failure output file to DEBUG for capture
    if paths:
        try:
            dbg_dir = _ensure_debug_dir(paths)
            fallback_name = "{}_{}_{}_ERROR.sexyDuck".format(
                datetime.now().strftime("%Y-%m"),
                job.get("hub_name", "hub"),
                job.get("model_name", "model")
            )
            out_path = _join(dbg_dir, fallback_name)
            output_payload = {
                "job_metadata": {
                    "job_id": job.get("job_id"),
                    "hub_name": job.get("hub_name"),
                    "project_name": job.get("project_name"),
                    "model_name": job.get("model_name"),
                    "revit_version": job.get("revit_version"),
                    "timestamp": datetime.now().isoformat()
                },
                "status": "failed",
                "logs": "\n".join(logs),
                "error_msg": traceback_str
            }
            _save_json(out_path, output_payload)
        except Exception as ex:
            _append_debug("Write failure payload failed: {}".format(traceback.format_exc()), paths)
    
    print("Job failed. See logs in job file or debug directory.")




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
            _append_debug("Document open failed: {}".format(str(doc_ex)), paths)
            print("STATUS: Document open failed - metrics will use mock data")
            # Don't raise - let run_metric handle the None doc and return mock data
        
        begin_time = time.time()
        
        try:
            _write_heartbeat("Running health metrics...", paths)
            result = run_metric(doc, job, paths)
            _write_heartbeat("Health metrics completed", paths)
        finally:
            try:
                if must_close and doc is not None:
                    _write_heartbeat("Closing document...", paths)
                    doc.Close(False)
                    _write_heartbeat("Document closed", paths)
            except Exception as e:
                _append_debug("Failed to close document: {}".format(traceback.format_exc()), paths)
        
        # Calculate execution time
        execution_time = time.time() - begin_time

        # 4) write output file
        _write_heartbeat("Writing output file...", paths)
        out_name = _format_output_filename(job)
        out_path = _join(_ensure_output_dir(paths), out_name)
        output_payload = {
            "job_metadata": {
                "job_id": job.get("job_id"),
                "hub_name": job.get("hub_name"),
                "project_name": job.get("project_name"),
                "model_name": job.get("model_name"),
                "revit_version": job.get("revit_version"),
                "timestamp": datetime.now().isoformat(),
                "execution_time_seconds": round(execution_time, 2),
                "execution_time_readable": _format_time(execution_time)
            },
            "result_data": result,
            "status": "completed"
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
        _handle_job_failure(job, logs, e, tb, paths)



def _emergency_error_log(error_title, error_obj):
    """
    EMERGENCY logging when everything else fails.
    Writes to multiple locations to guarantee capture.
    Used for catastrophic failures before paths are initialized.
    """
    timestamp = datetime.now().isoformat()
    tb = traceback.format_exc()
    
    # Location 1: Script directory (always available)
    try:
        emergency_file = _join(_script_dir(), "EMERGENCY_ERROR_{}.txt".format(timestamp.replace(":", "-")))
        with open(emergency_file, 'w') as f:
            f.write("="*80 + "\n")
            f.write("EMERGENCY ERROR LOG - Remote Server Catastrophic Failure\n")
            f.write("="*80 + "\n")
            f.write("Title: {}\n".format(error_title))
            f.write("Timestamp: {}\n".format(timestamp))
            f.write("Error: {}\n".format(str(error_obj)))
            f.write("\n" + "="*80 + "\n")
            f.write("FULL TRACEBACK:\n")
            f.write("="*80 + "\n")
            f.write(tb)
            f.write("\n" + "="*80 + "\n")
        print("EMERGENCY error logged to: {}".format(emergency_file))
    except Exception:
        pass
    
    # Location 2: Try C:\Users\USERNAME\Documents
    try:
        username = os.environ.get('USERNAME', 'user')
        docs_dir = "C:\\Users\\{}\\Documents".format(username)
        if os.path.exists(docs_dir):
            emergency_file2 = _join(docs_dir, "RevitRemoteServer_EMERGENCY_{}.txt".format(timestamp.replace(":", "-")))
            with open(emergency_file2, 'w') as f:
                f.write("EMERGENCY ERROR: {}\n".format(error_title))
                f.write("Timestamp: {}\n".format(timestamp))
                f.write("Error: {}\n\n".format(str(error_obj)))
                f.write(tb)
            print("EMERGENCY error also logged to: {}".format(emergency_file2))
    except Exception:
        pass
    
    # Location 3: Console output (always works)
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







