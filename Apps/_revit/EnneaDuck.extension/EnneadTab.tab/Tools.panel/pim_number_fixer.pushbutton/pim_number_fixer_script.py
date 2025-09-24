#!/usr/bin/python
# -*- coding: utf-8 -*-

__doc__ = """
Pim Number Fixer

This tool allows users to batch rename DWG and PDF files by updating or inserting a PIM number into their filenames.
It provides a simple UI to select files, preview the new filenames, and perform the renaming operation.
The tool also remembers the last used PIM number for convenience.

Typical use cases:
- Standardizing file naming conventions for project documentation.
- Quickly updating PIM numbers in multiple files after project changes.

Note: This tool operates on the file system and does not require an open Revit document.
"""
__title__ = "Pim Number\nFixer"
__context__ = "zero-doc"


from Autodesk.Revit.UI import IExternalEventHandler, ExternalEvent # pyright: ignore
from pyrevit import forms
from pyrevit.forms import WPFWindow
import proDUCKtion # pyright: ignore
proDUCKtion.validify()
from EnneadTab import ERROR_HANDLE, LOG, DATA_CONVERSION
from EnneadTab import DATA_FILE
import os
import re
import json
from pathlib import Path

class PimNumberFixerWindow(WPFWindow):
    def __init__(self):
        WPFWindow.__init__(self, 'PimNumberFixer.xaml')

        self.selected_files = []
        self.pim_entry.Text = self.load_pim_preference()
        self.debug_textbox.Text = "Debug Output:"
        self.bt_select_files.Click += self.select_files
        self.bt_clear_files.Click += self.clear_files
        self.bt_preview.Click += self.preview_rename
        self.bt_rename.Click += self.rename_files
        self.bt_close.Click += self.close_Click
        self.MouseLeftButtonDown += self.mouse_down_main_panel
        self.update_file_list()



    @ERROR_HANDLE.try_catch_error()
    def load_pim_preference(self):
        data = DATA_FILE.get_data("pim_number_fixer_pref")
        return data.get("pim_number", "")

    @ERROR_HANDLE.try_catch_error()
    def save_pim_preference(self, pim_number):
        DATA_FILE.set_data({"pim_number": pim_number}, "pim_number_fixer_pref")

    @ERROR_HANDLE.try_catch_error()
    def select_files(self, sender, args):
        files = forms.pick_file('Select DWG/PDF files to rename', files_filter='DWG and PDF Files (*.dwg;*.pdf)|*.dwg;*.pdf|All Files (*.*)|*.*', multi_file=True)
        if files:
            # Use the utility function to safely convert .NET Array to Python list
            self.selected_files = DATA_CONVERSION.safe_convert_net_array_to_list(files)
            self.update_file_list()

    @ERROR_HANDLE.try_catch_error()
    def clear_files(self, sender, args):
        self.selected_files = []
        self.update_file_list()
        self.preview_text.Text = ''

    @ERROR_HANDLE.try_catch_error()
    def update_file_list(self):
        self.file_listbox.Items.Clear()
        for file_path in self.selected_files:
            filename = os.path.basename(file_path)
            self.file_listbox.Items.Add(filename)

    @ERROR_HANDLE.try_catch_error()
    def parse_filename(self, filename):
        name_without_ext = os.path.splitext(filename)[0]
        # Split on "Sheet - " to get the part after it
        if "Sheet - " not in name_without_ext:
            return None

        name_without_ext = name_without_ext.split("Sheet - ", 1)[1]


        # Find the first occurrence of " - " to properly separate sheet number and sheet name
        # This handles sheet numbers like "A-001" that contain dashes
        first_dash_index = name_without_ext.find(" - ")
        if first_dash_index != -1:
            sheet_number = name_without_ext[:first_dash_index].strip()
            sheet_name = name_without_ext[first_dash_index + 3:].strip()  # +3 to skip " - "
            return sheet_number, sheet_name

        return None

    @ERROR_HANDLE.try_catch_error()
    def generate_new_filename(self, original_filename, pim_number):
        parsed = self.parse_filename(original_filename)
        if not parsed:
            return None
        sheet_number, sheet_name = parsed

        extension = os.path.splitext(original_filename)[1]
        new_filename = "{}-{}_{}{}".format(pim_number, sheet_number, sheet_name, extension)
        return new_filename

    @ERROR_HANDLE.try_catch_error()
    def preview_rename(self, sender, args):
        pim_number = self.pim_entry.Text.strip()
        if not pim_number:
            self.debug_textbox.Text = "Please enter a PIM number"
            return
        if not self.selected_files:
            self.debug_textbox.Text = "Please select files first"
            return
        preview_text = "Preview of file renaming:\n\n"
        for file_path in self.selected_files:
            original_filename = os.path.basename(file_path)
            new_filename = self.generate_new_filename(original_filename, pim_number)
            if new_filename:
                preview_text += "Original: {}\n".format(original_filename)
                preview_text += "New:      {}\n".format(new_filename)
                preview_text += "-" * 50 + "\n"
            else:
                preview_text += "SKIP: {} (cannot parse format)\n".format(original_filename)
                preview_text += "-" * 50 + "\n"
        self.preview_text.Text = preview_text

    @ERROR_HANDLE.try_catch_error()
    def rename_files(self, sender, args):
        pim_number = self.pim_entry.Text.strip()
        if not pim_number:
            self.debug_textbox.Text = "Please enter a PIM number"
            return
        if not self.selected_files:
            self.debug_textbox.Text = "Please select files first"
            return
        self.save_pim_preference(pim_number)
        success_count = 0
        error_count = 0
        skipped_count = 0
        for file_path in self.selected_files:
            try:
                original_filename = os.path.basename(file_path)
                new_filename = self.generate_new_filename(original_filename, pim_number)
                if not new_filename:
                    skipped_count += 1
                    continue
                directory = os.path.dirname(file_path)
                new_file_path = os.path.join(directory, new_filename)
                if os.path.exists(new_file_path):
                    result = forms.alert("File '{}' already exists. Overwrite?".format(new_filename), options=["Yes", "No"])
                    if result != "Yes":
                        continue
                os.rename(file_path, new_file_path)
                success_count += 1
            except Exception as e:
                error_count += 1
                ERROR_HANDLE.print_note("Error renaming {}: {}".format(file_path, e))
        message = "Rename completed:\n"
        message += "Success: {}\n".format(success_count)
        message += "Errors: {}\n".format(error_count)
        message += "Skipped: {}".format(skipped_count)
        self.debug_textbox.Text = message
        if success_count > 0:
            self.clear_files(None, None)

    @ERROR_HANDLE.try_catch_error()
    def close_Click(self, sender, args):
        self.Close()

    @ERROR_HANDLE.try_catch_error()
    def mouse_down_main_panel(self, sender, args):
        self.DragMove()


@LOG.log(__file__, __title__)
@ERROR_HANDLE.try_catch_error()
def pim_number_fixer(doc=None):
    # This tool works with zero documents - it's a file system tool, not a Revit tool
    window = PimNumberFixerWindow()
    window.ShowDialog()

################## main code below #####################
if __name__ == "__main__":
    # This tool can run with zero documents - it's a file system utility
    pim_number_fixer()