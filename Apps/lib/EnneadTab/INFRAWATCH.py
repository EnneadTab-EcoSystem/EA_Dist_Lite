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
import datetime

from EnneadTab import ENVIRONMENT
from EnneadTab.SYSTEM import APPS, TaskType
from EnneadTab import TASK_REGISTER

_LEGACY_TASK_NAMES = [
    "EnneadTab_InfraWatch_Collect_Task",
    "InfraWatch-Heavy",
    "InfraWatch-Events",
]

_RAN_THIS_PROCESS = False


def _log(reason):
    """Append one enrollment outcome line. Never raises, never blocks startup.

    2026-07-18: added because every skip path here was silent. A machine that
    was merely out-of-canary and a machine whose registration CRASHED produced
    identical output -- none -- which is why the InfraWatch dashboard sat at
    one reporting machine unnoticed (see EnneadTab-InfraWatch Amendment A).

    Deliberately a plain file append rather than LOG.py: this module runs on
    the Revit/Rhino startup path, so it must not pull heavy imports, must not
    slow launch, and must not be able to raise. Plane B collectors are
    decoupled from LOG.py for the same reason.
    """
    try:
        folder = ENVIRONMENT.DUMP_FOLDER
        if not os.path.exists(folder):
            os.makedirs(folder)
        line = "{} {} {}\n".format(
            datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
            _hostname(),
            reason,
        )
        with open(os.path.join(folder, "infrawatch_enroll.log"), "a") as f:
            f.write(line)
    except:
        # A logger that can break startup is worse than no logger.
        pass


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
            name = app.get("app_name", "?")
            if not _is_in_canary(app):
                _log("SKIP {} not-in-canary".format(name))
                continue
            bat = _bat_path(app)
            if not bat or not os.path.exists(bat):
                # Most likely failure mode now that canary_hosts is "*": the
                # collector .bat did not make it into this machine's EA_Dist.
                _log("SKIP {} bat-missing {}".format(name, bat or "<empty>"))
                continue
            TASK_REGISTER.register_app_task(bat, app, hostname, skip_if_exists=True)
            _log("OK {} registered".format(name))
    except Exception as e:
        # Still swallowed -- enrollment must never break Revit/Rhino startup --
        # but no longer silent.
        _log("FAIL register_if_needed {}".format(e))


def unregister_all():
    """Idempotent removal of InfraWatch tasks."""
    for legacy in _LEGACY_TASK_NAMES:
        TASK_REGISTER.delete_task(legacy)
    for app in _infra_apps():
        if "task_name" in app:
            TASK_REGISTER.delete_task(app["task_name"])
