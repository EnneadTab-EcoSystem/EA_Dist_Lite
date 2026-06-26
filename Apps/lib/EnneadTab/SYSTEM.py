#!/usr/bin/python
# -*- coding: utf-8 -*-

"""
EnneadTab System Utilities

Provides system-level utilities and monitoring functions for the EnneadTab ecosystem.
Includes system uptime monitoring, resource checks, and system health notifications.
Compatible with both IronPython 2.7 and CPython 3.x environments.
"""
import os
import re
import shutil
import datetime
import time
import random
import json
import traceback
import NOTIFICATION, DATA_FILE,USER,  EXE, FOLDER, ENVIRONMENT, ERROR_HANDLE
import threading


# Define task types using class variables for Python 2.7 compatibility
class TaskType:
    STARTUP = "startup"    # Run when PC starts
    REPEAT = "repeat"      # Run every X minutes
    DAILY = "daily"        # Run daily at specific time
    WEEKLY = "weekly"      # Run weekly (staggered for fleet collectors)

APPS = [
    {
        "app_name": "EnneadTab_OS_Installer",
        "file_name": "EnneadTab_OS_Installer.exe",
        "shortcut_name": "EnneadTab_OS_Installer",
        "description": "Auto Run At Login",
        "task_name": "EnneadTab_OS_Installer_Task",
        "task_type": TaskType.REPEAT,
        "interval_minutes": 45,
        "active": True
    },
    {
        "app_name": "ClearRevitRhinoCache",
        "file_name": "ClearRevitRhinoCache.exe",
        "shortcut_name": "EnneadTab_Cache_Cleaner",
        "description": "EnneadTab Clean Revit/Rhino Cache Auto Run At The Login",
        "task_type": TaskType.STARTUP,
        "active": True
    },
    {
        "app_name": "AccAutoRestarter",
        "file_name": "AccAutoRestarter.exe",
        "shortcut_name": "EnneadTab_Acc_Auto_Restarter",
        "description": "EnneadTab ACC Connector Auto Restarter Auto Run At The Login",
        "task_type": TaskType.STARTUP,
        "active": False
    },
    {
        "app_name": "AutoReconnectDrive",
        "file_name": "AutoReconnectDrive.exe",
        "shortcut_name": "EnneadTab_Auto_Reconnect_Drives",
        "description": "EnneadTab Auto Reconnect Drives Task",
        "task_name": "EnneadTab_Auto_Reconnect_Drives_Task",
        "task_type": TaskType.REPEAT,
        "interval_minutes": 73,
        "active": False
    },
    {
        "app_name": "AutoReconnectDrive",
        "file_name": "AutoReconnectDrive.exe",
        "shortcut_name": "EnneadTab_Auto_Reconnect_Drives_StartUp",
        "description": "EnneadTab_Auto_Reconnect_Drives at startup",
        "task_type": TaskType.STARTUP,
        "active": False
    },
    {
        "app_name": "Rhino8RuiUpdater",
        "file_name": "Rhino8RuiUpdater.exe",
        "shortcut_name": "EnneadTab_Rhino8RuiUpdater",
        "task_name": "EnneadTab_Rhino8RuiUpdater_Task",
        "description": "EnneadTab Rhino8RuiUpdater",
        "task_type": TaskType.REPEAT,
        "interval_minutes": 25,
        "active": True
    },
    {
        # 2026-06-26 (#1816): retired 15-min monolith -- replaced by split Events 60m +
        # Heavy 6h entries below. Kept inactive so RegisterAutoStartup removes the
        # legacy scheduled task on next enrollment pass.
        "app_name": "InfraWatch_Collect",
        "file_name": r"..\DumpScripts\collectors\run_collectors.bat",
        "shortcut_name": "EnneadTab_InfraWatch_Collect",
        "task_name": "EnneadTab_InfraWatch_Collect_Task",
        "description": "DEPRECATED -- use InfraWatch_Events + InfraWatch_Heavy",
        "task_type": TaskType.REPEAT,
        "interval_minutes": 15,
        "active": False
    },
    {
        # Plane B -- hourly connectivity probe + BSOD/events (not plugin usage).
        "app_name": "InfraWatch_Events",
        "file_name": r"..\DumpScripts\collectors\run_collectors.bat",
        "task_args": "--events-only",
        "shortcut_name": "EnneadTab_InfraWatch_Events",
        "task_name": "EnneadTab_InfraWatch_Events_Task",
        "description": "EnneadTab InfraWatch hourly events + drive connectivity to enneadtab.com/infra",
        "task_type": TaskType.REPEAT,
        "interval_minutes": 60,
        "canary_hosts": ["MININT-5V26DTJ", "EANY-PW-0HJ97N"],
        "active": True
    },
    {
        # Plane B -- 6h heavy sweep: drive latency/capacity + machine spec.
        "app_name": "InfraWatch_Heavy",
        "file_name": r"..\DumpScripts\collectors\run_collectors.bat",
        "task_args": "--heavy",
        "shortcut_name": "EnneadTab_InfraWatch_Heavy",
        "task_name": "EnneadTab_InfraWatch_Heavy_Task",
        "description": "EnneadTab InfraWatch heavy collectors to enneadtab.com/infra",
        "task_type": TaskType.REPEAT,
        "interval_minutes": 360,
        "canary_hosts": ["MININT-5V26DTJ", "EANY-PW-0HJ97N"],
        "active": True
    },
    {
        # Plane B -- weekly Revit journal upload (pilot % gate inside collector).
        "app_name": "InfraWatch_Journal",
        "file_name": r"..\DumpScripts\collectors\run_collectors.bat",
        "task_args": "--journals-only",
        "shortcut_name": "EnneadTab_Journal_Collect",
        "task_name": "EnneadTab_Journal_Collect_Task",
        "description": "EnneadTab weekly Revit journal upload to enneadtab.com/infra",
        "task_type": TaskType.WEEKLY,
        "stagger_weekly": True,
        "canary_hosts": ["MININT-5V26DTJ", "EANY-PW-0HJ97N"],
        "active": True
    },
    {
        "app_name": "WhatTheLunch",
        "file_name": "WhatTheLunch.exe",
        "shortcut_name": "WhatTheLunch",
        "task_name": "WhatTheLunch_Daily",
        "description": "WhatTheLunch Daily Task at 11:45",
        "task_type": TaskType.DAILY,
        "daily_time": "11:45",
        "active": True
    },
    {
        "app_name": "AvdResourceMonitor",
        "file_name": "AvdResourceMonitor.exe",
        "shortcut_name": "AvdResourceMonitor",
        "task_name": "AvdResourceMonitor",
        "description": "AvdResourceMonitor to check the CPU usage",
        "task_type": TaskType.STARTUP,
        "active": False
    },
    # 2026-04-21: DriveStorageHistory + MonitorBlueScreen retired. InfraWatch
    # collectors are Plane B scheduled tasks (InfraWatch_Events / Heavy above).
    {
        "app_name": "AboutMe_ComputerInfo_Silent",
        "file_name": "AboutMe_ComputerInfo_Silent.exe",
        "shortcut_name": "AboutMe_ComputerInfo_Silent",
        "description": "AboutMe_ComputerInfo_Silent",
        "task_type": TaskType.STARTUP,
        "active": False
    }
]


def parse_timestamp(timestamp_str):
    """Parse timestamp string that can be in two different formats.
    
    Args:
        timestamp_str (str): Timestamp in either 'YYYY-MM-DD HH:MM:SS' or 'YYYYMMDD HHMMSS' format
        
    Returns:
        datetime.datetime: Parsed datetime object
        
    Raises:
        ValueError: If timestamp cannot be parsed in either format
    """
    # Try the newer format first (YYYYMMDD HHMMSS)
    try:
        return datetime.datetime.strptime(timestamp_str, "%Y%m%d %H%M%S")
    except ValueError:
        pass
    
    # Try the older format (YYYY-MM-DD HH:MM:SS)
    try:
        return datetime.datetime.strptime(timestamp_str, "%Y-%m-%d %H:%M:%S")
    except ValueError:
        pass
    
    # If neither format works, raise an error
    raise ValueError("Cannot parse timestamp: {}".format(timestamp_str))

def _fetch_publish_status_api():
    """Fetch the latest publish event from InfraWatch.

    Transport order mirrors ERROR_HANDLE.send_error_to_error_dump: .NET
    HttpWebRequest first, because urllib HTTPS silently fails under
    IronPython on some office network segments (see memory:
    feedback_ironpython_networking), then urllib for CPython.

    Uses the direct vercel domain (same as the InfraWatch collectors in
    infrawatch_common.py): the enneadtab.com proxy would subject the request
    to EnneadTabHome auth, and this is InfraWatch's deliberately
    unauthenticated read route.

    Returns:
        dict: Parsed JSON response, or None on any failure.
    """
    url = "https://infrawatch-ennead-projects.vercel.app/infra/api/publish-status/history?limit=1"

    # Transport 1: .NET HttpWebRequest (IronPython 2.7 inside Revit/Rhino)
    try:
        import clr  # noqa: F401  (IronPython interop gate)
        clr.AddReference("System")
        from System.Net import WebRequest, ServicePointManager, SecurityProtocolType
        from System.IO import StreamReader

        try:
            ServicePointManager.SecurityProtocol = SecurityProtocolType.Tls12
        except Exception:
            pass

        req = WebRequest.Create(url)
        req.Method = "GET"
        req.Timeout = 5000  # milliseconds
        resp = req.GetResponse()
        try:
            reader = StreamReader(resp.GetResponseStream())
            body = reader.ReadToEnd()
        finally:
            resp.Close()
        return json.loads(body)
    except ImportError:
        pass  # not running under IronPython / .NET - fall through to urllib paths
    except Exception:
        pass

    # Transport 2: urllib.request (CPython 3.x)
    try:
        from urllib.request import urlopen
        response = urlopen(url, timeout=5)
        return json.loads(response.read().decode("utf-8"))
    except ImportError:
        pass
    except Exception:
        pass

    # Transport 3: urllib2 (legacy CPython 2.7)
    try:
        import urllib2
        response = urllib2.urlopen(url, timeout=5)
        return json.loads(response.read())
    except Exception:
        pass

    return None


def _alert_publish_freshness(timestamp_dt, was_success, now_dt, display_timestamp):
    """Duck-pop if the most recent publish is more than 1 day old or failed.

    now_dt must be in the same time domain as timestamp_dt: the API reports
    UTC (caller passes utcnow()), the local history file is machine-local
    time (caller passes now()).
    """
    time_diff = now_dt - timestamp_dt

    # Check if more than 1 day old
    is_old = time_diff.total_seconds() > 24 * 60 * 60  # 1 day in seconds

    # Alert if most recent is more than 1 day old OR if it failed
    if is_old or not was_success:
        if is_old and not was_success:
            message = "Yikes! Last publish was {} ago AND it failed! Time to fix things up!".format(
                format_time_diff(time_diff)
            )
        elif is_old:
            message = "Hey there! Last publish was {} ago. Maybe time for an update?".format(
                format_time_diff(time_diff)
            )
        else:
            message = "Oops! Last publish failed at {}. Better check what went wrong!".format(
                display_timestamp
            )

        ERROR_HANDLE.print_note("DEBUG: Would show duck pop message: {}".format(message))
        NOTIFICATION.duck_pop(message)
    else:
        ERROR_HANDLE.print_note("DEBUG: All good! Most recent publish at {} was successful and recent.".format(display_timestamp))


def alert_missing_schedule_update():
    if not USER.IS_DEVELOPER:
        return

    # Primary source: InfraWatch publish_runs (migrated from EnneadTab-Sync
    # 2026-06-11; before that, a status gist the publisher stopped updating
    # in March 2026).
    try:
        data = _fetch_publish_status_api()
        if data:
            last_publish = (data.get("stats") or {}).get("last_publish")
            if last_publish and last_publish.get("created_at"):
                created_at = str(last_publish.get("created_at"))
                # created_at is ISO 8601 UTC (e.g. 2026-03-24T18:44:59.246Z);
                # slice to whole seconds to avoid strptime %f/%z quirks on
                # IronPython, and compare against utcnow() to match domains
                timestamp_dt = datetime.datetime.strptime(created_at[:19], "%Y-%m-%dT%H:%M:%S")
                _alert_publish_freshness(
                    timestamp_dt,
                    last_publish.get("success", False),
                    datetime.datetime.utcnow(),
                    created_at,
                )
                return
            # last_publish is null when the table is empty: fall through to
            # the local file rather than alarming on missing data
    except Exception as e:
        ERROR_HANDLE.print_note("Error reading publish status API: {}".format(e))

    # Fallback: local publish history (only present on the publish machine)
    history = os.path.join(ENVIRONMENT.ROOT, "DarkSide", "publish", "publish_history.json")
    if not os.path.exists(history):
        return
    try:
        with open(history, "r") as f:
            data = json.load(f)
    except Exception as e:
        ERROR_HANDLE.print_note("Error reading publish history: {}".format(e))
        return

    runs = data.get("runs", [])
    if not runs:
        return

    # Sort records by timestamp (most recent first)
    try:
        sorted_runs = sorted(runs, key=lambda x: parse_timestamp(x["timestamp"]), reverse=True)
    except Exception as e:
        ERROR_HANDLE.print_note("Error sorting publish history: {}".format(e))
        return

    most_recent = sorted_runs[0]
    most_recent_timestamp = most_recent["timestamp"]

    try:
        timestamp_dt = parse_timestamp(most_recent_timestamp)
        # local-file timestamps are written in machine-local time
        # (_schedule_publish.py uses now()), so the baseline here stays now()
        _alert_publish_freshness(
            timestamp_dt,
            most_recent.get("success", False),
            datetime.datetime.now(),
            most_recent_timestamp,
        )
    except Exception as e:
        ERROR_HANDLE.print_note("Error processing timestamp: {}".format(e))
        return

def format_time_diff(time_diff):
    """Helper function to format time difference in human readable format."""
    days = int(time_diff.total_seconds() // (24 * 60 * 60))
    hours = int((time_diff.total_seconds() % (24 * 60 * 60)) // (60 * 60))
    
    if days > 0:
        if hours > 0:
            return "{} days and {} hours".format(days, hours)
        else:
            return "{} days".format(days)
    else:
        return "{} hours".format(hours)

def get_system_uptime():
    """Get system uptime in seconds for Windows systems, compatible with both Python 3 and IronPython 2.7.
    
    Returns:
        float: System uptime in seconds. Returns 0 if calculation fails.
    """
    try:
        # Try IronPython 2.7 approach first
        from System.Diagnostics import Process # type: ignore
        uptime = time.time() - Process.GetCurrentProcess().StartTime.ToUniversalTime().Ticks / 10000000.0
        if uptime < 0:
            raise ValueError("Negative uptime detected")
        return uptime
    except (ImportError, ValueError):
        try:
            # Try Python 3 approach with ctypes
            import ctypes
            lib = ctypes.windll.kernel32
            tick_count = lib.GetTickCount64()
            return tick_count / 1000.0  # Convert milliseconds to seconds
        except:
            return 0

def check_system_uptime():
    """Check system uptime and send notification if it exceeds 7 days.
    
    Monitors the system's uptime and sends a notification if the system has been
    running for more than 7 days. This helps prevent system performance degradation
    due to extended uptime. Checks are limited to once per hour to avoid spam.
    
    Returns:
        float: System uptime in seconds
    """
    # Get last check time from data file
    last_check_data = DATA_FILE.get_data("system_uptime_check") or {}
    last_check_time = last_check_data.get("last_check_time", 0)
    
    # Only proceed if more than 1 hour has passed since last check
    if time.time() - last_check_time < 3600:  # 3600 seconds = 1 hour
        return last_check_data.get("last_uptime", 0)
    
    uptime = get_system_uptime()
    
    # Update last check time and uptime
    DATA_FILE.set_data({
        "last_check_time": time.time(),
        "last_uptime": uptime
    }, "system_uptime_check")
    
    if uptime > 7 * 24 * 60 * 60:  # 7 days in seconds
        days = int(uptime / (24 * 60 * 60))
        hours = int((uptime % (24 * 60 * 60)) / (60 * 60))
        uptime_messages = [
            "No one even work their donkey this hard.\nYour computer has been running for {} days and {} hours. Consider restarting your computer for optimal performance.",
            "Let me sleep, please please please.\nThis PC has been awake for {} days and {} hours.",
            "Your revit file is about to form a union becuase of how much overworked there is.\nFun fact: your computer hasn't rebooted in {} days and {} hours.",
            "Treat your revit file to a restart spa day.\nThis copmuter has survived {} days and {} hours without a reboot.",
            "Reboot before dust bunnies start paying rent.\nWe're seeing {} days and {} hours of nonstop revit usage.",
        ]
        NOTIFICATION.messenger(random.choice(uptime_messages).format(days, hours))
    return uptime

def purge_powershell_folder():
    """Clean up PowerShell transcript folders that match YYYYMMDD pattern.
    
    This function:
    1. Scans Documents folder for YYYYMMDD pattern folders
    2. Checks for PowerShell_transcript files inside
    3. Deletes matching folders
    4. Runs once per day using timestamp check
    
    """

    
    # Get the documents folder path
    docs_folder = ENVIRONMENT.USER_DOCUMENT_FOLDER
    if not os.path.exists(docs_folder):
        return
    
    # Check if we already ran today
    timestamp_file = FOLDER.get_local_dump_folder_file("last_ps_cleanup.txt")
    
    try:
        with open(timestamp_file, 'r') as f:
            last_run = f.read().strip()
            if last_run == datetime.datetime.now().strftime("%Y%m%d"):
                return
    except:
        pass
        
    # Pattern for YYYYMMDD folders
    date_pattern = re.compile(r"^\d{8}$")
    
    folders_to_delete = []
    
    # Scan for matching folders
    for folder_name in os.listdir(docs_folder):
        folder_path = os.path.join(docs_folder, folder_name)
        
        # Check if it's a directory and matches date pattern
        if os.path.isdir(folder_path) and date_pattern.match(folder_name):
            # Check if contains PowerShell transcripts
            has_ps_transcript = False
            for file in os.listdir(folder_path):
                if "PowerShell_transcript" in file:
                    has_ps_transcript = True
                    break
            if len(os.listdir(folder_path)) == 0:
                folders_to_delete.append(folder_path)
                    
            if has_ps_transcript:
                folders_to_delete.append(folder_path)
    
    # Actual deletion
    deleted_count = 0
    for folder in folders_to_delete:
        try:
            # Try to delete entire folder tree first
            shutil.rmtree(folder)
            deleted_count += 1
        except Exception as e:
            # If folder deletion fails, try deleting individual files
            try:
                files = os.listdir(folder)
                for file in files:
                    file_path = os.path.join(folder, file)
                    try:
                        if os.path.isfile(file_path):
                            os.remove(file_path)
                        elif os.path.isdir(file_path):
                            shutil.rmtree(file_path)
                    except Exception:
                        continue
                # Try deleting empty folder again
                os.rmdir(folder)
                deleted_count += 1
            except Exception:
                continue
        
    # Update timestamp file
    with open(timestamp_file, 'w') as f:
        f.write(datetime.datetime.now().strftime("%Y%m%d"))
    
    return folders_to_delete



def about_me():
    return
    try:
        EXE.try_open_app("AboutMe_ComputerInfo_Silent", safe_open=True)
    except Exception as e:
        ERROR_HANDLE.print_note("Error opening AboutMe_ComputerInfo_Silent: {}".format(e))





def run_system_checks():
    """Run system checks with configurable probabilities.
    
    This function runs various system checks and maintenance tasks based on
    random probability values. Each check has its own probability threshold.
    Checks are limited to once per hour to prevent excessive system load using
    environment variables for lightweight tracking between sessions.
    
    Returns:
        bool: True if checks were performed, False if skipped due to frequency limit
    """
    # Check if we already ran recently using environment variable
    env_var_name = "LAST_SYSTEM_CHECK"
    
    try:
        last_check_time_str = os.environ.get(env_var_name, "0")
        last_check_time = float(last_check_time_str)
    except (ValueError, TypeError):
        last_check_time = 0
    
    # Only proceed if more than 1 hour has passed since last check
    if time.time() - last_check_time < 1800:  # 1800 seconds = 30 minutes
        return False
    
    # Generate a single random number for all probability checks
    random_value = random.random()
    
    # Define check probabilities
    checks = [
        (0.02, "InfraWatch_Collect"),
        (0.01, "AccAutoRestarter"),
        (0.02, "RegisterAutoStartup"),
        (0.03, "Rhino8RuiUpdater"),
        (0.05, check_system_uptime),
        (0.03, purge_powershell_folder),
        (0.05, about_me)

    ]
    
    # Run checks based on probability
    for probability, check in checks:
        if random_value < probability:
            if callable(check):
                check()
            else:
                EXE.try_open_app(check, safe_open=True)

    # this is only for developer and it is handled inside the function
    alert_missing_schedule_update()
    
    # Update last check time in environment variable
    os.environ[env_var_name] = str(time.time())
    
    return True

# Run system checks when module is imported
run_system_checks()


if __name__ == "__main__":
    about_me()
    # from REVIT import REVIT_ACC # type: ignore

    # REVIT_ACC.get_ACC_summary_data(show_progress=True)

