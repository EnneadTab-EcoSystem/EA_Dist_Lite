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
    
    # Setup open options - detach and preserve worksets
    if heartbeat_callback:
        heartbeat_callback("2.3", "Configuring open options (detached, audit, all worksets)")
    
    open_options = DB.OpenOptions()
    open_options.DetachFromCentralOption = DB.DetachFromCentralOption.DetachAndPreserveWorksets
    open_options.SetOpenWorksetsConfiguration(
        DB.WorksetConfiguration(DB.WorksetConfigurationOption.OpenAllWorksets)
    )
    open_options.Audit = True
    
    print("Opening document (detached, audit, all worksets)...")
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
        
        # Run exports
        write_heartbeat("4", "Starting exports")
        write_job_status("exporting")
        
        export_results = revit_export_logic.run_all_exports(actual_doc, heartbeat_callback=write_heartbeat)
        
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







