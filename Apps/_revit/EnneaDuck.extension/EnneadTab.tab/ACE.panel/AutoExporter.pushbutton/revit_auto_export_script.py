#!/usr/bin/python
# -*- coding: utf-8 -*-

"""
AutoExporter Revit Script

Runs INSIDE Revit (IronPython 2.7) to perform automated model exports.
Opens cloud models, exports files (PDF/DWG/JPG), sends notifications, and closes Revit.

This script is launched by the orchestrator (runs outside Revit) via pyRevit CLI.
Configuration is loaded from current_job_payload.json which specifies the active config file.

Process:
1. Read job payload to get active config
2. Open cloud model specified in config (detached, audit, all worksets)
3. Filter sheets based on export parameter
4. Export to dated folders (PDF/DWG/JPG)
5. Send email notification with export summary
6. Write job status to current_job_status.json
7. Close Revit cleanly

Status Stages:
- running: Script started
- exporting: Performing file exports
- post_export: Sending notifications
- completed: Job finished successfully
- failed: Error occurred (with error message)


"""

__doc__ = "AutoExporter - Opens cloud model, exports files, sends notifications, closes Revit"
__title__ = "Amazing Auto Export"
__context__ = "zero-doc"

# Basic imports
import time
import os
import sys
import traceback
from datetime import datetime

# Ensure EnneadTab lib is in sys.path
# Load paths from config.json
import config_loader
path_settings = config_loader.get_path_settings()
lib_paths = path_settings.get('lib_paths', [])

# Try each lib path in order
lib_path = None
for candidate_path in lib_paths:
    if os.path.exists(candidate_path):
        lib_path = candidate_path
        break

# If no valid path found, use first as default
if not lib_path and lib_paths:
    lib_path = lib_paths[0]

if lib_path and lib_path not in sys.path:
    sys.path.insert(0, lib_path)

# Import proDUCKtion (optional)
try:
    import proDUCKtion # pyright: ignore 
    proDUCKtion.validify()
except:
    pass

# Import required modules
from EnneadTab import ERROR_HANDLE, LOG
from EnneadTab.REVIT import REVIT_APPLICATION
from Autodesk.Revit import DB # pyright: ignore 
import System # pyright: ignore 
from pyrevit.revit import ErrorSwallower # pyright: ignore
import revit_export_logic
import revit_post_export_logic

# Load configuration from config.json
MODEL_DATA = config_loader.get_model_data()
PROJECT_INFO = config_loader.get_project_info()
HEARTBEAT_SETTINGS = config_loader.get_heartbeat_settings()

# Get job information
JOB_ID = config_loader.get_current_job_id()
CONFIG_NAME = config_loader.get_current_config_name()


def write_heartbeat(step, message, is_error=False, reset=False):
    """Write a heartbeat entry with timestamp to track script execution"""
    try:
        if not HEARTBEAT_SETTINGS.get('enabled', True):
            return None
        
        folder_name = HEARTBEAT_SETTINGS.get('folder_name', 'heartbeat')
        date_format = HEARTBEAT_SETTINGS.get('date_format', '%Y%m%d')
        
        heartbeat_dir = os.path.join(os.path.dirname(__file__), folder_name)
        if not os.path.exists(heartbeat_dir):
            os.makedirs(heartbeat_dir)
        
        date_stamp = datetime.now().strftime(date_format)
        heartbeat_file = os.path.join(heartbeat_dir, "heartbeat_{}.log".format(date_stamp))
        
        timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        status = "ERROR" if is_error else "OK"
        
        if reset:
            with open(heartbeat_file, 'w') as f:
                f.write("="*80 + "\n")
                f.write("AUTO EXPORT HEARTBEAT LOG\n")
                f.write("="*80 + "\n")
        
        with open(heartbeat_file, 'a') as f:
            f.write("[{}] [STEP {}] [{}] {}\n".format(timestamp, step, status, message))
        
        return heartbeat_file
    except Exception as e:
        print("Heartbeat error: {}".format(e))
        return None


def open_heartbeat_file(heartbeat_file):
    """Open the heartbeat log file"""
    if heartbeat_file and os.path.exists(heartbeat_file):
        os.startfile(heartbeat_file)


def write_job_status(status, error=None, exports=None, traceback_info=None):
    """Write job status to current_job_status.json
    
    Args:
        status: Job status ("running", "exporting", "post_export", "completed", "failed")
        error: Error message if failed
        exports: Dictionary with export counts (pdf, dwg, jpg)
        traceback_info: Full traceback string for debugging
    """
    try:
        status_file = os.path.join(os.path.dirname(__file__), "current_job_status.json")
        
        status_data = {
            "job_id": JOB_ID,
            "config": CONFIG_NAME,
            "status": status,
            "updated_at": datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        }
        
        if error:
            status_data["error"] = str(error)
        
        if traceback_info:
            status_data["traceback"] = traceback_info
        
        if exports:
            status_data["exports"] = exports
        
        if status == "completed":
            status_data["completed_at"] = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        
        # Write atomically via temp file
        temp_file = status_file + ".tmp"
        with open(temp_file, 'w') as f:
            import json
            json.dump(status_data, f, indent=2)
        
        if os.path.exists(status_file):
            os.remove(status_file)
        os.rename(temp_file, status_file)
        
    except Exception as e:
        print("Failed to write job status: {}".format(e))


def tuple_to_model_path(data_dict):
    """Convert model data dictionary to ModelPath object"""
    if not data_dict:
        return None
    
    project_guid = data_dict.get("project_guid")
    file_guid = data_dict.get("model_guid")
    region = data_dict.get("region")
    
    # Build list of candidate regions
    candidate_regions = [region] if region else []
    candidate_regions.extend(REVIT_APPLICATION.get_known_regions())
    
    # Remove duplicates
    seen = set()
    candidate_regions = [x for x in candidate_regions if x and not (x in seen or seen.add(x))]
    
    # Try each region
    for reg in candidate_regions:
        try:
            cloud_path = DB.ModelPathUtils.ConvertCloudGUIDsToCloudPath(
                reg,
                System.Guid(project_guid),
                System.Guid(file_guid)
            )
            return cloud_path
        except:
            continue
    
    print("Failed to build cloud path")
    return None


def open_and_activate_doc(doc_name, model_data, heartbeat_callback=None):
    """Open and activate a document by name with detailed progress tracking"""
    if doc_name not in model_data:
        error_msg = "[{}] not found in model data".format(doc_name)
        print(error_msg)
        if heartbeat_callback:
            heartbeat_callback("2.1", error_msg, is_error=True)
        return None
    
    # Build cloud path with detailed logging
    if heartbeat_callback:
        heartbeat_callback("2.1", "Building cloud path for model [{}]".format(doc_name))
    
    print("Building cloud path for model: {}".format(doc_name))
    model_info = model_data[doc_name]
    print("  Project GUID: {}".format(model_info.get('project_guid', 'N/A')))
    print("  Model GUID: {}".format(model_info.get('model_guid', 'N/A')))
    print("  Region: {}".format(model_info.get('region', 'N/A')))
    
    cloud_path = tuple_to_model_path(model_data[doc_name])
    if not cloud_path:
        error_msg = "Failed to build cloud path"
        if heartbeat_callback:
            heartbeat_callback("2.2", error_msg, is_error=True)
        return None
    
    if heartbeat_callback:
        heartbeat_callback("2.2", "Cloud path created successfully")
    
    # Setup open options - match standard "open doc silently" behavior (no detach, default worksets)
    if heartbeat_callback:
        heartbeat_callback("2.3", "Configuring open options (standard open behavior)")
    
    open_options = DB.OpenOptions()
    
    print("Opening document using standard options (no detach)...")
    print("  This may take several minutes for large cloud models...")
    
    if heartbeat_callback:
        heartbeat_callback("2.4", "Initiating document download and open from ACC (this may take 3-10 min for large models)")
    
    # Try primary method
    try:
        if heartbeat_callback:
            heartbeat_callback("2.5", "Attempting OpenAndActivateDocument...")
        print("  Attempting OpenAndActivateDocument...")
        
        doc = REVIT_APPLICATION.get_uiapp().OpenAndActivateDocument(cloud_path, open_options, False)
        
        if heartbeat_callback:
            heartbeat_callback("2.6", "Document opened successfully via OpenAndActivateDocument")
        print("  Document opened successfully!")
        return doc
    except Exception as e:
        error_msg = "OpenAndActivateDocument failed: {}".format(str(e))
        print("  {}".format(error_msg))
        if heartbeat_callback:
            heartbeat_callback("2.5", "{}, trying alternative method...".format(error_msg))
        
        # Try fallback method
        try:
            if heartbeat_callback:
                heartbeat_callback("2.6", "Attempting OpenDocumentFile...")
            print("  Attempting OpenDocumentFile (fallback)...")
            
            doc = REVIT_APPLICATION.get_app().OpenDocumentFile(cloud_path, open_options)
            
            if doc:
                if heartbeat_callback:
                    heartbeat_callback("2.7", "Document opened via OpenDocumentFile, activating...")
                print("  Document opened via fallback, activating...")
                REVIT_APPLICATION.open_and_active_project(cloud_path)
                
                if heartbeat_callback:
                    heartbeat_callback("2.8", "Document opened and activated successfully via fallback method")
                print("  Document activated successfully!")
                return doc
            else:
                error_msg = "OpenDocumentFile returned None"
                print("  {}".format(error_msg))
                if heartbeat_callback:
                    heartbeat_callback("2.7", error_msg, is_error=True)
                return None
        except Exception as e2:
            error_msg = "All open methods failed. Final error: {}".format(str(e2))
            print("  {}".format(error_msg))
            if heartbeat_callback:
                heartbeat_callback("2.7", error_msg, is_error=True)
            return None


def _log_link_guard(message, exc=None):
    """Standardized logging for link guard diagnostics."""
    if exc:
        print("[LinkGuard] {} | {}".format(message, exc))
    else:
        print("[LinkGuard] {}".format(message))


def _get_link_type_name(link_type):
    """Return a readable Revit link type name."""
    try:
        param = link_type.get_Parameter(DB.BuiltInParameter.SYMBOL_NAME_PARAM)
        if param:
            value = param.AsString()
            if value:
                return value
    except Exception as param_error:
        _log_link_guard("Failed reading link type parameter for name fallback", param_error)
    
    try:
        return link_type.Name
    except Exception as name_error:
        _log_link_guard("Failed reading link type Name property", name_error)
    
    try:
        element_id = getattr(link_type, "Id", None)
        if element_id:
            id_value = None
            
            if hasattr(element_id, "Value"):
                try:
                    id_value = element_id.Value
                except Exception as value_error:
                    _log_link_guard("Failed reading ElementId.Value for link type name", value_error)
                    id_value = None
            
            if id_value is None and hasattr(element_id, "IntegerValue"):
                try:
                    id_value = element_id.IntegerValue
                except Exception as int_error:
                    _log_link_guard("Failed reading ElementId.IntegerValue for link type name", int_error)
                    id_value = None
            
            if id_value is not None:
                return "RevitLinkType-{}".format(id_value)
    except Exception as id_error:
        _log_link_guard("Failed building link type fallback name from ElementId", id_error)
    
    return "RevitLinkType"


def _attempt_reload_link_type(doc, link_type, link_name):
    """Reload a single Revit link type.
    
    Note:
        Some Revit environments do not allow link reload to be wrapped in an
        explicit Transaction because Reload() manages its own internal
        transaction. Attempting to wrap it can trigger errors like:
        'Operation is not permitted when there is any open sub-transaction,
        transaction, or transaction group.'
        
        To avoid nested transaction conflicts, call Reload() directly and let
        Revit handle the transaction boundaries internally.
    """
    try:
        link_type.Reload()
    except Exception as reload_error:
        # Surface the original error to the caller and log for diagnostics
        _log_link_guard(
            "Link reload failed for [{}]".format(link_name),
            reload_error
        )
        raise


def _wait_for_link_to_load(doc, link_type, deadline, poll_interval=5):
    """Wait until a link reports as loaded or deadline reached."""
    while time.time() < deadline:
        if DB.RevitLinkType.IsLoaded(doc, link_type.Id):
            return True
        time.sleep(poll_interval)
    return DB.RevitLinkType.IsLoaded(doc, link_type.Id)


def ensure_all_links_loaded(doc, timeout_minutes=10, heartbeat_callback=None):
    """Ensure every Revit link type in the document is loaded before export."""
    timeout_minutes = timeout_minutes or 0
    if timeout_minutes <= 0:
        timeout_minutes = 10
    
    link_types = list(DB.FilteredElementCollector(doc).OfClass(DB.RevitLinkType))
    total_links = len(link_types)
    
    if total_links == 0:
        if heartbeat_callback:
            heartbeat_callback("3.1", "No Revit links found in document (nothing to reload)")
        return {"total": 0, "already_loaded": 0, "reloaded": 0}
    
    already_loaded = []
    reloaded = []
    deadline = time.time() + (timeout_minutes * 60)
    
    if heartbeat_callback:
        heartbeat_callback("3.1", "Checking {} Revit link(s) before export".format(total_links))
    
    for idx, link_type in enumerate(link_types):
        link_name = _get_link_type_name(link_type)
        stage = "3.{}".format(idx + 2)
        
        try:
            is_loaded = DB.RevitLinkType.IsLoaded(doc, link_type.Id)
        except Exception as state_error:
            if heartbeat_callback:
                heartbeat_callback(stage, "Unable to determine state for [{}]: {}".format(link_name, state_error), is_error=True)
            raise
        
        if is_loaded:
            already_loaded.append(link_name)
            continue
        
        if heartbeat_callback:
            heartbeat_callback(stage, "Reloading Revit link [{}] ({} of {})".format(link_name, idx + 1, total_links))
        
        try:
            _attempt_reload_link_type(doc, link_type, link_name)
        except Exception as reload_error:
            error_msg = "Reload failed for [{}]: {}".format(link_name, reload_error)
            if heartbeat_callback:
                heartbeat_callback(stage, error_msg, is_error=True)
            raise Exception(error_msg)
        
        if heartbeat_callback:
            heartbeat_callback(stage, "Waiting for [{}] to finish loading".format(link_name))
        
        if not _wait_for_link_to_load(doc, link_type, deadline):
            error_msg = "Link [{}] did not finish loading before timeout ({} min)".format(link_name, timeout_minutes)
            if heartbeat_callback:
                heartbeat_callback(stage, error_msg, is_error=True)
            raise Exception(error_msg)
        
        reloaded.append(link_name)
    
    summary_msg = "Revit link check complete: {} total / {} already loaded / {} reloaded".format(
        total_links,
        len(already_loaded),
        len(reloaded)
    )
    if heartbeat_callback:
        heartbeat_callback("3.{}".format(total_links + 2), summary_msg)
    print(summary_msg)
    
    return {
        "total": total_links,
        "already_loaded": len(already_loaded),
        "reloaded": len(reloaded)
    }


@LOG.log(__file__, __title__)
@ERROR_HANDLE.try_catch_error()
def auto_export():
    # Initialize job status
    write_job_status("running")
    
    # Force reload config to get the current job's configuration
    # This is critical because the orchestrator updates current_job_payload.json between jobs
    config_loader.load_config(force_reload=True)
    
    # Reload all config data with the new config
    model_data = config_loader.get_model_data()
    project_info = config_loader.get_project_info()
    job_id = config_loader.get_current_job_id()
    config_name = config_loader.get_current_config_name()
    
    # Initialize heartbeat log
    heartbeat_file = write_heartbeat("START", "Auto export started [Job: {}]".format(job_id or "Unknown"), reset=True)
    
    try:
        # Get model name from config (first model in model_data)
        if not model_data:
            error_msg = "No models defined in configuration"
            write_heartbeat("1", error_msg, is_error=True)
            write_job_status("failed", error=error_msg, traceback_info="Model data empty")
            print("ERROR: {}".format(error_msg))
            return
        
        doc_name = model_data.keys()[0]
        print("Model from config: {}".format(doc_name))
        print("Config file: {}".format(config_name))
        
        # Check Revit version
        required_version = model_data[doc_name]["revit_version"]
        current_version = str(REVIT_APPLICATION.get_revit_version())
        
        write_heartbeat("1", "Version check: Required={}, Current={}".format(required_version, current_version))
        
        if current_version != required_version:
            error_msg = "Version mismatch: Need Revit {}, currently running {}".format(required_version, current_version)
            write_heartbeat("1", error_msg, is_error=True)
            write_job_status("failed", error=error_msg, traceback_info="Version check failed (no exception)")
            print("ERROR: {}".format(error_msg))
            return
    
        # Open document with detailed progress tracking
        write_heartbeat("2", "Opening document [{}]".format(doc_name))
        print("Opening [{}]...".format(doc_name))
        
        with ErrorSwallower():
            target_doc = open_and_activate_doc(doc_name, model_data, heartbeat_callback=write_heartbeat)
        
        if not target_doc:
            error_msg = "Failed to open document [{}] - Check orchestrator heartbeat log for detailed progress".format(doc_name)
            write_heartbeat("2.9", error_msg, is_error=True)
            write_job_status("failed", error=error_msg, traceback_info="Document open failed (no exception)")
            return
    
        write_heartbeat("3", "Document opened successfully")
        print("Document opened: {}".format(doc_name))
        
        # Extract Document object from UIDocument if needed
        if hasattr(target_doc, 'Document'):
            actual_doc = target_doc.Document
            print("Extracted Document object from UIDocument")
        else:
            actual_doc = target_doc
        
        try:
            ensure_all_links_loaded(
                actual_doc,
                timeout_minutes=10,
                heartbeat_callback=write_heartbeat
            )
        except Exception as link_error:
            error_msg = "Failed to load Revit links before export: {}".format(link_error)
            write_heartbeat("3.9", error_msg, is_error=True)
            write_job_status("failed", error=error_msg, traceback_info=traceback.format_exc())
            print("ERROR: {}".format(error_msg))
            return
        
        # Run exports
        write_heartbeat("4", "Starting exports")
        write_job_status("exporting")
        
        export_results = revit_export_logic.run_all_exports(
            actual_doc,
            job_id=JOB_ID,
            use_staging=True,
            heartbeat_callback=write_heartbeat
        )
        
        export_counts = {
            "pdf": len(export_results["pdf_files"]),
            "dwg": len(export_results["dwg_files"]),
            "jpg": len(export_results["jpg_files"])
        }
        
        write_heartbeat("4", "Exports completed: {} PDF, {} DWG, {} JPG".format(
            export_counts["pdf"],
            export_counts["dwg"],
            export_counts["jpg"]))
        
        # Run post-export tasks (email notifications, etc.)
        write_heartbeat("5", "Starting post-export tasks")
        write_job_status("post_export", exports=export_counts)
        
        pim_number = revit_export_logic.get_pim_number(actual_doc)
        project_name = project_info.get('project_name', 'Unknown Project')
        model_name = config_loader.get_model_name()
        revit_post_export_logic.run_post_export_tasks(
            export_results, pim_number, project_name, model_name, heartbeat_callback=write_heartbeat)
        write_heartbeat("5", "Post-export tasks completed")
        
        # Close Revit
        write_heartbeat("6", "Closing Revit")
        print("Closing Revit...")
        time.sleep(2)
        
        REVIT_APPLICATION.close_revit_app()
        write_heartbeat("END", "Auto export completed")
        
        # Write final status
        write_job_status("completed", exports=export_counts)
        
        # Don't auto-open heartbeat log (orchestrator will handle)
    
    except Exception as e:
        error_msg = "Auto export failed: {}".format(str(e))
        
        # Capture full traceback
        tb_lines = traceback.format_exc()
        
        write_heartbeat("ERROR", error_msg, is_error=True)
        write_job_status("failed", error=error_msg, traceback_info=tb_lines)
        
        # Also log traceback to heartbeat
        write_heartbeat("ERROR", "Full traceback:\n{}".format(tb_lines), is_error=True)
        
        raise




################## main code below #####################
if __name__ == "__main__":
    auto_export()







