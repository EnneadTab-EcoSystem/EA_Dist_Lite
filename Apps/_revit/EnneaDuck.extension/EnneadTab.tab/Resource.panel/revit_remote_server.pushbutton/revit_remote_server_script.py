__context__ = "zero-doc"
#!/usr/bin/python
# -*- coding: utf-8 -*-

__doc__ = "Standalone Remote Server Script (no EnneadTab/proDUCKtion dependency)."
__title__ = "Revit Remote Server"

from Autodesk.Revit import DB # pyright: ignore 
import os
import json
from datetime import datetime
import traceback



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

CURRENT_JOB_FILENAME = "current_job.SexyDuck"
TASK_OUTPUT_DIRNAME = "task_output"
DEBUG_DIRNAME = "_debug"
PUBLIC_DB_FOLDER = "L:\\4b_Design Technology\\05_EnneadTab-DB\\Shared Data Dump\\RevitSlaveDatabase"

def _join(*parts):
    return os.path.join(*parts)

def _script_dir():
    return os.path.dirname(os.path.abspath(__file__))

def _job_path():
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

def _ensure_output_dir():
    out_dir = _join(PUBLIC_DB_FOLDER, TASK_OUTPUT_DIRNAME)
    if not os.path.exists(out_dir):
        os.makedirs(out_dir)
    return out_dir

def _ensure_debug_dir():
    dbg_dir = _join(PUBLIC_DB_FOLDER, DEBUG_DIRNAME)
    if not os.path.exists(dbg_dir):
        try:
            os.makedirs(dbg_dir)
        except Exception:
            pass
    return dbg_dir

def _append_debug(message):
    try:
        dbg_dir = _ensure_debug_dir()
        with open(_join(dbg_dir, "debug.txt"), 'a') as f:
            f.write("[{}] {}\n".format(datetime.now().isoformat(), message))
    except Exception:
        pass

def _write_failure_payload(title, exc, job=None):
    try:
        dbg_dir = _ensure_debug_dir()
        name = "{}_ERROR_{}.SexyDuck".format(datetime.now().strftime("%Y-%m"), title)
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
        _save_json(_join(dbg_dir, name), payload)
    except Exception:
        pass

def _format_output_filename(job_payload):
    # {yyyy-mm}_hub_project_model.SexyDuck
    ts = datetime.now().strftime("%Y-%m")
    hub = (job_payload.get("hub_name") or "hub")
    proj = (job_payload.get("project_name") or "project")
    model = (job_payload.get("model_name") or "model")
    return "{}_{}_{}_{}.SexyDuck".format(ts, hub, proj, model)

def _update_job_status(job, new_status, extra_fields=None):
    job["status"] = new_status
    if extra_fields:
        for k in extra_fields:
            job[k] = extra_fields[k]
    _save_json(_job_path(), job)

def _get_app():
    # Optimized: Use only the successful pyrevit.HOST_APP.app path
    from pyrevit import HOST_APP as _HOST_APP
    if hasattr(_HOST_APP, 'app') and _HOST_APP.app is not None:
        return _HOST_APP.app
    raise Exception("pyRevit HOST_APP.app not available")

def get_doc(job_payload):
    """
    Obtain a Revit Document by opening the model_path specified in the job payload.
    Returns (doc, must_close):
      - doc: the active document reference (or None on failure)
      - must_close (bool): True if this function opened the document and caller should close it
    """
    opened_doc = None
    try:
        model_path = job_payload.get('model_path') if isinstance(job_payload, dict) else None
        if not model_path:
            raise Exception("Missing model_path in job payload")
        app = _get_app()
        # Best-effort version/worksharing probe; do not block open on mismatch here
        try:
            bfi = DB.BasicFileInfo.Extract(model_path)
        except Exception as ex:
            _append_debug("BasicFileInfo.Extract failed: {}".format(ex))
            bfi = None
        mpath = DB.ModelPathUtils.ConvertUserVisiblePathToModelPath(model_path)
        opts = DB.OpenOptions()
        # If the file is workshared, prefer to detach to avoid central locks
        try:
            if bfi is not None and bfi.IsWorkshared:
                opts.DetachFromCentralOption = DB.DetachFromCentralOption.DetachAndPreserveWorksets
        except Exception as ex:
            _append_debug("Setting DetachFromCentralOption failed: {}".format(ex))
        # Open with minimal load: close all worksets for reliability
        wsconfig = DB.WorksetConfiguration(DB.WorksetConfigurationOption.CloseAllWorksets)
        opts.SetOpenWorksetsConfiguration(wsconfig)
        opened_doc = app.OpenDocumentFile(mpath, opts)
        if opened_doc is None:
            raise Exception("OpenDocumentFile returned None")
        return opened_doc, True
    except Exception as e:
        _append_debug("get_doc failed: {}".format(e))
        _write_failure_payload("get_doc", e, job_payload)
        raise

def run_metric(doc, job_payload):
    """
    Placeholder metric function interface.
    - doc: active Revit document
    - job_payload: dict-like payload read from current_job (parsed JSON)

    Returns a dict-like result that will be stored under result_data on success.
    Replace the internal logic with real metrics in the future.
    """
    # Placeholder: return a simple result shape; real implementation should
    # compute values (e.g., total wall count) from the active document.
    if doc is None:
        raise Exception("No active document available")
    try:
        collector = DB.FilteredElementCollector(doc).OfCategory(DB.BuiltInCategory.OST_Walls).WhereElementIsNotElementType()
        walls = list(collector)
        return {"placeholder": False, "wall_count": len(walls)}
    except Exception as ex:
        _append_debug("run_metric failed: {}".format(ex))
        raise




def revit_remote_server():
    logs = []
    job = None
    try:
        # Heartbeat: prove script started and can write to TASK_OUTPUT
        try:
            hb_dir = _ensure_debug_dir()
            hb_path = _join(hb_dir, "_heartbeat.txt")
            with open(hb_path, 'a') as _hb:
                _hb.write(datetime.now().isoformat() + " started" + "\n")
        except Exception as ex:
            _append_debug("Heartbeat write failed: {}".format(ex))

        job_path = _job_path()
        if not os.path.exists(job_path):
            raise Exception("current_job.SexyDuck not found")

        job = _load_json(job_path)
        if not isinstance(job, dict):
            raise Exception("Invalid job payload structure")

        # 1) pending (taken)
        _update_job_status(job, "pending")
        logs.append("Job set to pending")

        # 2) running
        _update_job_status(job, "running")
        logs.append("Job set to running")

        # 3) get document and execute metric
        doc, must_close = get_doc(job)
        try:
            result = run_metric(doc, job)
        finally:
            try:
                if must_close and doc is not None:
                    doc.Close(False)
            except:
                pass

        # 4) write output file
        out_dir = _ensure_output_dir()
        out_name = _format_output_filename(job)
        out_path = _join(out_dir, out_name)
        output_payload = {
            "job_metadata": {
                "job_id": job.get("job_id"),
                "hub_name": job.get("hub_name"),
                "project_name": job.get("project_name"),
                "model_name": job.get("model_name"),
                "revit_version": job.get("revit_version"),
                "timestamp": datetime.now().isoformat()
            },
            "result_data": result,
            "status": "completed"
        }
        _save_json(out_path, output_payload)
        logs.append("Output saved: " + out_path)

        # 5) mark completed (success)
        _update_job_status(job, "completed", {"result_data": result})
        logs.append("Job completed")
    except Exception as e:
        import traceback
        tb = traceback.format_exc()
        logs.append("Exception: " + str(e))
        # Try to write failure to job file if available; else create a minimal one
        try:
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
            _update_job_status(job, "failed", {"logs": "\n".join(logs), "error_msg": tb})
        except Exception:
            pass
        # Also emit a failure output file to TASK_OUTPUT/DEBUG for capture
        try:
            dbg_dir = _ensure_debug_dir()
            fallback_name = "{}_{}_{}_ERROR.SexyDuck".format(
                datetime.now().strftime("%Y-%m"),
                (job.get("hub_name") if isinstance(job, dict) else "hub"),
                (job.get("model_name") if isinstance(job, dict) else "model")
            )
            out_path = _join(dbg_dir, fallback_name)
            output_payload = {
                "job_metadata": {
                    "job_id": job.get("job_id") if isinstance(job, dict) else None,
                    "hub_name": job.get("hub_name") if isinstance(job, dict) else None,
                    "project_name": job.get("project_name") if isinstance(job, dict) else None,
                    "model_name": job.get("model_name") if isinstance(job, dict) else None,
                    "revit_version": job.get("revit_version") if isinstance(job, dict) else None,
                    "timestamp": datetime.now().isoformat()
                },
                "status": "failed",
                "logs": "\n".join(logs),
                "error_msg": tb
            }
            _save_json(out_path, output_payload)
        except Exception as ex:
            _append_debug("Write failure payload failed: {}".format(ex))
        print("Job failed. See logs in job file or TASK_OUTPUT.")



################## main code below #####################
if __name__ == "__main__":
    revit_remote_server()







