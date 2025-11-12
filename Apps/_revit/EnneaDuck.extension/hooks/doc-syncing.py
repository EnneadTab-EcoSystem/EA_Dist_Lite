from pyrevit import EXEC_PARAMS
from Autodesk.Revit import DB # pyright: ignore
import io

import proDUCKtion # pyright: ignore 
proDUCKtion.validify()
from EnneadTab import VERSION_CONTROL, ERROR_HANDLE, LOG, DATA_FILE, TIME, USER, DUCK, CONFIG, FOLDER, TIMESHEET
from EnneadTab.REVIT import REVIT_FORMS, REVIT_SELECTION, REVIT_EVENT

__title__ = "Doc Syncing Hook"
DOC = EXEC_PARAMS.event_args.Document

# Sync queue configuration
SYNC_QUEUE_IGNORE_LIST = [
    "SPARC_A_EA_CUNY_Building",
]

QUEUE_EXPIRY_MINUTES = 30

QUEUE_DIALOG_FOOTER = "\n\nWhen There are no other people on the list, or you are the first on the wait list you can sync normally.\nRecord older than 30mins will be removed from the queue to avoid holding line too long."


# Helper functions for sync queue management

def _is_project_ignored(doc_title, ignore_list):
    """Check if project should bypass sync queue checking.
    
    Args:
        doc_title: Document title to check
        ignore_list: List of project names/patterns to ignore
        
    Returns:
        bool: True if project should bypass queue, False otherwise
    """
    if not doc_title:
        return False
        
    doc_title_lower = doc_title.lower()
    for ignored_project in ignore_list:
        if ignored_project.lower() in doc_title_lower:
            ERROR_HANDLE.print_note("Project '{}' is in sync queue ignore list, bypassing queue check.".format(doc_title))
            return True
    return False


def _cleanup_old_queue_records(queue):
    """Remove queue records older than QUEUE_EXPIRY_MINUTES.
    
    Args:
        queue: List of queue records in format "[timestamp]username"
        
    Returns:
        list: Cleaned queue with old records removed
    """
    cleaned_queue = []
    for existing_item in queue:
        try:
            record_unix_time = existing_item.split("]")[0].split("_")[1]
        except (IndexError, ValueError):
            # Keep records we can't parse
            cleaned_queue.append(existing_item)
            continue
        
        # Check if record has expired (default 30 mins)
        if TIME.time_has_passed_too_long(record_unix_time):
            ERROR_HANDLE.print_note("Removing record that is older than {} minutes so it is not holding queue: {}".format(QUEUE_EXPIRY_MINUTES, existing_item))
        else:
            cleaned_queue.append(existing_item)
    
    return cleaned_queue


def _add_user_to_queue_if_needed(queue, user_name, timestamp):
    """Add user to queue if not already present.
    
    Args:
        queue: List of queue records
        user_name: Username to add
        timestamp: Formatted timestamp
        
    Returns:
        tuple: (modified_queue, was_added) - Updated queue and boolean indicating if user was added
    """
    # Check if user is already in queue
    for existing_item in queue:
        if user_name in existing_item:
            return queue, False
    
    # Add user to end of queue
    data = "[{}]{}".format(timestamp, user_name)
    queue.append(data)
    return queue, True


def _build_queue_dialog_text(queue):
    """Build dialog text showing current queue status.
    
    Args:
        queue: List of queue records
        
    Returns:
        str: Formatted queue display text
    """
    queue_header = "Current Sync Queue:\n"
    queue_items = ["\n  -" + item for item in queue]
    return queue_header + "".join(queue_items) + QUEUE_DIALOG_FOOTER


def _get_or_create_queue_file(log_file):
    """Ensure queue file exists and is accessible.
    
    Args:
        log_file: Path to queue log file
        
    Returns:
        bool: True if file is accessible, False otherwise
    """
    try:
        with io.open(log_file, "r", encoding="utf-8"):
            pass
    except IOError:
        try:
            with io.open(log_file, "w+", encoding="utf-8"):
                pass
        except IOError as e:
            ERROR_HANDLE.print_note("Warning: Cannot access queue file: {}".format(str(e)))
            return False
    return True


def check_sync_queue(doc):
    """Check if document sync should proceed based on queue status.
    
    Manages a sync queue system to prevent multiple users from syncing simultaneously.
    Projects in SYNC_QUEUE_IGNORE_LIST bypass the queue entirely.
    
    Args:
        doc: Revit Document object to check sync status for
        
    Returns:
        bool: True if sync can proceed, False if sync has been cancelled/stopped
    """
    # Validate document
    if not doc:
        ERROR_HANDLE.print_note("Error: check_sync_queue received None document")
        can_proceed_sync = True
        return can_proceed_sync
    
    # Check if project should bypass queue
    if _is_project_ignored(doc.Title, SYNC_QUEUE_IGNORE_LIST):
        can_proceed_sync = True
        return can_proceed_sync
    
    # Get queue file and ensure it exists
    log_file = FOLDER.get_shared_dump_folder_file("SYNC_QUEUE_{}".format(doc.Title))
    if not _get_or_create_queue_file(log_file):
        # Cannot access queue file, allow sync to proceed
        ERROR_HANDLE.print_note("Cannot access sync queue file, allowing sync to proceed")
        can_proceed_sync = True
        return can_proceed_sync
    
    # Load and clean queue
    try:
        queue = DATA_FILE.get_list(log_file)
    except Exception as e:
        ERROR_HANDLE.print_note("Error reading queue file: {}".format(str(e)))
        can_proceed_sync = True
        return can_proceed_sync
    
    wait_num = len(queue)
    queue = _cleanup_old_queue_records(queue)
    
    # Add current user to queue if needed
    time = TIME.get_formatted_current_time()
    user_name = USER.USER_NAME
    queue, was_added = _add_user_to_queue_if_needed(queue, user_name, time)
    
    # Save updated queue if user was added
    if was_added:
        try:
            DATA_FILE.set_list(queue, log_file)
        except Exception as e:
            # Cannot write to queue file (e.g., SH cannot write to L drive)
            ERROR_HANDLE.print_note("Warning: Cannot write to queue file: {}".format(str(e)))
            can_proceed_sync = True
            return can_proceed_sync
    
    # Check if user can proceed with sync
    if wait_num == 0 or user_name in queue[0] or REVIT_EVENT.is_sync_queue_disabled():
        # No one on wait list, or user is first in line, or queue is globally disabled
        can_proceed_sync = True
        return can_proceed_sync
    
    # User must wait - show dialog
    current_queue = _build_queue_dialog_text(queue)
    opts = [
        ["I will join the waitlist and sync later.(Click 'Close' when you see Revit Sync Fail on next step, it just means the sync has been cancelled. You still hold position on the waitlist.)", "Resume working and try syncing later.(+ $50 EA Coins)"],
        ["I don't care! Sync me now!", "Jump in line will make other people who are syncing has to wait longer.(- $100 EA Coins for every position cut line)"]
    ]
    res = REVIT_FORMS.dialogue(
        main_text="There are other people queuing before you, do you want to resume working and try sync later?\n\nYour name has been added to the wait list even if you cancel current sync.\n\n[You are also welcomed to save local while waiting.]",
        sub_text=current_queue,
        options=opts
    )
    
    if res == opts[1][0]:
        # User chose to cut in line
        can_proceed_sync = True
        return can_proceed_sync
    
    # User chose to wait - cancel sync
    EXEC_PARAMS.event_args.Cancel()
    
    # Play duck sound if enabled
    if CONFIG.get_setting("toggle_bt_is_duck_allowed", False):
        DUCK.quack()
    
    # Save local copy
    try:
        doc.Save()
    except Exception as e:
        ERROR_HANDLE.print_note("Warning: Could not save local copy: {}".format(str(e)))
    
    can_proceed_sync = False
    return can_proceed_sync





@ERROR_HANDLE.try_catch_error(is_pass=True)
def fill_drafter_info(doc):
    all_sheets = DB.FilteredElementCollector(doc).OfCategory(DB.BuiltInCategory.OST_Sheets).ToElements()
    free_sheets = REVIT_SELECTION.filter_elements_changable(all_sheets)
    
    t = DB.Transaction(doc, "Fill Drafter Info")
    t.Start()
    is_sparc_project = False
    if doc and doc.Title:
        is_sparc_project = doc.Title.strip().lower() == "sparc_a_ea_cuny_building"
    for sheet in free_sheets:
        tooltip_info = DB.WorksharingUtils.GetWorksharingTooltipInfo(doc, sheet.Id)
        sheet.LookupParameter("Drawn By").Set(tooltip_info.Creator)
        designed_by_value = tooltip_info.LastChangedBy
        if is_sparc_project:
            designed_by_value = "Ennead Architects"
        sheet.LookupParameter("Designed By").Set(designed_by_value)
    t.Commit()


@LOG.log(__file__, __title__)
@ERROR_HANDLE.try_catch_error(is_silent=True)
def doc_syncing(doc):
    VERSION_CONTROL.update_dist_repo()


    can_sync = check_sync_queue(doc)
    if can_sync:
        # LEGACY_LOG.update_account_by_local_warning_diff(doc)
        pass

    if REVIT_EVENT.is_all_sync_closing():
        return

    # do this after checking queue so the primary EXE_PARAM is same as before
    fill_drafter_info(doc)

    TIMESHEET.update_timesheet(doc.Title)


    

#################################################################

if __name__ == "__main__":
    doc_syncing(DOC)