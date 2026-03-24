# -*- coding: utf-8 -*-
import tkinter as tk
from tkinter import ttk
import datetime
from data_manager import DataManager

# Theme Configuration
THEME = {
    "bg": "#FAFAFA",           # Very light gray/white background
    "fg": "#333333",           # Soft black text
    "accent": "#5E5E5E",       # Neutral accent (dark gray)
    "highlight": "#E0E0E0",    # Light gray for borders/separators
    "missing_bg": "#FFF0F0",   # Very subtle red tint for missing items
    "font_main": ("Segoe UI", 9),
    "font_header": ("Segoe UI", 10, "bold"),
    "font_title": ("Segoe UI", 11, "bold"),
}

class TimeSheetApp:
    def __init__(self, root):
        self.root = root
        self.root.title("Time")
        self.root.configure(bg=THEME["bg"])
        self.dm = DataManager()
        
        self.current_week_start = self.get_start_of_current_week()
        self.view_week_start = self.current_week_start
        
        self.grid_widgets = {} # (date_str, time_str) -> Combobox
        self.is_editing = False
        
        self.apply_styles()
        self.setup_ui()
        self.refresh_data()
        self.start_auto_refresh()

    def apply_styles(self):
        style = ttk.Style()
        style.theme_use('clam') # 'clam' usually allows more color customization than 'vista' or 'aqua'

        # Configure generic styles
        style.configure("TFrame", background=THEME["bg"])
        style.configure("TLabel", background=THEME["bg"], foreground=THEME["fg"], font=THEME["font_main"])
        style.configure("TButton", 
                        background=THEME["bg"], 
                        foreground=THEME["fg"], 
                        font=THEME["font_main"], 
                        borderwidth=0, 
                        focuscolor=THEME["bg"])
        
        # Mapping for button hover/pressed states
        style.map("TButton",
                  background=[('active', THEME["highlight"]), ('pressed', THEME["highlight"])],
                  foreground=[('active', THEME["fg"]), ('pressed', THEME["fg"])])

        style.configure("Header.TLabel", font=THEME["font_header"], padding=5)
        style.configure("Title.TLabel", font=THEME["font_title"], padding=5)
        
        style.configure("TCheckbutton", background=THEME["bg"], font=THEME["font_main"])
        style.configure("TScrollbar", troughcolor=THEME["bg"], background=THEME["highlight"], borderwidth=0, arrowsize=0)

        # Combobox style
        style.configure("TCombobox", fieldbackground="#FFFFFF", background=THEME["bg"], selectbackground=THEME["highlight"], selectforeground=THEME["fg"])
        
    def get_start_of_current_week(self):
        today = datetime.date.today()
        # Monday is 0, Sunday is 6
        return today - datetime.timedelta(days=today.weekday())

    def setup_ui(self):
        # Top Frame: Navigation
        nav_frame = ttk.Frame(self.root)
        nav_frame.pack(fill='x', padx=20, pady=15)
        
        # Navigation Buttons (Minimalist text buttons)
        ttk.Button(nav_frame, text="←", width=3, command=self.prev_week).pack(side='left')
        
        self.week_label = ttk.Label(nav_frame, text="", style="Title.TLabel", width=20, anchor='center')
        self.week_label.pack(side='left', padx=10)
        
        ttk.Button(nav_frame, text="→", width=3, command=self.next_week).pack(side='left')
        
        ttk.Button(nav_frame, text="Today", command=self.go_current_week).pack(side='left', padx=15)
        
        # Settings (Subtle checkbox)
        self.auto_show_var = tk.BooleanVar(value=self.dm.get_settings().get("auto_show", True))
        ttk.Checkbutton(nav_frame, text="Auto-open", variable=self.auto_show_var, command=self.save_settings).pack(side='right')

        # Main Grid Frame with Canvas for Scrollbar
        self.main_frame = ttk.Frame(self.root)
        self.main_frame.pack(fill='both', expand=True, padx=20, pady=(0, 20))

        # Canvas styling
        self.canvas = tk.Canvas(self.main_frame, bg=THEME["bg"], highlightthickness=0)
        self.scrollbar = ttk.Scrollbar(self.main_frame, orient="vertical", command=self.canvas.yview)
        
        self.scrollable_frame = ttk.Frame(self.canvas)
        self.scrollable_frame.bind(
            "<Configure>",
            lambda e: self.canvas.configure(
                scrollregion=self.canvas.bbox("all")
            )
        )

        self.canvas_window = self.canvas.create_window((0, 0), window=self.scrollable_frame, anchor="nw")
        self.canvas.configure(yscrollcommand=self.scrollbar.set)

        self.canvas.pack(side="left", fill="both", expand=True)
        self.scrollbar.pack(side="right", fill="y")
        
        # Populate Grid
        self.build_grid()

    def build_grid(self):
        # Clear existing widgets
        for widget in self.scrollable_frame.winfo_children():
            widget.destroy()
        self.grid_widgets = {}

        # Padding settings
        pad_x = 2
        pad_y = 4

        # Time Header (Empty corner)
        ttk.Label(self.scrollable_frame, text="").grid(row=0, column=0, padx=pad_x, pady=pad_y)

        # Day Headers
        days = ["Mon", "Tue", "Wed", "Thu", "Fri"]
        for i, day in enumerate(days):
            date = self.view_week_start + datetime.timedelta(days=i)
            # Minimal date format: Mon 28
            text = f"{day} {date.strftime('%d')}"
            
            # Highlight today column header
            today = datetime.date.today()
            if date == today:
                 ttk.Label(self.scrollable_frame, text=text, style="Header.TLabel", foreground=THEME["accent"]).grid(row=0, column=i+1, padx=pad_x, pady=pad_y)
            else:
                 ttk.Label(self.scrollable_frame, text=text, style="Header.TLabel", foreground="#999999").grid(row=0, column=i+1, padx=pad_x, pady=pad_y)

        # Time Rows
        start_hour = 9
        end_hour = 18 # up to 18:00
        current_time = datetime.datetime.combine(self.view_week_start, datetime.time(start_hour, 0))
        
        row = 1
        while current_time.hour < end_hour:
            time_str = current_time.strftime("%H:%M")
            # Minimal time label, right aligned
            ttk.Label(self.scrollable_frame, text=time_str, foreground="#AAAAAA", anchor='e', width=6).grid(row=row, column=0, padx=(0, 10), pady=pad_y)
            
            for col in range(5): # Mon-Fri
                day_date = self.view_week_start + datetime.timedelta(days=col)
                date_str = day_date.strftime("%Y-%m-%d")
                
                # Check for "missing" status to style background?
                # Tkinter Combobox doesn't support background color change easily per state in standard themes without hacking style maps.
                # Instead, we will keep it simple.
                
                cb = ttk.Combobox(self.scrollable_frame, width=18, font=THEME["font_main"])
                cb.grid(row=row, column=col+1, padx=pad_x, pady=pad_y)
                
                # Bindings
                cb.bind("<<ComboboxSelected>>", lambda e, d=date_str, t=time_str: self.on_entry_change(e, d, t))
                cb.bind("<FocusOut>", lambda e, d=date_str, t=time_str: self.on_entry_change(e, d, t))
                cb.bind("<FocusIn>", self.on_focus_in)
                cb.bind("<Return>", lambda e, d=date_str, t=time_str: self.on_return(e, d, t))
                
                self.grid_widgets[(date_str, time_str)] = cb
            
            current_time += datetime.timedelta(minutes=30)
            row += 1

    def refresh_data(self):
        # Format: "Oct 24 - Oct 28"
        end_week = self.view_week_start + datetime.timedelta(days=4)
        if self.view_week_start.month == end_week.month:
            range_str = f"{self.view_week_start.strftime('%b %d')} - {end_week.strftime('%d')}"
        else:
            range_str = f"{self.view_week_start.strftime('%b %d')} - {end_week.strftime('%b %d')}"
            
        self.week_label.config(text=range_str)
        
        data = self.dm.get_entries_for_week(self.view_week_start)
        recents = self.dm.get_recent_entries()
        
        now = datetime.datetime.now()
        
        for (date_str, time_str), widget in self.grid_widgets.items():
            current_val = data.get(date_str, {}).get(time_str, "")
            
            # Avoid overwriting if user is currently editing THIS widget
            if widget != self.root.focus_get():
                if widget.get() != current_val:
                    widget.set(current_val)
            
            widget['values'] = recents
            
            # Visual indicator for missing past entries (Very Subtle)
            # Only if empty and in the past
            # Note: We can't change background of individual combobox instance easily in ttk
            # But we can try to style it if needed, or just leave it clean. 
            # "Zen" implies we shouldn't scream "ERROR" with red.
            # Maybe just let the emptiness speak for itself.

    def on_entry_change(self, event, date_str, time_str):
        widget = event.widget
        value = widget.get()
        self.dm.save_entry(date_str, time_str, value)
        
    def on_return(self, event, date_str, time_str):
        self.on_entry_change(event, date_str, time_str)
        self.root.focus()

    def on_focus_in(self, event):
        self.is_editing = True

    def prev_week(self):
        self.view_week_start -= datetime.timedelta(weeks=1)
        self.build_grid()
        self.refresh_data()

    def next_week(self):
        self.view_week_start += datetime.timedelta(weeks=1)
        self.build_grid()
        self.refresh_data()

    def go_current_week(self):
        self.view_week_start = self.current_week_start
        self.build_grid()
        self.refresh_data()

    def save_settings(self):
        self.dm.update_setting("auto_show", self.auto_show_var.get())

    def start_auto_refresh(self):
        self.auto_refresh_loop()

    def auto_refresh_loop(self):
        focused = self.root.focus_get()
        is_user_active = isinstance(focused, (ttk.Combobox, tk.Entry))
        
        if not is_user_active:
            self.refresh_data()
            
            if self.auto_show_var.get():
                missing = self.dm.check_missing_slots()
                state = self.root.state()
                
                if missing > 0:
                    if state == 'iconic':
                        self.root.deiconify()
                else:
                    if state == 'normal':
                        self.root.iconify()
        
        self.root.after(60000, self.auto_refresh_loop)
