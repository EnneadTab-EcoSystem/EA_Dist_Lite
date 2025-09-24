"""File and folder management utilities for EnneadTab.

This module provides comprehensive file and folder operations across the EnneadTab
ecosystem, including file copying, backup management, and path manipulation.

Key Features:
- Safe file copying and backup creation
- Path manipulation and formatting
- Folder security and creation
- File extension management
- Local and shared dump folder operations
- Automated backup scheduling

Compatible with Python 2.7 and Python 3.x
"""

import time
import os
import traceback
import shutil
import traceback

# Try to import USER with error handling to avoid circular import warnings
try:
    import USER
except Exception:
    print ("USER import failed in FOLDER.py, {}".format(traceback.format_exc()))
    # Create a minimal USER fallback if import fails
    class USER_FALLBACK:
        USER_NAME = os.environ.get("USERNAME", "unknown")
    USER = USER_FALLBACK()

# Try to import ENVIRONMENT with error handling
try:
    from ENVIRONMENT import DUMP_FOLDER, SHARED_DUMP_FOLDER, PLUGIN_EXTENSION
except Exception:
    print ("ENVIRONMENT import failed in FOLDER.py, {}".format(traceback.format_exc()))
    # Fallback values if ENVIRONMENT import fails
    DUMP_FOLDER = os.path.join(os.environ.get("USERPROFILE", ""), "Documents", "EnneadTab Ecosystem", "Dump")
    SHARED_DUMP_FOLDER = DUMP_FOLDER
    PLUGIN_EXTENSION = ".sexyDuck"

try:
    import COPY
except Exception as e:
    print ("COPY import failed in FOLDER.py: {}".format(traceback.format_exc()))

try:
    import ERROR_HANDLE
except Exception as e:
    print ("ERROR_HANDLE import failed in FOLDER.py: {}".format(traceback.format_exc()))



def get_safe_copy(filepath, include_metadata=False):
    """Create a safe copy of a file in the dump folder.

    Creates a timestamped copy of the file in the EA dump folder to prevent
    file conflicts and data loss.

    Args:
        filepath (str): Path to the source file
        include_metadata (bool, optional): If True, preserves file metadata.
            Defaults to False.

    Returns:
        str: Path to the safe copy
    """
    _, file = os.path.split(filepath)
    safe_copy = get_local_dump_folder_file("save_copy_{}_".format(time.time()) + file)
    COPY.copyfile(filepath, safe_copy, include_metadata)
    return safe_copy

def copy_file(original_path, new_path):
    """Copy file to new location, creating directories if needed.

    Args:
        original_path (str): Source file path
        new_path (str): Destination file path

    Note:
        Creates parent directories if they don't exist.
    """
    target_folder = os.path.dirname(new_path)
    if not os.path.exists(target_folder):
        os.makedirs(target_folder)
    COPY.copyfile(original_path, new_path)


def copy_file_or_folder_to_folder(original_path, target_folder, handle_BW_file = False):
    """Copy file to target folder, preserving filename.

    Args:
        original_path (str): Source file path
        target_folder (str): Destination folder path

    Returns:
        str: Path to the copied file

    Note:
        Creates target folder if it doesn't exist.
    """

    # Build destination path under target folder keeping name structure
    new_path = original_path.replace(os.path.dirname(original_path), target_folder)
    if handle_BW_file:
        new_path = new_path.replace("_BW", "")
    
    try:
        # Ensure destination directory exists
        dest_dir = os.path.dirname(new_path)
        if dest_dir:
            secure_folder(dest_dir)

        if os.path.isfile(original_path):
            # Overwrite target file
            COPY.copyfile(original_path, new_path)
        else:
            # Copy a directory; prefer clean copy, then fall back to merge copy
            if os.path.exists(new_path):
                try:
                    shutil.rmtree(new_path)
                except Exception:
                    pass
            try:
                shutil.copytree(original_path, new_path)
            except Exception as e:
                # If destination exists or cannot be fully removed, perform merge copy
                _merge_copy_dir(original_path, new_path)
    except Exception as e:
        print(traceback.format_exc())

    return new_path


def remove_path(path):
    """Remove a file or folder.
    """
    if not os.path.exists(path):
        return
    if os.path.isfile(path):
        os.remove(path)
    else:
        shutil.rmtree(path)

def _merge_copy_dir(src_dir, dst_dir):
    """Merge-copy directory contents from src into dst, creating folders and
    overwriting files as needed. Compatible with IronPython 2.7.
    """
    try:
        if not os.path.exists(dst_dir):
            secure_folder(dst_dir)
        for root, dirs, files in os.walk(src_dir):
            relative = root.replace(src_dir, "").lstrip("\\/")
            target_root = os.path.join(dst_dir, relative) if relative else dst_dir
            if not os.path.exists(target_root):
                secure_folder(target_root)
            for d in dirs:
                candidate = os.path.join(target_root, d)
                if not os.path.exists(candidate):
                    try:
                        os.makedirs(candidate)
                    except Exception:
                        pass
            for f in files:
                src_file = os.path.join(root, f)
                dst_file = os.path.join(target_root, f)
                try:
                    COPY.copyfile(src_file, dst_file)
                except Exception:
                    # Best effort; skip problematic file
                    pass
    except Exception:
        # Swallow merge errors to keep pipeline moving
        pass

def secure_folder(folder):
    """Create folder if it doesn't exist.

    Args:
        folder (str): Path to folder to create/verify

    Returns:
        str: Path to secured folder
    """
    parent_folder = os.path.dirname(folder)
    if not os.path.exists(parent_folder):
        os.makedirs(parent_folder)
    if not os.path.exists(folder):
        os.makedirs(folder)
    return folder



def get_file_name_from_path(file_path, include_extension=True):
    """Extract filename from full path.

    Args:
        file_path (str): Full path to file
        include_extension (bool, optional): If True, includes file extension.
            Defaults to True.

    Returns:
        str: Extracted filename
    """
    _, tail = os.path.split(file_path)
    if not include_extension:
        tail = tail.split(".")[0]
    return tail


def get_file_extension_from_path(file_path):
    """Extract file extension from path.

    Args:
        file_path (str): Full path to file

    Returns:
        str: File extension including dot (e.g. '.txt')
    """
    return os.path.splitext(file_path)[1]

def secure_legal_file_name(file_name):
    """Ensure file name is legal for all operating systems.
    
    Args:
        file_name (str): Original filename
        
    """
    return file_name.replace("::", "_").replace("/", "-").replace("\\", "-").replace(":", "-").replace("*", "-").replace("?", "-").replace("\\", "-").replace("<", "-").replace(">", "-").replace("|", "-").replace(".", "_")

def _secure_file_name(file_name):
    """Ensure file has proper extension.
    
    If file has no extension, append PLUGIN_EXTENSION.
    If file already has an extension, use it as is.
    
    Args:
        file_name (str): Original filename
        
    Returns:
        str: Filename with proper extension
    """
    current_extension = get_file_extension_from_path(file_name)
    if current_extension:
        return file_name
    
    return file_name + PLUGIN_EXTENSION


def _get_internal_file_from_folder(folder, file_name):
    """this construct the path but DO NOT garatee exist."""
    return os.path.join(folder, _secure_file_name(file_name))
  



def get_local_dump_folder_file(file_name):
    """Get full path for file in EA dump folder.

    Args:
        file_name (str): Name of file,  extension optional

    Returns:
        str: Full path in EA dump folder
    """
    return _get_internal_file_from_folder(DUMP_FOLDER, file_name)

def get_local_dump_folder_folder(folder_name):
    """Get full path for folder in EA dump folder.

    Args:
        folder_name (str): Name of folder

    Returns:    
        str: Full path in EA dump folder
    """
    return os.path.join(DUMP_FOLDER, folder_name)

def get_shared_dump_folder_file(file_name):
    """Get full path for file in shared dump folder.

    Args:
        file_name (str): Name of file including extension

    Returns:
        str: Full path in shared dump folder
    """
    return _get_internal_file_from_folder(SHARED_DUMP_FOLDER, file_name)



def copy_file_to_local_dump_folder(original_path, file_name=None, ignore_warning=False):
    """Copy file to local dump folder.

    Creates a local copy of a file in the dump folder, optionally with
    a new name.

    Args:
        original_path (str): Source file path
        file_name (str, optional): New name for copied file.
            Defaults to original filename.
        ignore_warning (bool, optional): If True, suppresses file-in-use warnings.
            Defaults to False.

    Returns:
        str: Path to copied file

    Raises:
        Exception: If file is in use and ignore_warning is False
    """
    if file_name is None:
        file_name = original_path.rsplit("\\", 1)[1]

    local_path = get_local_dump_folder_file(file_name)
    try:
        COPY.copyfile(original_path, local_path)
    except Exception as e:
        if not ignore_warning:
            if "being used by another process" in str(e):
                print("Please close opened file first.")
            else:
                raise e

    return local_path


def backup_data(data_file_name, backup_folder_title, max_time=60 * 60 * 24 * 7):
    """Create scheduled backups of data files.

    Decorator that creates timestamped backups of data files at specified intervals.
    Backups are stored in a dedicated backup folder within the EA dump folder.

    Args:
        data_file_name (str): Name of file to backup
        backup_folder_title (str): Name for backup folder
        max_time (int, optional): Backup interval in seconds.
            Defaults to 7 days (604800 seconds).

    Returns:
        function: Decorated function that performs backup
    """
    def decorator(func):
        def wrapper(*args, **kwargs):
            out = func(*args, **kwargs)

            # Check if source file exists before proceeding
            source_file = get_local_dump_folder_file(data_file_name)
            if not os.path.exists(source_file):
                return out

            backup_folder = get_local_dump_folder_file("backup_" + backup_folder_title)
            if not os.path.exists(backup_folder):
                os.makedirs(backup_folder)

            # Get today's date once
            today = time.strftime("%Y-%m-%d")
            
            # Check if backup exists for today
            today_backup = os.path.join(backup_folder, "{}_{}".format(today, data_file_name))
            if os.path.exists(today_backup):
                return out

            # Find latest backup date
            latest_backup_date = None
            for filename in os.listdir(backup_folder):
                if not filename.endswith(PLUGIN_EXTENSION):
                    continue
                backup_date_str = filename.split("_")[0]
                try:
                    backup_date = time.strptime(backup_date_str, "%Y-%m-%d")
                    if not latest_backup_date or backup_date > latest_backup_date:
                        latest_backup_date = backup_date
                except Exception:
                    continue

            # Skip if latest backup is within max_time
            if latest_backup_date:
                if (time.mktime(time.strptime(today, "%Y-%m-%d")) - time.mktime(latest_backup_date)) <= max_time:
                    return out

            # Create new backup
            try:
                COPY.copyfile(source_file, today_backup)
            except Exception as e:
                print("Backup failed: %s" % str(e))

            return out

        return wrapper

    return decorator


def cleanup_folder_by_extension(folder, extension, old_file_only=False):
    """Delete files with specified extension from folder.

    Args:
        folder (str): Target folder path
        extension (str): File extension to match (with or without dot)
        old_file_only (bool, optional): If True, only deletes files older than 10 days.
            Defaults to False.

    Returns:
        int: Number of files deleted
    """
    filenames = os.listdir(folder)

    if "." not in extension:
        extension = "." + extension

    count = 0
    for current_file in filenames:
        ext = os.path.splitext(current_file)[1]
        if ext.upper() == extension.upper():
            full_path = os.path.join(folder, current_file)

            if old_file_only:
                if time.time() - os.path.getmtime(full_path) > 60 * 60 * 24 * 10:
                    continue
            try:
                os.remove(full_path)
                count += 1
            except Exception as e:
                print(
                    "Cannot delete file [{}] becasue error: {}".format(current_file, e)
                )
    return count


def secure_filename_in_folder(output_folder, desired_name, extension):
    """Format and secure filename in output folder.

    Ensures proper file naming in output folder, particularly useful for
    Revit exports where filenames may be modified.
    Note that with the new Revit API PDF exporter, this is no longer needed since revit 2022.
    But for image export, this is still needed. Becasue ti always export with e a -Sheet- thing in file name.

    Args:
        output_folder (str): Target folder path
        desired_name (str): Desired filename without extension
        extension (str): File extension including dot (e.g. '.jpg')

    Returns:
        str: Properly formatted filename
    """

    # For previewA and previewB files, don't try to remove them as they might be in use
    if desired_name in ["previewA", "previewB"]:
        # Just proceed with the rename operation, don't try to remove the target
        pass
    else:
        # First, try to remove the target file if it exists
        target_file = os.path.join(output_folder, desired_name + extension)
        try:
            if os.path.exists(target_file):
                os.remove(target_file)
        except Exception as e:
            # If we can't remove the target file, try to use a unique name
            import time
            unique_suffix = str(int(time.time() * 1000))[-6:]  # Last 6 digits of timestamp
            desired_name = "{}_{}".format(desired_name, unique_suffix)

    # print keyword
    keyword = " - Sheet - "

    for file_name in os.listdir(output_folder):
        if desired_name in file_name and extension in file_name.lower():
            new_name = desired_name

            # Check if target file already exists and use unique name if needed
            target_path = os.path.join(output_folder, new_name + extension)
            if os.path.exists(target_path):
                import time
                unique_suffix = str(int(time.time() * 1000))[-6:]  # Last 6 digits of timestamp
                new_name = "{}_{}".format(desired_name, unique_suffix)
                target_path = os.path.join(output_folder, new_name + extension)

            # this prefix allow longer path limit
            old_path = "\\\\?\\{}\\{}".format(output_folder, file_name)
            new_path = "\\\\?\\{}\\{}".format(output_folder, new_name + extension)
            try:
                os.rename(old_path, new_path)
                ERROR_HANDLE.print_note("Successfully renamed to {}".format(new_name + extension))
            except Exception as e:
                try:
                    os.rename(
                        os.path.join(output_folder, file_name),
                        os.path.join(output_folder, new_name + extension),
                    )
                    ERROR_HANDLE.print_note("Successfully renamed to {} (fallback)".format(new_name + extension))
                except Exception as e2:
                    ERROR_HANDLE.print_note("filename clean up failed: skip {} becasue: {}".format(file_name, e2))
                    # Don't try to rename again, just continue
                    continue


def wait_until_file_is_ready(file_path):
    """Wait until a file is ready to use.

    Args:
        file_path (str): Path to the file to check

    Returns:
        bool: True if file is ready, False otherwise
    """
    max_attemp = 100
    
    for _ in range(max_attemp):
        if os.path.exists(file_path):
            try:
                with open(file_path, "rb"):
                    return True
            except:
                time.sleep(0.15)
        else:
            time.sleep(0.15)

    return False


def unit_test():
    print( "input: test.txt, should return test.txt")
    print ("actual return: {}".format(_secure_file_name("test.txt")))
    print ("\n")
    print( "input: test.sexyDuck, should return test.sexyDuck")
    print ("actual return: {}".format(_secure_file_name("test.sexyDuck")))
    print ("\n")
    print( "input: test, should return test.sexyDuck")
    print ("actual return: {}".format(_secure_file_name("test")))
    print ("\n")
    print( "PLUGIN_EXTENSION: {}".format(PLUGIN_EXTENSION))



if __name__ == "__main__":
    unit_test()