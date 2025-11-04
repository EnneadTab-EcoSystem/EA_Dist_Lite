#!/usr/bin/python
# -*- coding: utf-8 -*-

"""
SparcHealth Revit Script

Runs INSIDE Revit (IronPython 2.7) to perform automated model health checks.
Opens cloud models detached with closed worksets, collects health metrics, and closes Revit.

This script is launched by the orchestrator (runs outside Revit) via pyRevit CLI.
Configuration is loaded from current_job_payload.json which specifies the active model.

Process:
1. Read job payload to get active model data
2. Open cloud model (detached, closed worksets)
3. Collect health metrics (timestamp, doc title)
4. Write output to OneDrive Dump/SparcHealth folder
5. Write job status to current_job_status.json
6. Close Revit cleanly

Status Stages:
- running: Script started
- checking: Performing health checks
- completed: Job finished successfully
- failed: Error occurred (with error message)
"""

__doc__ = "SparcHealth - Opens cloud model, collects health metrics, closes Revit"
__title__ = "Sparc Health Check"
__context__ = "zero-doc"

# Basic imports
import time
import os
import sys
import traceback
from datetime import datetime

# Ensure EnneadTab lib is in sys.path
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

# Load configuration from config_loader
HEARTBEAT_SETTINGS = config_loader.get_heartbeat_settings()
OUTPUT_SETTINGS = config_loader.get_output_settings()
PROJECT_INFO = config_loader.get_project_info()

# Get job information
JOB_ID = config_loader.get_current_job_id()
MODEL_DATA = config_loader.get_current_model_data()


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
                f.write("SPARC HEALTH CHECK HEARTBEAT LOG\n")
                f.write("="*80 + "\n")
        
        with open(heartbeat_file, 'a') as f:
            f.write("[{}] [STEP {}] [{}] {}\n".format(timestamp, step, status, message))
        
        return heartbeat_file
    except Exception as e:
        print("Heartbeat error: {}".format(e))
        return None


def write_job_status(status, error=None, health_data=None, traceback_info=None):
    """Write job status to current_job_status.json
    
    Args:
        status: Job status ("running", "checking", "completed", "failed")
        error: Error message if failed
        health_data: Dictionary with health check results
        traceback_info: Full traceback string for debugging
    """
    try:
        status_file = os.path.join(os.path.dirname(__file__), "current_job_status.json")
        
        status_data = {
            "job_id": JOB_ID,
            "model_name": MODEL_DATA.get('name') if MODEL_DATA else 'Unknown',
            "status": status,
            "updated_at": datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        }
        
        if error:
            status_data["error"] = str(error)
        
        if traceback_info:
            status_data["traceback"] = traceback_info
        
        if health_data:
            status_data["health_data"] = health_data
        
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


def tuple_to_model_path(model_data):
    """Convert model data dictionary to ModelPath object"""
    if not model_data:
        return None
    
    project_guid = model_data.get("project_guid")
    file_guid = model_data.get("model_guid")
    region = model_data.get("region")
    
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


def open_and_activate_doc(model_data):
    """Open and activate a document from model data"""
    if not model_data:
        print("No model data provided")
        return None
    
    cloud_path = tuple_to_model_path(model_data)
    if not cloud_path:
        return None
    
    # Setup open options - detach and CLOSE worksets (not open)
    open_options = DB.OpenOptions()
    open_options.DetachFromCentralOption = DB.DetachFromCentralOption.DetachAndPreserveWorksets
    open_options.SetOpenWorksetsConfiguration(
        DB.WorksetConfiguration(DB.WorksetConfigurationOption.CloseAllWorksets)
    )
    open_options.Audit = False  # No audit for health checks
    
    print("Opening document (detached, closed worksets)...")
    
    try:
        return REVIT_APPLICATION.get_uiapp().OpenAndActivateDocument(cloud_path, open_options, False)
    except:
        try:
            doc = REVIT_APPLICATION.get_app().OpenDocumentFile(cloud_path, open_options)
            if doc:
                REVIT_APPLICATION.open_and_active_project(cloud_path)
            return doc
        except Exception as e:
            print("Failed to open: {}".format(e))
            return None


def format_time(seconds):
    """Format time in seconds to readable format"""
    if seconds < 60:
        return "{:.1f}s".format(seconds)
    elif seconds < 3600:
        return "{:.1f}min".format(seconds / 60)
    else:
        return "{:.1f}hr".format(seconds / 3600)


def get_file_size_info(doc):
    """Get file size information"""
    try:
        if not doc or not hasattr(doc, 'PathName') or not doc.PathName:
            return {"size_bytes": 0, "size_readable": "Unknown"}
        
        import os
        if os.path.exists(doc.PathName):
            size_bytes = os.path.getsize(doc.PathName)
            # Convert to human readable
            for unit in ['B', 'KB', 'MB', 'GB']:
                if size_bytes < 1024.0:
                    return {
                        "size_bytes": int(size_bytes),
                        "size_readable": "{:.2f} {}".format(size_bytes, unit)
                    }
                size_bytes /= 1024.0
            return {
                "size_bytes": int(size_bytes * 1024 * 1024 * 1024 * 1024),
                "size_readable": "{:.2f} TB".format(size_bytes)
            }
        else:
            return {"size_bytes": 0, "size_readable": "Unknown"}
    except:
        return {"size_bytes": 0, "size_readable": "Error"}


def collect_health_metrics(doc, start_time):
    """Collect health metrics from the document - matching RevitSlave-3.0 format
    
    Args:
        doc: Revit Document object
        start_time: Job start time for execution tracking
        
    Returns:
        dict: Health metrics data in RevitSlave-3.0 format
    """
    # Calculate execution time
    execution_time = time.time() - start_time
    
    # Get file size
    file_size_info = get_file_size_info(doc)
    
    # Build output in RevitSlave-3.0 format
    health_output = {
        "job_metadata": {
        "job_id": JOB_ID,
            "hub_name": "ACC",  # SPARC project is on ACC
        "project_name": PROJECT_INFO.get('project_name', 'Unknown'),
            "model_name": MODEL_DATA.get('name') if MODEL_DATA else 'Unknown',
            "model_file_size_bytes": file_size_info["size_bytes"],
            "model_file_size_readable": file_size_info["size_readable"],
        "revit_version": MODEL_DATA.get('revit_version') if MODEL_DATA else 'Unknown',
            "discipline": MODEL_DATA.get('discipline', 'Unknown') if MODEL_DATA else 'Unknown',
            "timestamp": datetime.now().isoformat(),
            "execution_time_seconds": round(execution_time, 2),
            "execution_time_readable": format_time(execution_time)
        },
        "health_metric_result": {
            "version": "v2",
            "timestamp": datetime.now().isoformat(),
            "document_title": doc.Title if doc else "Unknown",
            "is_EnneadTab_Available": False,
            "checks": {}
        },
        "status": "success"
    }
    
    checks = health_output["health_metric_result"]["checks"]
    
    if not doc:
        health_output["status"] = "failed"
        health_output["error"] = "No document available"
        return health_output
    
    try:
        # Check 1: Critical Elements (matching RevitSlave-3.0)
        print("Collecting critical elements...")
        critical_elements = {}
        all_elements = DB.FilteredElementCollector(doc).WhereElementIsNotElementType().ToElements()
        total_elements = len(list(all_elements))
        critical_elements["total_elements"] = total_elements
        
        # Element counts by category
        element_counts = {}
        categories_to_count = [
            (DB.BuiltInCategory.OST_Walls, "Walls"),
            (DB.BuiltInCategory.OST_Doors, "Doors"),
            (DB.BuiltInCategory.OST_Windows, "Windows"),
            (DB.BuiltInCategory.OST_Floors, "Floors"),
            (DB.BuiltInCategory.OST_Roofs, "Roofs"),
            (DB.BuiltInCategory.OST_Columns, "Columns"),
            (DB.BuiltInCategory.OST_StructuralColumns, "Structural Columns"),
            (DB.BuiltInCategory.OST_StructuralFraming, "Structural Framing"),
            (DB.BuiltInCategory.OST_Rooms, "Rooms"),
            (DB.BuiltInCategory.OST_MEPSpaces, "Spaces"),
            (DB.BuiltInCategory.OST_DuctCurves, "Ducts"),
            (DB.BuiltInCategory.OST_PipeCurves, "Pipes"),
            (DB.BuiltInCategory.OST_ElectricalEquipment, "Electrical Equipment"),
            (DB.BuiltInCategory.OST_MechanicalEquipment, "Mechanical Equipment"),
            (DB.BuiltInCategory.OST_LightingFixtures, "Lighting Fixtures"),
            (DB.BuiltInCategory.OST_Furniture, "Furniture"),
        ]
        
        for bic, name in categories_to_count:
            try:
                count = DB.FilteredElementCollector(doc).OfCategory(bic).WhereElementIsNotElementType().GetElementCount()
                if count > 0:
                    element_counts[name] = count
            except:
                pass
        
        critical_elements["element_counts_by_category"] = element_counts
        
        # Collect warning counts
        print("Collecting warnings...")
        try:
            warnings = doc.GetWarnings()
            warning_count = len(list(warnings))
            critical_elements["warning_count"] = warning_count
            
            # Group warnings by severity
            warning_by_severity = {}
            for warning in warnings:
                severity = str(warning.GetSeverity())
                warning_by_severity[severity] = warning_by_severity.get(severity, 0) + 1
            critical_elements["warnings_by_severity"] = warning_by_severity
        except Exception as e:
            critical_elements["warning_count"] = "Error: {}".format(str(e))
        
        # Store critical elements check
        checks["critical_elements"] = critical_elements
        
        # Check 2: Views and Sheets (matching RevitSlave-3.0)
        print("Collecting views and sheets...")
        views_sheets = {}
        try:
            all_views = DB.FilteredElementCollector(doc).OfClass(DB.View).WhereElementIsNotElementType()
            view_count = all_views.GetElementCount()
            views_sheets["total_views"] = view_count
            
            # Count by view type
            view_types = {}
            for view in all_views:
                if view.IsTemplate:
                    continue
                vt = str(view.ViewType)
                view_types[vt] = view_types.get(vt, 0) + 1
            views_sheets["view_count_by_type"] = view_types
        except Exception as e:
            views_sheets["total_views"] = "Error: {}".format(str(e))
        
        # Collect sheet counts
        try:
            sheets = DB.FilteredElementCollector(doc).OfClass(DB.ViewSheet).WhereElementIsNotElementType()
            sheet_count = sheets.GetElementCount()
            views_sheets["total_sheets"] = sheet_count
        except Exception as e:
            views_sheets["total_sheets"] = "Error: {}".format(str(e))
        
        # Store views_sheets check
        checks["views_sheets"] = views_sheets
        
        # Check 3: Project Info (including worksets - matching RevitSlave-3.0)
        print("Collecting project info...")
        project_info = {}
        try:
            project_info["is_workshared"] = doc.IsWorkshared
            if doc.IsWorkshared:
                worksets = DB.FilteredWorksetCollector(doc).OfKind(DB.WorksetKind.UserWorkset).ToWorksets()
                workset_count = len(list(worksets))
                project_info["workset_count"] = workset_count
                
                workset_names = []
                for ws in worksets:
                    workset_names.append(ws.Name)
                project_info["workset_names"] = workset_names
            else:
                project_info["workset_count"] = 0
        except Exception as e:
            project_info["workset_info_error"] = "Error: {}".format(str(e))
        
        # Store project_info check
        checks["project_info"] = project_info
        
        # Check 4: Linked Files (matching RevitSlave-3.0)
        print("Collecting linked models...")
        linked_files = {}
        try:
            rvt_links = DB.FilteredElementCollector(doc).OfClass(DB.RevitLinkInstance)
            link_count = rvt_links.GetElementCount()
            linked_files["linked_files_count"] = link_count
            
            if link_count > 0:
                link_list = []
                for link in rvt_links:
                    try:
                        link_doc = link.GetLinkDocument()
                        if link_doc:
                            link_list.append({
                                "linked_file_name": link_doc.Title,
                                "instance_name": link.Name,
                                "loaded_status": "Loaded" if link_doc else "Unloaded"
                            })
                        else:
                            link_list.append({
                                "linked_file_name": "Unloaded",
                                "instance_name": link.Name,
                                "loaded_status": "Unloaded"
                            })
                    except:
                        link_list.append({
                            "linked_file_name": "Unknown",
                            "instance_name": "Unknown",
                            "loaded_status": "Error"
                        })
                linked_files["linked_files"] = link_list
        except Exception as e:
            linked_files["error"] = "Error: {}".format(str(e))
        
        # Store linked_files check
        checks["linked_files"] = linked_files
        
        # Check 5: Families (matching RevitSlave-3.0)
        print("Collecting family counts...")
        families_check = {}
        try:
            families = DB.FilteredElementCollector(doc).OfClass(DB.Family)
            family_count = families.GetElementCount()
            families_check["family_count"] = family_count
        except Exception as e:
            families_check["error"] = "Error: {}".format(str(e))
        
        # Store families check
        checks["families"] = families_check
        
        # Check 6: Additional project parameters
        print("Collecting additional project parameters...")
        try:
            proj_info = doc.ProjectInformation
            if proj_info:
                # Try to get common project info parameters
                param_names = ["Project Name", "Project Number", "Project Address", "Client Name", "Project Status"]
                for param_name in param_names:
                    try:
                        param = proj_info.LookupParameter(param_name)
                        if param and param.HasValue:
                            project_info[param_name.lower().replace(" ", "_")] = param.AsString()
                    except:
                        pass
        except Exception as e:
            project_info["parameters_error"] = "Error: {}".format(str(e))
        
        # Update project_info check with additional parameters
        checks["project_info"] = project_info
        
        # Optional: Design options (if present)
        try:
            design_options = DB.FilteredElementCollector(doc).OfClass(DB.DesignOption)
            design_option_count = design_options.GetElementCount()
            if design_option_count > 0:
                checks["design_options"] = {"count": design_option_count}
        except:
            pass
        
        print("Health metrics collected successfully")
        
    except Exception as e:
        health_output["status"] = "partial"
        health_output["collection_error"] = str(e)
        print("Error collecting some health metrics: {}".format(e))
    
    return health_output


def write_health_output(health_data):
    """Write health data to output folder
    
    Args:
        health_data: Dictionary with health check results
        
    Returns:
        str: Path to output file
    """
    try:
        # Get output base path
        output_base = OUTPUT_SETTINGS.get('base_path', '')
        if not output_base:
            raise RuntimeError("Output base path not configured")
        
        # Ensure output directory exists
        if not os.path.exists(output_base):
            os.makedirs(output_base)
        
        # Generate output filename
        model_name = MODEL_DATA.get('name', 'Unknown') if MODEL_DATA else 'Unknown'
        timestamp = datetime.now().strftime(OUTPUT_SETTINGS.get('date_format', '%Y%m%d_%H%M%S'))
        output_filename = "{}_{}.json".format(model_name, timestamp)
        output_path = os.path.join(output_base, output_filename)
        
        # Write JSON file
        import json
        with open(output_path, 'w') as f:
            json.dump(health_data, f, indent=2)
        
        print("Health data written to: {}".format(output_path))
        return output_path
        
    except Exception as e:
        error_msg = "Failed to write health output: {}".format(e)
        print(error_msg)
        raise RuntimeError(error_msg)


@LOG.log(__file__, __title__)
@ERROR_HANDLE.try_catch_error()
def health_check():
    # Track execution time
    start_time = time.time()
    
    # Initialize job status
    write_job_status("running")
    
    # Force reload config to get the current job's configuration
    config_loader.load_config(force_reload=True)
    
    # Reload all config data with the new config
    global MODEL_DATA, JOB_ID
    MODEL_DATA = config_loader.get_current_model_data()
    JOB_ID = config_loader.get_current_job_id()
    
    # Initialize heartbeat log
    heartbeat_file = write_heartbeat("START", "Health check started [Job: {}]".format(JOB_ID or "Unknown"), reset=True)
    
    try:
        # Validate model data
        if not MODEL_DATA:
            error_msg = "No model data found in payload"
            write_heartbeat("1", error_msg, is_error=True)
            write_job_status("failed", error=error_msg, traceback_info="Model data empty")
            print("ERROR: {}".format(error_msg))
            return
        
        model_name = MODEL_DATA.get('name', 'Unknown')
        print("Model from payload: {}".format(model_name))
        print("Job ID: {}".format(JOB_ID))
        
        # Check Revit version
        required_version = MODEL_DATA.get("revit_version", "Unknown")
        current_version = str(REVIT_APPLICATION.get_revit_version())
        
        write_heartbeat("1", "Version check: Required={}, Current={}".format(required_version, current_version))
        
        if current_version != required_version:
            error_msg = "Version mismatch: Need Revit {}, currently running {}".format(required_version, current_version)
            write_heartbeat("1", error_msg, is_error=True)
            write_job_status("failed", error=error_msg, traceback_info="Version check failed")
            print("ERROR: {}".format(error_msg))
            return
    
        # Open document
        write_heartbeat("2", "Opening document [{}]".format(model_name))
        print("Opening [{}]...".format(model_name))
        
        with ErrorSwallower():
            target_doc = open_and_activate_doc(MODEL_DATA)
        
        if not target_doc:
            error_msg = "Failed to open document [{}]".format(model_name)
            write_heartbeat("2", error_msg, is_error=True)
            write_job_status("failed", error=error_msg, traceback_info="Document open failed")
            return
    
        write_heartbeat("3", "Document opened successfully")
        print("Document opened: {}".format(model_name))
        
        # Extract Document object from UIDocument if needed
        if hasattr(target_doc, 'Document'):
            actual_doc = target_doc.Document
            print("Extracted Document object from UIDocument")
        else:
            actual_doc = target_doc
        
        # Collect health metrics
        write_heartbeat("4", "Collecting health metrics")
        write_job_status("checking")
        
        health_output = collect_health_metrics(actual_doc, start_time)
        
        write_heartbeat("4", "Health metrics collected successfully")
        
        # Write health output to file
        write_heartbeat("5", "Writing health data to output folder")
        
        output_path = write_health_output(health_output)
        
        write_heartbeat("5", "Health data written to: {}".format(output_path))
        
        # Close Revit
        write_heartbeat("6", "Closing Revit")
        print("Closing Revit...")
        time.sleep(2)
        
        REVIT_APPLICATION.close_revit_app()
        write_heartbeat("END", "Health check completed")
        
        # Write final status
        write_job_status("completed", health_data=health_output)
    
    except Exception as e:
        error_msg = "Health check failed: {}".format(str(e))
        
        # Capture full traceback
        tb_lines = traceback.format_exc()
        
        write_heartbeat("ERROR", error_msg, is_error=True)
        write_job_status("failed", error=error_msg, traceback_info=tb_lines)
        
        # Also log traceback to heartbeat
        write_heartbeat("ERROR", "Full traceback:\n{}".format(tb_lines), is_error=True)
        
        raise




################## main code below #####################
if __name__ == "__main__":
    health_check()

