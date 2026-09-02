#!/usr/bin/python
# -*- coding: utf-8 -*-

__doc__ = """Identify the most recent Revit crash journal file and launch Crash Detective.

Scans %LOCALAPPDATA%\\Autodesk\\Revit\\*\\Journals for the latest journal session,
copies its path to the clipboard, and opens the Revit Crash Detective web app for instant diagnosis."""
__title__ = "Report\nLast Crash"
__context__ = "zero-doc"
__tip__ = True
import proDUCKtion # pyright: ignore
proDUCKtion.validify()

import os
import glob
import webbrowser
from EnneadTab import ERROR_HANDLE, LOG, NOTIFICATION, CLIPBOARD

CRASH_DETECTIVE_URL = "https://enneadtab.com/crash/"

def get_latest_journal():
    """Find the most recently modified journal file across all installed Revit versions."""
    local_app_data = os.environ.get("LOCALAPPDATA", "")
    if not local_app_data:
        return None
        
    revit_dir = os.path.join(local_app_data, "Autodesk", "Revit")
    if not os.path.exists(revit_dir):
        return None

    pattern = os.path.join(revit_dir, "Autodesk Revit *", "Journals", "journal.*.txt")
    journal_files = glob.glob(pattern)
    
    if not journal_files:
        pattern_fallback = os.path.join(revit_dir, "*", "Journals", "journal.*.txt")
        journal_files = glob.glob(pattern_fallback)

    if not journal_files:
        return None

    journal_files.sort(key=lambda p: os.path.getmtime(p), reverse=True)
    return journal_files[0]

@LOG.log(__file__, __title__)
@ERROR_HANDLE.try_catch_error()
def report_last_crash():
    latest_journal = get_latest_journal()
    
    if latest_journal and os.path.exists(latest_journal):
        try:
            CLIPBOARD.copy_to_clipboard(latest_journal)
        except Exception:
            pass
            
        file_name = os.path.basename(latest_journal)
        
        NOTIFICATION.messenger(
            main_text="Latest Journal Detected:\n{}\n\nFile path copied to clipboard! Drop it into Crash Detective.".format(file_name),
            sub_text="Launching Revit Crash Detective...",
            window_title="EnneadTab Crash Reporter"
        )
    else:
        NOTIFICATION.messenger(
            main_text="Could not automatically locate the latest Revit journal file.",
            sub_text="Opening Revit Crash Detective...",
            window_title="EnneadTab Crash Reporter"
        )

    webbrowser.open(CRASH_DETECTIVE_URL)

if __name__ == "__main__":
    report_last_crash()