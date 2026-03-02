import os
import json
import datetime
from contextlib import contextmanager

class DataManager:
    DATA_FILE_NAME = "timesheet_miniapp_data.json"

    def __init__(self):
        # Determine user documents path
        try:
            # Try standard Documents location
            docs_dir = os.path.join(os.path.expanduser("~"), "Documents")
            if not os.path.exists(docs_dir):
                # Fallback to home directory if Documents doesn't exist
                docs_dir = os.path.expanduser("~")
            
            # Create a dedicated subfolder
            self.app_dir = os.path.join(docs_dir, "EnneadTab_TimeSheet")
            if not os.path.exists(self.app_dir):
                os.makedirs(self.app_dir)
                
            self.data_path = os.path.join(self.app_dir, self.DATA_FILE_NAME)
            
        except Exception as e:
            # Fallback to local script folder if permission denied or other error
            print(f"Warning: Could not use Documents folder ({e}). Using application folder instead.")
            self.data_path = os.path.join(os.path.dirname(os.path.abspath(__file__)), self.DATA_FILE_NAME)

        self.ensure_data_file()

    def ensure_data_file(self):
        if not os.path.exists(self.data_path):
            initial_data = {
                "settings": {"auto_show": True},
                "entries": {},
                "recent_entries": []
            }
            self._save_json(initial_data)

    def _read_json(self):
        if not os.path.exists(self.data_path):
            return {}
        try:
            with open(self.data_path, 'r', encoding='utf-8') as f:
                return json.load(f)
        except Exception as e:
            # print(f"Error reading data: {e}")
            return {}

    def _save_json(self, data):
        try:
            with open(self.data_path, 'w', encoding='utf-8') as f:
                json.dump(data, f, indent=4)
        except Exception as e:
            # print(f"Error saving data: {e}")
            pass

    @contextmanager
    def update_data_context(self):
        data = self._read_json()
        try:
            yield data
        finally:
            self._save_json(data)

    def get_data(self):
        return self._read_json()

    def save_entry(self, date_str, time_str, content):
        with self.update_data_context() as data:
            if "entries" not in data:
                data["entries"] = {}
            if date_str not in data["entries"]:
                data["entries"][date_str] = {}
            
            if content and content.strip():
                data["entries"][date_str][time_str] = content.strip()
                
                # Update recent entries
                recents = data.get("recent_entries", [])
                if content in recents:
                    recents.remove(content)
                recents.insert(0, content)
                data["recent_entries"] = recents[:20] # Keep top 20
            else:
                # If content is empty, remove the entry
                if time_str in data["entries"][date_str]:
                    del data["entries"][date_str][time_str]

    def get_entries_for_week(self, start_date):
        # start_date is Monday of the week (datetime.date)
        data = self.get_data()
        entries = data.get("entries", {})
        week_data = {}
        for i in range(5): # Mon-Fri
            current_date = start_date + datetime.timedelta(days=i)
            date_str = current_date.strftime("%Y-%m-%d")
            week_data[date_str] = entries.get(date_str, {})
        return week_data

    def get_recent_entries(self):
        data = self.get_data()
        return data.get("recent_entries", [])

    def get_settings(self):
        data = self.get_data()
        return data.get("settings", {"auto_show": True})

    def update_setting(self, key, value):
        with self.update_data_context() as data:
            if "settings" not in data:
                data["settings"] = {}
            data["settings"][key] = value

    def check_missing_slots(self):
        # Check slots up to current time for the current week
        now = datetime.datetime.now()
        current_date = now.date()
        
        # Start of current week (Monday)
        start_of_week = current_date - datetime.timedelta(days=current_date.weekday())
        
        missing_count = 0
        
        data = self.get_data()
        entries = data.get("entries", {})

        # Iterate days from Monday to Today (inclusive)
        for i in range(5): # Mon-Fri
            day_date = start_of_week + datetime.timedelta(days=i)
            
            # If we are looking at future days, skip
            if day_date > current_date:
                break
            
            date_str = day_date.strftime("%Y-%m-%d")
            day_entries = entries.get(date_str, {})
            
            # Time slots 9am to 6pm, 0.5 interval
            start_hour = 9
            end_hour = 18
            
            current_slot_time = datetime.datetime.combine(day_date, datetime.time(start_hour, 0))
            
            while current_slot_time.hour < end_hour:
                slot_str = current_slot_time.strftime("%H:%M")
                
                # If this slot is in future (relative to now), stop checking
                if current_slot_time > now:
                    break
                    
                if slot_str not in day_entries or not day_entries[slot_str].strip():
                    missing_count += 1
                
                current_slot_time += datetime.timedelta(minutes=30)
                
        return missing_count
