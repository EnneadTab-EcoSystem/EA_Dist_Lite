# -*- coding: utf-8 -*-
"""InfraWatch fleet bootstrap. IronPython 2.7 compatible.

Idempotent task registration called from plugin_startup.py (Revit) and
_rhino/startup.py. Replaces the RegisterAutoStartup.exe pattern for
new collectors going forward -- no exe, no PyInstaller, no AV false
positives, full visibility.

Two layers of safety:
  1. Canary gate (this file)   -- only enrolls listed hostnames.
  2. Kill switch (collect_all) -- sentinel file at ROOT disables
     every collector POST without needing a re-enroll.

Once the canary list is broadened to "*", every Revit/Rhino startup on
every workstation will idempotently register the InfraWatch tasks. To
retire: empty CANARY_HOSTS or delete this module.
"""

import os
import socket
import subprocess

from EnneadTab import ENVIRONMENT


# --- Configuration -----------------------------------------------------------

# Hosts permitted to enroll. Use "*" to enable fleet-wide. Expand the
# allowlist incrementally as canaries prove healthy.
CANARY_HOSTS = ["MININT-5V26DTJ"]

# Tasks to register. Each becomes a user-level Windows Scheduled Task
# pointing at run_collectors.bat with the given args.
_TASKS = [
    {
        "name": "InfraWatch-Heavy",
        "args": "--heavy",
        "schedule": "/sc HOURLY /mo 6",
    },
    {
        "name": "InfraWatch-Events",
        "args": "--events-only",
        "schedule": "/sc HOURLY /mo 1",
    },
]

# Module-level guard so re-imports inside the same Revit/Rhino session
# don't re-shell-out 4 times per startup.
_RAN_THIS_PROCESS = False


# --- Helpers ----------------------------------------------------------------

def _bat_path():
    """Absolute path to the collector launcher inside EA_Dist / dev tree."""
    return os.path.join(
        ENVIRONMENT.ROOT,
        "Apps", "lib", "DumpScripts", "collectors", "run_collectors.bat",
    )


def _hostname():
    # COMPUTERNAME is the AD-joined Windows hostname; more reliable than
    # socket.gethostname() which sometimes returns FQDN.
    return os.environ.get("COMPUTERNAME", "")


def _is_in_canary():
    if "*" in CANARY_HOSTS:
        return True
    return _hostname() in CANARY_HOSTS


def _task_exists(name):
    cmd = 'schtasks /query /tn "{}" >nul 2>&1'.format(name)
    try:
        rc = subprocess.call(cmd, shell=True)
        return rc == 0
    except Exception:
        return False


def _create_task(name, bat, args, schedule):
    # /tr value gets double-quoted so paths with spaces survive cmd.exe
    # word-splitting (matches RegisterAutoStartup.py:131 escape pattern).
    tr = '\\"{}\\" {}'.format(bat, args)
    cmd = 'schtasks /create /tn "{}" /tr "{}" {} /f >nul 2>&1'.format(
        name, tr, schedule,
    )
    try:
        rc = subprocess.call(cmd, shell=True)
        return rc == 0
    except Exception:
        return False


# --- Public entry ------------------------------------------------------------

def register_if_needed():
    """Register InfraWatch scheduled tasks on this machine, if eligible.

    Safe to call repeatedly. Wrapped in broad except so a failure here
    can never break Revit/Rhino startup. Prints nothing on the success
    path -- silent enrollment is the goal.
    """
    global _RAN_THIS_PROCESS
    if _RAN_THIS_PROCESS:
        return
    _RAN_THIS_PROCESS = True

    try:
        if not _is_in_canary():
            return
        bat = _bat_path()
        if not os.path.exists(bat):
            return
        for spec in _TASKS:
            if _task_exists(spec["name"]):
                continue
            _create_task(spec["name"], bat, spec["args"], spec["schedule"])
    except:
        # Never crash startup. Collector POSTs themselves report to ErrorDump
        # if they fail, so we'll see downstream silence in InfraWatch as the
        # signal that a fleet of machines didn't enroll.
        pass


def unregister_all():
    """Idempotent removal of every InfraWatch task. Used by retirement."""
    for spec in _TASKS:
        cmd = 'schtasks /delete /tn "{}" /f >nul 2>&1'.format(spec["name"])
        try:
            subprocess.call(cmd, shell=True)
        except Exception:
            pass
