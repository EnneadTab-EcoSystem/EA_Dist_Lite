#!/usr/bin/python
# -*- coding: utf-8 -*-

__doc__ = "Run RevitSlave4 health metrics on the active document and save the report locally."
__title__ = "test slave"

from pyrevit import script # pyright: ignore

import proDUCKtion # pyright: ignore
proDUCKtion.validify()

import os
import sys
import json
import re
import time
import importlib
import traceback
from datetime import datetime

from EnneadTab import ERROR_HANDLE, LOG, NOTIFICATION
from EnneadTab.REVIT import REVIT_APPLICATION

DOC = REVIT_APPLICATION.get_doc()


def _resolve_repo_root():
    path = os.path.abspath(os.path.dirname(__file__))
    for _ in range(20):
        if os.path.isdir(os.path.join(path, ".git")):
            return path
        parent = os.path.dirname(path)
        if parent == path:
            break
        path = parent
    raise Exception("Could not locate repository root from {}".format(__file__))


def _ensure_dir(path):
    if not os.path.exists(path):
        os.makedirs(path)
    return path


def _sanitize_filename(value):
    if not value:
        return "untitled"
    sanitized = re.sub(r"[^A-Za-z0-9._-]+", "_", value)
    if not sanitized:
        sanitized = "untitled"
    return sanitized


@LOG.log(__file__, __title__)
@ERROR_HANDLE.try_catch_error()
def run_health_metric(doc):
    if doc is None:
        NOTIFICATION.messenger("No active Revit document was found.")
        return

    repo_root = _resolve_repo_root()
    revitslave_logic_path = os.path.join(
        repo_root,
        "DarkSide",
        "exes",
        "source code",
        "RevitSlave-4.0",
        "revit_logic",
    )

    if not os.path.exists(revitslave_logic_path):
        raise Exception("RevitSlave4 logic folder not found: {}".format(revitslave_logic_path))

    if revitslave_logic_path not in sys.path:
        sys.path.append(revitslave_logic_path)

    health_metric_path = os.path.join(revitslave_logic_path, "health_metric")
    if health_metric_path not in sys.path:
        sys.path.append(health_metric_path)

    health_metric_module = importlib.import_module("health_metric")
    HealthMetric = getattr(health_metric_module, "HealthMetric")

    debug_root = os.path.join(repo_root, "DEBUG", "RevitSlave4", "test_slave_button")
    _ensure_dir(debug_root)

    timestamp_str = datetime.now().strftime("%Y%m%d_%H%M%S")
    job_id = "test_slave_{}".format(timestamp_str)
    crash_log_path = os.path.join(debug_root, "test_slave_crash_{}.log".format(timestamp_str))

    start_time = time.time()
    error_message = None

    try:
        metric_runner = HealthMetric(doc)
        health_report = metric_runner.check()
    except Exception as run_error:
        error_message = "HealthMetric.check crashed: {}".format(str(run_error))
        tb_text = traceback.format_exc()
        health_report = {
            "error": str(run_error),
            "traceback": tb_text,
            "stage": "HealthMetric.check",
        }
        try:
            with open(crash_log_path, "w") as crash_handle:
                crash_handle.write("Health metric crash captured at {}\n".format(datetime.now().isoformat()))
                crash_handle.write("Job ID: {}\n".format(job_id))
                crash_handle.write("Document: {}\n".format(getattr(doc, "Title", "Unknown")))
                crash_handle.write("\nError:\n{}\n".format(str(run_error)))
                crash_handle.write("\nTraceback:\n{}\n".format(tb_text))
        except Exception as crash_write_error:
            script.get_output().print_md(
                "- Failed to write crash log ({}).".format(str(crash_write_error))
            )

    execution_time = time.time() - start_time

    button_dir = os.path.abspath(os.path.dirname(__file__))
    output_dir = _ensure_dir(button_dir)

    file_base = _sanitize_filename(getattr(doc, "Title", "HealthMetric"))
    output_name = "{}_{}.sexyDuck".format(file_base, timestamp_str)
    output_path = os.path.join(output_dir, output_name)

    output_payload = {
        "job_metadata": {
            "job_id": job_id,
            "hub_name": None,
            "project_name": getattr(doc, "Title", "Unknown"),
            "model_name": getattr(doc, "Title", "Unknown"),
            "model_path": getattr(doc, "PathName", None),
            "revit_version": getattr(doc.Application, "VersionName", ""),
            "timestamp": datetime.now().isoformat(),
            "execution_time_seconds": round(execution_time, 2),
            "execution_time_readable": "{0:.1f}s".format(execution_time),
        },
        "health_metric_result": health_report,
        "export_data": None,
        "status": "completed" if not error_message else "completed with errors",
        "error": error_message,
    }

    try:
        with open(output_path, "w") as handle:
            json.dump(output_payload, handle, indent=2)
    except Exception as write_error:
        fallback_dir = _ensure_dir(os.path.join(debug_root, "output"))
        output_path = os.path.join(fallback_dir, output_name)
        with open(output_path, "w") as handle:
            json.dump(output_payload, handle, indent=2)
        script.get_output().print_md(
            "- Could not write to button folder ({}). Saved to fallback: `{}`".format(write_error, output_path)
        )

    out = script.get_output()
    out.close_others()
    out.print_md("### RevitSlave4 Health Metric")
    out.print_md("- Saved report to `{}`".format(output_path))
    if error_message:
        out.print_md("- Metrics completed with warnings/errors: {}".format(error_message))
        if os.path.exists(crash_log_path):
            out.print_md("- Crash log saved to `{}`".format(crash_log_path))
    else:
        out.print_md("- Metrics completed successfully.")

    NOTIFICATION.messenger("Health metric saved to:\n{}".format(output_path))


if __name__ == "__main__":
    run_health_metric(DOC)

