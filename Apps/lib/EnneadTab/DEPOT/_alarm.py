# -*- coding: utf-8 -*-
"""Depot-unreachable alarm -- loud once, then quiet.

A straight port of ENVIRONMENT.announce_shared_root_status (plan 5.3): fire at
most once per process, and at most once per 24h per machine (a marker file under
the cache dir plays the DuckLock role). Lazy, guarded imports of NOTIFICATION so
this never drags a UI dependency into ENVIRONMENT's import graph, and it NEVER
raises -- an alarm that crashes the button is worse than no alarm.

Both ASSET (offline read) and STATE (offline write, Commit 3) call this.
"""

import os
import time

from EnneadTab import ENVIRONMENT

_ANNOUNCED_THIS_PROCESS = False
_MARKER_NAME = ".depot_unreachable_alarm"
_QUIET_SECONDS = 24 * 60 * 60


def _marker_path():
    return os.path.join(ENVIRONMENT.DEPOT_CACHE_FOLDER, _MARKER_NAME)


def _within_quiet_window():
    """True if the 24h marker exists and is fresh (so we should stay quiet)."""
    path = _marker_path()
    try:
        if not os.path.exists(path):
            return False
        return (time.time() - os.path.getmtime(path)) < _QUIET_SECONDS
    except Exception:
        return False


def _touch_marker():
    path = _marker_path()
    try:
        d = os.path.dirname(path)
        if d and not os.path.exists(d):
            os.makedirs(d)
        f = open(path, "w")
        try:
            f.write(str(time.time()))
        finally:
            f.close()
    except Exception:
        pass


def announce_depot_unreachable(context=""):
    """Notify the user once that the depot is unreachable and work is offline.
    Idempotent per process and rate-limited to once per 24h per machine. Returns
    True if it actually announced this call, else False. Never raises."""
    global _ANNOUNCED_THIS_PROCESS
    if _ANNOUNCED_THIS_PROCESS:
        return False
    _ANNOUNCED_THIS_PROCESS = True
    if _within_quiet_window():
        return False
    _touch_marker()
    msg = ("EnneadTab could not reach the shared depot (enneadtab.com). "
           "Working from the local cache; new shared data may be unavailable "
           "until the connection returns.")
    if context:
        msg = msg + " [" + str(context) + "]"
    try:
        from EnneadTab import NOTIFICATION
        NOTIFICATION.messenger(msg)
    except Exception:
        pass
    try:
        from EnneadTab import ERROR_HANDLE
        ERROR_HANDLE.print_note(msg)
    except Exception:
        pass
    return True
