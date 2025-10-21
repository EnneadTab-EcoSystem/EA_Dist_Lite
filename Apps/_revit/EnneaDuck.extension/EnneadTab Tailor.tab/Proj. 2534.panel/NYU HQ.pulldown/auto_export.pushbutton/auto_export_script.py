#!/usr/bin/python
# -*- coding: utf-8 -*-

__doc__ = "Auto export script for NYU HQ project. Opens cloud model, exports files, closes Revit."
__title__ = "Auto Export"
__context__ = "zero-doc"

# Basic imports
import time
import os
import sys
from datetime import datetime

# Ensure EnneadTab lib is in sys.path
# Get username dynamically and check both developer and distribution paths
import os
USERNAME = os.environ.get("USERNAME", "szhang")

# Try developer path first, then distribution path
lib_path_dev = r"C:\Users\{}\github\EnneadTab-OS\Apps\lib".format(USERNAME)
lib_path_dist = r"C:\Users\{}\Documents\EnneadTab Ecosystem\EA_Dist\Apps\lib".format(USERNAME)

if os.path.exists(lib_path_dev):
    lib_path = lib_path_dev
elif os.path.exists(lib_path_dist):
    lib_path = lib_path_dist
else:
    lib_path = lib_path_dev  # Default to dev path

if lib_path not in sys.path:
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
import export_logic
import post_export_logic

MODEL_DATA = {
    "2534_A_EA_NYU HQ_Shell": {
        "model_guid": "e8392a95-51dd-49b1-ad35-d2b66e3a8cbf", 
        "project_guid": "51bdf270-659d-4299-9fe0-0eb024873dc2", 
        "region": "US", 
        "revit_version": "2026"
    }
}


def write_heartbeat(step, message, is_error=False, reset=False):
    """Write a heartbeat entry with timestamp to track script execution"""
    try:
        heartbeat_dir = os.path.join(os.path.dirname(__file__), "heartbeat")
        if not os.path.exists(heartbeat_dir):
            os.makedirs(heartbeat_dir)
        
        date_stamp = datetime.now().strftime("%Y%m%d")
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


def open_and_activate_doc(doc_name, model_data):
    """Open and activate a document by name"""
    if doc_name not in model_data:
        print("[{}] not found in model data".format(doc_name))
        return None
    
    cloud_path = tuple_to_model_path(model_data[doc_name])
    if not cloud_path:
        return None
    
    # Setup open options - detach and preserve worksets
    open_options = DB.OpenOptions()
    open_options.DetachFromCentralOption = DB.DetachFromCentralOption.DetachAndPreserveWorksets
    open_options.SetOpenWorksetsConfiguration(
        DB.WorksetConfiguration(DB.WorksetConfigurationOption.OpenAllWorksets)
    )
    open_options.Audit = True
    
    print("Opening document (detached, audit, all worksets)...")
    
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


@LOG.log(__file__, __title__)
@ERROR_HANDLE.try_catch_error()
def auto_export():
    # Initialize heartbeat log
    heartbeat_file = write_heartbeat("START", "Auto export started", reset=True)
    
    # Check Revit version
    doc_name = "2534_A_EA_NYU HQ_Shell"
    required_version = MODEL_DATA[doc_name]["revit_version"]
    current_version = str(REVIT_APPLICATION.get_revit_version())
    
    write_heartbeat("1", "Version check: Required={}, Current={}".format(required_version, current_version))
    
    if current_version != required_version:
        write_heartbeat("1", "Version mismatch!", is_error=True)
        print("ERROR: Need Revit {}, currently running {}".format(required_version, current_version))
        return
    
    # Open document
    write_heartbeat("2", "Opening document [{}]".format(doc_name))
    print("Opening [{}]...".format(doc_name))
    
    with ErrorSwallower():
        target_doc = open_and_activate_doc(doc_name, MODEL_DATA)
    
    if not target_doc:
        write_heartbeat("2", "Failed to open document", is_error=True)
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
    export_results = export_logic.run_all_exports(actual_doc, heartbeat_callback=write_heartbeat)
    write_heartbeat("4", "Exports completed: {} PDF, {} DWG, {} JPG".format(
        len(export_results["pdf_files"]),
        len(export_results["dwg_files"]),
        len(export_results["jpg_files"])))
    
    # Run post-export tasks (email notifications, etc.)
    write_heartbeat("5", "Starting post-export tasks")
    pim_number = export_logic.get_pim_number(actual_doc)
    project_name = "NYU HQ"
    post_export_logic.run_post_export_tasks(
        export_results, pim_number, project_name, heartbeat_callback=write_heartbeat)
    write_heartbeat("5", "Post-export tasks completed")
    
    # Close Revit
    write_heartbeat("6", "Closing Revit")
    print("Closing Revit...")
    time.sleep(2)
    
    REVIT_APPLICATION.close_revit_app()
    write_heartbeat("END", "Auto export completed")
    
    # Open heartbeat log
    open_heartbeat_file(heartbeat_file)




################## main code below #####################
if __name__ == "__main__":
    auto_export()







