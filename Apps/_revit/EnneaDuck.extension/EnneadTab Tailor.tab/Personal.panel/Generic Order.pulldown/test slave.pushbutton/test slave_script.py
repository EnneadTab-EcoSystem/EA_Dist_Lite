#!/usr/bin/python
# -*- coding: utf-8 -*-

__doc__ = "Run RevitSlave5 health metrics on the active document and save the report locally."
__title__ = "test slave"

from pyrevit import script  # pyright: ignore

import proDUCKtion  # pyright: ignore
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

REVITSLAVE5_LOGIC_PATH = r"C:\Users\szhang\github\HealthMetric\RevitSlave-5.0\revit_logic"

try:
    LONG_TYPE = long  # type: ignore # noqa: F821
except NameError:
    LONG_TYPE = int

try:
    basestring  # type: ignore # noqa: F821
except NameError:
    basestring = (str, bytes)  # type: ignore


def _format_number(value):
    if value is None:
        return "0"
    try:
        return "{0:,}".format(int(value))
    except Exception:
        return str(value)


def _top_entries(mapping, limit):
    if not isinstance(mapping, dict):
        return []
    items = []
    iterator = getattr(mapping, "iteritems", None)
    if iterator:
        iterable = iterator()
    else:
        iterable = mapping.items()
    for key, value in iterable:
        items.append((key, value))
    items.sort(key=lambda x: x[1], reverse=True)
    return items[:limit]


def _build_health_summary(health_report, error_message):
    summary = {
        "document_title": health_report.get("document_title"),
        "timestamp": health_report.get("timestamp"),
        "overall_status": "error" if error_message else "ok",
        "headline": "",
        "bullets": [],
        "metrics": {},
    }

    checks = health_report.get("checks") or {}
    cad = checks.get("cad_files") or {}
    families = checks.get("families") or {}
    warnings = checks.get("warnings") or {}
    materials = checks.get("materials") or {}
    views = checks.get("views_sheets") or {}

    dwg_files = cad.get("dwg_files")
    imported_dwgs = cad.get("imported_dwgs")
    linked_dwgs = cad.get("linked_dwgs")

    critical_warning_count = warnings.get("critical_warning_count")
    warning_users = warnings.get("warning_count_per_user") or {}
    warnings_by_editor = warning_users.get("by_last_editor") or {}
    top_warning_users = _top_entries(warnings_by_editor, 3)

    views_not_on_sheets = views.get("views_not_on_sheets")
    total_views = views.get("total_views")
    total_sheets = views.get("total_sheets")

    total_families = families.get("total_families")
    in_place = families.get("in_place_families")
    non_parametric = families.get("non_parametric_families")
    unused_families = families.get("unused_families_count")

    material_count = materials.get("materials")

    headline_parts = []
    if critical_warning_count is not None:
        headline_parts.append("{} critical warnings".format(_format_number(critical_warning_count)))
    if views_not_on_sheets is not None:
        headline_parts.append("{} unplaced views".format(_format_number(views_not_on_sheets)))
    if dwg_files is not None:
        headline_parts.append("{} DWGs".format(_format_number(dwg_files)))
    summary["headline"] = " | ".join(headline_parts) if headline_parts else "Health metrics summary"

    if dwg_files is not None:
        summary["bullets"].append(
            "CAD linkage: {0} DWGs ({1} imported / {2} linked)".format(
                _format_number(dwg_files),
                _format_number(imported_dwgs),
                _format_number(linked_dwgs),
            )
        )
    if total_families is not None:
        summary["bullets"].append(
            "Families: {0} total, {1} in-place, {2} non-parametric, {3} unused".format(
                _format_number(total_families),
                _format_number(in_place),
                _format_number(non_parametric),
                _format_number(unused_families),
            )
        )
    if material_count is not None:
        summary["bullets"].append("Materials: {0}".format(_format_number(material_count)))
    if total_views is not None:
        summary["bullets"].append(
            "Sheets & views: {0} views ({1} not on sheets) across {2} sheets".format(
                _format_number(total_views),
                _format_number(views_not_on_sheets),
                _format_number(total_sheets),
            )
        )
    if critical_warning_count is not None:
        if top_warning_users:
            user_parts = []
            for name, count in top_warning_users:
                user_parts.append("{0} ({1})".format(name, _format_number(count)))
            summary["bullets"].append(
                "Warnings: {0} critical – top editors {1}".format(
                    _format_number(critical_warning_count), ", ".join(user_parts)
                )
            )
        else:
            summary["bullets"].append("Warnings: {0} critical".format(_format_number(critical_warning_count)))

    summary["metrics"] = {
        "dwg_files": dwg_files,
        "critical_warning_count": critical_warning_count,
        "views_not_on_sheets": views_not_on_sheets,
        "total_views": total_views,
        "total_sheets": total_sheets,
        "total_families": total_families,
        "in_place_families": in_place,
        "non_parametric_families": non_parametric,
        "unused_families": unused_families,
        "materials": material_count,
    }

    summary["shareable_markdown"] = "*{0}*\n- {1}".format(
        summary.get("document_title", "Health Metric"), "\n- ".join(summary["bullets"])
    )

    return summary


def _to_json_safe(value):
    if value is None:
        return None

    if isinstance(value, (bool, int, float, basestring)):  # type: ignore # noqa: F821
        if isinstance(value, LONG_TYPE):
            return int(value)
        return value

    if isinstance(value, dict):
        safe_dict = {}
        iterator = getattr(value, "iteritems", None)
        if iterator:
            iterator = iterator()
        else:
            iterator = value.items()
        for key, val in iterator:
            safe_key = key
            if isinstance(key, LONG_TYPE):
                safe_key = str(int(key))
            safe_dict[safe_key] = _to_json_safe(val)
        return safe_dict

    if isinstance(value, (list, tuple, set)):
        return [_to_json_safe(item) for item in value]

    return repr(value)


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


def _get_revitslave5_paths():
    logic_path = os.path.normpath(REVITSLAVE5_LOGIC_PATH)
    health_path = os.path.join(logic_path, "health_metric")

    if not os.path.isdir(logic_path):
        raise Exception("RevitSlave5 logic folder not found: {}".format(logic_path))

    if not os.path.isdir(health_path):
        raise Exception("RevitSlave5 health_metric folder not found: {}".format(health_path))

    return logic_path, health_path


@LOG.log(__file__, __title__)
@ERROR_HANDLE.try_catch_error()
def run_health_metric(doc):
    if doc is None:
        NOTIFICATION.messenger("No active Revit document was found.")
        return

    repo_root = _resolve_repo_root()
    revitslave_logic_path, health_metric_path = _get_revitslave5_paths()

    if revitslave_logic_path not in sys.path:
        sys.path.append(revitslave_logic_path)

    if health_metric_path not in sys.path:
        sys.path.append(health_metric_path)

    health_metric_module = importlib.import_module("health_metric")
    HealthMetric = getattr(health_metric_module, "HealthMetric")

    debug_root = os.path.join(repo_root, "DEBUG", "RevitSlave", "test_slave_button")
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

    summary_payload = _build_health_summary(health_report, error_message)

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
            "health_metric_path": health_metric_path,
        },
        "health_metric_result": health_report,
        "export_data": None,
        "status": "completed" if not error_message else "completed with errors",
        "error": error_message,
        "shareable_summary": summary_payload,
    }

    safe_payload = _to_json_safe(output_payload)

    try:
        with open(output_path, "w") as handle:
            json.dump(safe_payload, handle, indent=2)
    except Exception as write_error:
        fallback_dir = _ensure_dir(os.path.join(debug_root, "output"))
        output_path = os.path.join(fallback_dir, output_name)
        with open(output_path, "w") as handle:
            json.dump(safe_payload, handle, indent=2)
        script.get_output().print_md(
            "- Could not write to button folder ({}). Saved to fallback: `{}`".format(write_error, output_path)
        )

    out = script.get_output()
    out.close_others()
    out.print_md("### RevitSlave5 Health Metric")
    out.print_md("- Using health metric module at `{}`".format(health_metric_path))
    out.print_md("- Saved report to `{}`".format(output_path))
    out.print_md(
        "This is a test RevitSlave script to run on a fully open Revit document. The idea is to test if there are any API errors in the health metric logic by importing directly from the RevitSlave5 remote folder. "
        "Host running script: `{}`.".format(os.path.abspath(__file__))
    )
    if summary_payload.get("headline"):
        out.print_md("### Quick Shareable Summary")
        out.print_md("- {}".format(summary_payload["headline"]))
        for bullet in summary_payload.get("bullets", []):
            out.print_md("- {}".format(bullet))
    if error_message:
        out.print_md("- Metrics completed with warnings/errors: {}".format(error_message))
        if os.path.exists(crash_log_path):
            out.print_md("- Crash log saved to `{}`".format(crash_log_path))
    else:
        out.print_md("- Metrics completed successfully.")

    NOTIFICATION.messenger("Health metric saved to:\n{}".format(output_path))


if __name__ == "__main__":
    run_health_metric(DOC)

