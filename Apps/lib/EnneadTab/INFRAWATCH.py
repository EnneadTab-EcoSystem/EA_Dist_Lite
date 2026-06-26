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

import os

from EnneadTab import ENVIRONMENT
from EnneadTab.SYSTEM import APPS, TaskType
from EnneadTab import TASK_REGISTER

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


def _bat_path(app_config):
    rel = app_config.get("file_name", "")
    if not rel:
        return ""
    return os.path.normpath(
        os.path.join(ENVIRONMENT.ROOT, "Apps", "lib", "ExeProducts", rel)
    )


def register_if_needed():
    """Register InfraWatch scheduled tasks on this machine, if eligible."""
    global _RAN_THIS_PROCESS
    if _RAN_THIS_PROCESS:
        return
    _RAN_THIS_PROCESS = True

    hostname = _hostname()
    try:
        for legacy in _LEGACY_TASK_NAMES:
            if TASK_REGISTER.task_exists(legacy):
                TASK_REGISTER.delete_task(legacy)

        for app in _infra_apps():
            if not _is_in_canary(app):
                continue
            bat = _bat_path(app)
            if not bat or not os.path.exists(bat):
                continue
            TASK_REGISTER.register_app_task(bat, app, hostname, skip_if_exists=True)
    except:
        pass


def unregister_all():
    """Idempotent removal of InfraWatch tasks."""
    for legacy in _LEGACY_TASK_NAMES:
        TASK_REGISTER.delete_task(legacy)
    for app in _infra_apps():
        if "task_name" in app:
            TASK_REGISTER.delete_task(app["task_name"])
