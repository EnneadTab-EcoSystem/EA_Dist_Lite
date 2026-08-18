import os
import shutil
import tkinter as tk
from tkinter import messagebox, ttk
import sys
import traceback
from _Exe_Util import DB_FOLDER, ECO_SYS_FOLDER, DUMP_FOLDER
from pathlib import Path
import time
import logging
from datetime import datetime

# Set up logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler(os.path.join(DUMP_FOLDER, 'ShanghaiRepoAssists.log')),
        logging.StreamHandler()
    ]
)

def log_action(message):
    """Log an action with timestamp"""
    timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    logging.info(f"[{timestamp}] {message}")
    return timestamp

def format_duration(seconds):
    """Format duration as MM:SS if under 1 hour, else HH:MM:SS"""
    hours = int(seconds // 3600)
    minutes = int((seconds % 3600) // 60)
    seconds = int(seconds % 60)
    if hours > 0:
        return f"{hours:02d}:{minutes:02d}:{seconds:02d}"
    else:
        return f"{minutes:02d}:{seconds:02d}"

def copy_file(source, dest, progress_callback, max_retries=3):
    """Copy a single file with progress tracking and retry mechanism"""
    for attempt in range(max_retries):
        try:
            log_action(f"Copying file: {source} -> {dest}")
            shutil.copy2(source, dest)
            progress_callback(1, source)
            return True
        except Exception as e:
            if attempt < max_retries - 1:
                log_action(f"Retry {attempt + 1}/{max_retries} for {source}: {str(e)}")
                time.sleep(1)  # Wait before retry
            else:
                log_action(f"Failed to copy {source} after {max_retries} attempts: {str(e)}")
                progress_callback(1, source, error=str(e))
                return False

def copy_directory(source, dest, progress_callback, max_retries=3):
    """Copy a directory with progress tracking and retry mechanism"""
    for attempt in range(max_retries):
        try:
            log_action(f"Copying directory: {source} -> {dest}")
            shutil.copytree(source, dest, dirs_exist_ok=True)
            file_count = sum(1 for _ in Path(source).rglob('*') if _.is_file())
            progress_callback(file_count, source)
            return True
        except Exception as e:
            if attempt < max_retries - 1:
                log_action(f"Retry {attempt + 1}/{max_retries} for directory {source}: {str(e)}")
                time.sleep(1)  # Wait before retry
            else:
                log_action(f"Failed to copy directory {source} after {max_retries} attempts: {str(e)}")
                progress_callback(1, source, error=str(e))
                return False

def copy_backup_repo():
    start_time = time.time()
    log_action("Starting backup repo operation")
    
    try:
        # Create the main window
        window = tk.Tk()
        window.title("Backup Repo Operation")
        window.geometry("800x400")
        
        # Create and pack the label
        label = tk.Label(window, text="Looking for Backup repo folder to copy into your user Ecosystem folder\nin case you have trouble accessing github.com")
        label.pack(pady=10)
        
        # Create and pack the progress bar
        progress = ttk.Progressbar(window, length=700, mode='determinate')
        progress.pack(pady=10)
        
        # Create and pack the status label
        status_label = tk.Label(window, text="Preparing to copy...", wraplength=700)
        status_label.pack(pady=5)
        
        # Create timestamp label
        timestamp_label = tk.Label(window, text="")
        timestamp_label.pack(pady=5)
        
        # Create current file label
        current_file_label = tk.Label(window, text="", wraplength=700)
        current_file_label.pack(pady=5)
        
        def update_progress(count, current_file, error=None):
            """Update progress bar and status"""
            progress['value'] += count
            current_time = datetime.now().strftime("%H:%M:%S")
            elapsed_time = time.time() - start_time
            status_text = f"Copying... {int(progress['value'])}/{total_items} items"
            timestamp_text = f"Current time: {current_time} | Elapsed: {format_duration(elapsed_time)}"
            
            if error:
                current_file_text = f"Error copying: {current_file}\nError: {error}"
            else:
                current_file_text = f"Currently copying: {current_file}"
            
            status_label.config(text=status_text)
            timestamp_label.config(text=timestamp_text)
            current_file_label.config(text=current_file_text)
            window.update()
        
        # Define source and destination paths
        source_dir = os.path.join(DB_FOLDER, "BackupRepo")
        destination_dir = os.path.join(ECO_SYS_FOLDER, "EA_Dist")
        
        log_action(f"Source directory: {source_dir}")
        log_action(f"Destination directory: {destination_dir}")
        
        # Check if source exists
        if not os.path.exists(source_dir):
            error_msg = f"BackupRepo folder not found at: {source_dir}\n\nPlease make sure you have access to the network drive (L:) and try again."
            log_action(f"Error: {error_msg}")
            messagebox.showerror("Error", error_msg)
            window.destroy()
            return
        
        # Create destination directory if it doesn't exist
        if not os.path.exists(destination_dir):
            log_action(f"Creating destination directory: {destination_dir}")
            try:
                os.makedirs(destination_dir)
            except Exception as e:
                error_msg = f"Failed to create destination directory: {destination_dir}\nError: {str(e)}"
                log_action(f"Error: {error_msg}")
                messagebox.showerror("Error", error_msg)
                window.destroy()
                return
        
        # Count total items to copy
        try:
            total_items = sum(1 for _ in Path(source_dir).rglob('*') if _.is_file())
            log_action(f"Total items to copy: {total_items}")
            progress['maximum'] = total_items
        except Exception as e:
            error_msg = f"Failed to count files in source directory: {str(e)}\n\nPlease make sure you have access to the network drive (L:)."
            log_action(f"Error: {error_msg}")
            messagebox.showerror("Error", error_msg)
            window.destroy()
            return
        
        # Sequential copying
        for item in os.listdir(source_dir):
            source_item = os.path.join(source_dir, item)
            dest_item = os.path.join(destination_dir, item)
            
            if os.path.isdir(source_item):
                copy_directory(source_item, dest_item, update_progress)
            else:
                copy_file(source_item, dest_item, update_progress)
        
        end_time = time.time()
        duration = end_time - start_time
        log_action(f"Backup completed in {format_duration(duration)}")
        
        # Show success message
        messagebox.showinfo(
            "Success",
            f"BackupRepo contents have been successfully copied to: {destination_dir}\nDuration: {format_duration(duration)}"
        )
        
    except Exception as e:
        error_msg = f"An error occurred:\n{str(e)}\n\nTraceback:\n{traceback.format_exc()}"
        log_action(f"Error: {error_msg}")
        messagebox.showerror("Error", error_msg)
    
    finally:
        try:
            window.destroy()
        except:
            pass

if __name__ == "__main__":
    try:
        log_action("Starting application")
        copy_backup_repo()
    except Exception as e:
        log_action(f"Fatal error: {str(e)}")
        log_action(traceback.format_exc())
        input("Press Enter to exit...")
