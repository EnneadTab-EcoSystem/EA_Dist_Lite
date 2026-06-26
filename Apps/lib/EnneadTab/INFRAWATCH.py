# -*- coding: utf-8 -*-
"""InfraWatch fleet bootstrap. IronPython 2.7 compatible.

Idempotent task registration called from plugin_startup.py (Revit) and
_rhino/startup.py. Reads infra entries from SYSTEM.APPS (sole config source).

Repair hook only: re-register missing InfraWatch_* tasks on eligible hosts.
RegisterAutoStartup.exe skips InfraWatch_* entries -- this module owns them.

Safety layers:
  1. canary_hosts on each APPS entry (or "*" for fleet)
  2. .infrawatch_kill sentinel disables collector POSTs without re-enroll
"""

import hashlib
import os
import subprocess

from EnneadTab import ENVIRONMENT
from EnneadTab.SYSTEM import APPS, TaskType


# Legacy task names removed during #1816 enrollment cleanup.
_LEGACY_TASK_NAMES = [
    "EnneadTab_InfraWatch_Collect_Task",
    "InfraWatch-Heavy",
    "InfraWatch-Events",
]

_RAN_THIS_PROCESS = False


def _hostname():
    return os.environ.get("COMPUTERNAME", "")


def _is_in_canary(app_config):
    hosts = app_config.get("canary_hosts")
    if not hosts:
        return False
    if "*" in hosts:
        return True
    return _hostname() in hosts


def _infra_apps():
    apps = []
    for app in APPS:
        name = app.get("app_name", "")
        if not name.startswith("InfraWatch_"):
            continue
        if not app.get("active", True):
            continue
        task_type = app.get("task_type")
        if task_type not in (TaskType.REPEAT, TaskType.WEEKLY):
            continue
        if "task_name" not in app:
            continue
        apps.append(app)
    return apps


def compute_weekly_stagger(hostname=None):
    """Deterministic weekly day + off-hours time from hostname hash."""
    hname = hostname or _hostname()
    digest = hashlib.md5(hname.upper().encode("ascii")).hexdigest()
    h = int(digest, 16)
    days = ["SUN", "MON", "TUE", "WED", "THU", "FRI", "SAT"]
    weekly_day = days[h % 7]
    offset_min = (h // 7) % 360
    weekly_time = "{:02d}:{:02d}".format(2 + offset_min // 60, offset_min % 60)
    return weekly_day, weekly_time


def _weekly_schedule(app):
    if app.get("stagger_weekly"):
        return compute_weekly_stagger(_hostname())
    return app.get("weekly_day", "SUN"), app.get("weekly_time", "02:00")


def _bat_path(app_config):
    rel = app_config.get("file_name", "")
    if not rel:
        return ""
    return os.path.normpath(
        os.path.join(ENVIRONMENT.ROOT, "Apps", "lib", "ExeProducts", rel)
    )


def _task_exists(name):
    cmd = 'schtasks /query /tn "{}" >nul 2>&1'.format(name)
    try:
        rc = subprocess.call(cmd, shell=True)
        return rc == 0
    except Exception:
        return False


def _delete_task(name):
    cmd = 'schtasks /delete /tn "{}" /f >nul 2>&1'.format(name)
    try:
        subprocess.call(cmd, shell=True)
    except Exception:
        pass


def _create_repeat_task(name, bat, args, interval_minutes):
    # /sc minute /mo N matches RegisterAutoStartup REPEAT tasks.
    tr = '\\"{}\\" {}'.format(bat, args).strip()
    cmd = (
        'schtasks /create /tn "{}" /tr "{}" /sc minute /mo {} /f >nul 2>&1'
    ).format(name, tr, int(interval_minutes))
    try:
        rc = subprocess.call(cmd, shell=True)
        return rc == 0
    except Exception:
        return False


def _create_weekly_task(name, bat, args, weekly_day, weekly_time):
    tr = '\\"{}\\" {}'.format(bat, args).strip()
    cmd = (
        'schtasks /create /tn "{}" /tr "{}" /sc WEEKLY /D {} /ST {} /f >nul 2>&1'
    ).format(name, tr, weekly_day, weekly_time)
    try:
        rc = subprocess.call(cmd, shell=True)
        return rc == 0
    except Exception:
        return False


def register_if_needed():
    """Register InfraWatch scheduled tasks on this machine, if eligible."""
    global _RAN_THIS_PROCESS
    if _RAN_THIS_PROCESS:
        return
    _RAN_THIS_PROCESS = True

    try:
        for legacy in _LEGACY_TASK_NAMES:
            if _task_exists(legacy):
                _delete_task(legacy)

        for app in _infra_apps():
            if not _is_in_canary(app):
                continue
            bat = _bat_path(app)
            if not bat or not os.path.exists(bat):
                continue
            task_name = app["task_name"]
            if _task_exists(task_name):
                continue
            args = app.get("task_args", "")
            if app.get("task_type") == TaskType.WEEKLY:
                weekly_day, weekly_time = _weekly_schedule(app)
                _create_weekly_task(task_name, bat, args, weekly_day, weekly_time)
            else:
                interval = app.get("interval_minutes", 60)
                _create_repeat_task(task_name, bat, args, interval)
    except:
        pass


def unregister_all():
    """Idempotent removal of InfraWatch tasks."""
    for legacy in _LEGACY_TASK_NAMES:
        _delete_task(legacy)
    for app in _infra_apps():
        if "task_name" in app:
            _delete_task(app["task_name"])
