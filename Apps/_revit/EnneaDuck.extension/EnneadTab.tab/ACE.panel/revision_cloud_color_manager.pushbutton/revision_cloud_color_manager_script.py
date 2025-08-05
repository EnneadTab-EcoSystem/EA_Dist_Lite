#!/usr/bin/python
# -*- coding: utf-8 -*-

__doc__ = "Manage revision cloud colors based on revision ID. Enable/disable color display and set custom colors for each revision across all documents."
__title__ = "Revision Cloud\nColor Manager"
__tip__ = True
__is_popular__ = True

import os
import json
from pyrevit import forms
from pyrevit import script

import proDUCKtion # pyright: ignore 
proDUCKtion.validify()
from EnneadTab.REVIT import REVIT_APPLICATION, REVIT_FORMS
from EnneadTab import ERROR_HANDLE, NOTIFICATION, COLOR, EXE, DATA_FILE, LOG, FOLDER
from Autodesk.Revit import DB # pyright: ignore 
from Autodesk.Revit import UI # pyright: ignore

uidoc = REVIT_APPLICATION.get_uidoc()
doc = REVIT_APPLICATION.get_doc()

# Configuration file name
CONFIG_FILE = "revision_cloud_colors"

# Default color palette - good looking colors for revisions
DEFAULT_COLOR_PALETTE = [
    {"R": 255, "G": 0, "B": 0},      # Red
    {"R": 0, "G": 128, "B": 255},    # Blue
    {"R": 0, "G": 200, "B": 0},      # Green
    {"R": 255, "G": 165, "B": 0},    # Orange
    {"R": 128, "G": 0, "B": 255},    # Purple
    {"R": 255, "G": 0, "B": 255},    # Magenta
    {"R": 0, "G": 255, "B": 255},    # Cyan
    {"R": 255, "G": 255, "B": 0},    # Yellow
    {"R": 128, "G": 128, "B": 128},  # Gray
    {"R": 255, "G": 192, "B": 203},  # Pink
    {"R": 165, "G": 42, "B": 42},    # Brown
    {"R": 0, "G": 128, "B": 128},    # Teal
    {"R": 255, "G": 140, "B": 0},    # Dark Orange
    {"R": 75, "G": 0, "B": 130},     # Indigo
    {"R": 220, "G": 20, "B": 60},    # Crimson
    {"R": 34, "G": 139, "B": 34},    # Forest Green
]

class RevisionCloudColorManager:
    def __init__(self, doc):
        self.doc = doc
        self.config = self.load_config()
        
    def load_config(self):
        """Load configuration from DATA_FILE"""
        default_config = {
            "enabled": False,
            "revision_colors": {},
            "default_color": {"R": 255, "G": 0, "B": 0}  # Default red
        }
        
        try:
            config = DATA_FILE.get_data(CONFIG_FILE)
            if config:
                return config
        except:
            pass
        
        # If no config exists, create one with default colors for existing revisions
        return self.create_default_config()
    
    def create_default_config(self):
        """Create a default configuration with colors assigned to existing revisions"""
        config = {
            "enabled": False,
            "revision_colors": {},
            "default_color": {"R": 255, "G": 0, "B": 0}  # Default red
        }
        
        # Get existing revisions and assign colors from palette
        revisions = self.get_all_revisions()
        for i, revision in enumerate(revisions):
            revision_number = revision.RevisionNumber
            # Use colors from palette, cycling if more revisions than colors
            color_index = i % len(DEFAULT_COLOR_PALETTE)
            config["revision_colors"][revision_number] = DEFAULT_COLOR_PALETTE[color_index]
        
        # Save the default config
        try:
            DATA_FILE.set_data(config, CONFIG_FILE)
        except:
            pass
        
        return config
    
    def save_config(self):
        """Save configuration using DATA_FILE"""
        try:
            DATA_FILE.set_data(self.config, CONFIG_FILE)
        except Exception as e:
            ERROR_HANDLE.print_note("Failed to save configuration: {}".format(e))
    
    def get_all_revisions(self):
        """Get all revisions in the document"""
        return list(DB.FilteredElementCollector(self.doc).OfClass(DB.Revision).WhereElementIsNotElementType().ToElements())
    
    def get_all_revision_clouds(self):
        """Get all revision clouds in the document"""
        return list(DB.FilteredElementCollector(self.doc).OfCategory(DB.BuiltInCategory.OST_RevisionClouds).WhereElementIsNotElementType().ToElements())
    
    def pick_color(self, title="Pick Color"):
        """Use pyrevit color picker to select a color"""
        try:
            # Try to use pyrevit color picker
            color = forms.pick_color(title=title)
            if color:
                return {"R": color.Red, "G": color.Green, "B": color.Blue}
        except:
            pass
        
        # Fallback to Windows color dialog
        try:
            import clr
            clr.AddReference("System.Windows.Forms")
            from System.Windows.Forms import ColorDialog
            
            color_dialog = ColorDialog()
            color_dialog.AllowFullOpen = True
            color_dialog.FullOpen = True
            
            if color_dialog.ShowDialog() == 1:  # DialogResult.OK
                color = color_dialog.Color
                return {"R": color.R, "G": color.G, "B": color.B}
        except:
            pass
        
        # Final fallback - return default red
        return {"R": 255, "G": 0, "B": 0}
    
    def assign_colors_to_new_revisions(self):
        """Assign colors to any revisions that don't have colors yet"""
        revisions = self.get_all_revisions()
        existing_colors = set(self.config["revision_colors"].keys())
        new_revisions = []
        
        for revision in revisions:
            revision_number = revision.RevisionNumber
            if revision_number not in existing_colors:
                new_revisions.append(revision_number)
        
        if not new_revisions:
            return
        
        # Assign colors to new revisions
        for i, revision_number in enumerate(new_revisions):
            # Find next available color from palette
            used_colors = set()
            for color in self.config["revision_colors"].values():
                used_colors.add((color["R"], color["G"], color["B"]))
            
            # Find first unused color from palette
            for color in DEFAULT_COLOR_PALETTE:
                color_tuple = (color["R"], color["G"], color["B"])
                if color_tuple not in used_colors:
                    self.config["revision_colors"][revision_number] = color
                    break
            else:
                # If all palette colors are used, generate a random color
                import random
                self.config["revision_colors"][revision_number] = {
                    "R": random.randint(50, 255),
                    "G": random.randint(50, 255), 
                    "B": random.randint(50, 255)
                }
        
        self.save_config()
        if new_revisions:
            NOTIFICATION.messenger("Assigned colors to {} new revisions.".format(len(new_revisions)))
    
    def apply_colors_to_revision_clouds(self):
        """Apply colors to revision clouds based on configuration using graphic overrides"""
        # Auto-enable if not already enabled
        if not self.config["enabled"]:
            self.config["enabled"] = True
            self.save_config()
            NOTIFICATION.messenger("Color management automatically enabled.")
        
        # First, assign colors to any new revisions
        self.assign_colors_to_new_revisions()
        
        clouds = self.get_all_revision_clouds()
        if not clouds:
            NOTIFICATION.messenger("No revision clouds found in the document.")
            return
        
        # Get all views to apply overrides
        all_views = list(DB.FilteredElementCollector(self.doc).OfClass(DB.View).WhereElementIsNotElementType().ToElements())
        
        # Track clouds colored per revision
        revision_cloud_counts = {}
        total_clouds_colored = 0
        
        t = DB.Transaction(self.doc, "Apply Revision Cloud Colors")
        t.Start()
        
        try:
            for view in all_views:
                # Skip views that don't support graphic overrides
                if not hasattr(view, 'SetElementOverrides'):
                    continue
                
                # Create override settings for each revision
                for cloud in clouds:
                    revision_id = cloud.RevisionId
                    if revision_id:
                        revision = self.doc.GetElement(revision_id)
                        if revision:
                            revision_number = revision.RevisionNumber
                            color_config = self.config["revision_colors"].get(revision_number, self.config["default_color"])
                            
                            # Create Revit color
                            revit_color = DB.Color(color_config["R"], color_config["G"], color_config["B"])
                            
                            # Create override settings
                            override_settings = DB.OverrideGraphicSettings()
                            override_settings.SetProjectionLineColor(revit_color)
                            override_settings.SetProjectionLineWeight(3)  # Make it more visible
                            
                            # Apply override to the cloud in this view
                            view.SetElementOverrides(cloud.Id, override_settings)
                            
                            # Track this cloud for the revision
                            if revision_number not in revision_cloud_counts:
                                revision_cloud_counts[revision_number] = 0
                            revision_cloud_counts[revision_number] += 1
                            total_clouds_colored += 1
            
            t.Commit()
            
            # Create summary message
            summary = "Applied colors to {} revision clouds across {} views.\n\n".format(total_clouds_colored, len(all_views))
            summary += "Summary by Revision:\n"
            
            if revision_cloud_counts:
                for revision_number in sorted(revision_cloud_counts.keys()):
                    count = revision_cloud_counts[revision_number]
                    color_config = self.config["revision_colors"].get(revision_number, self.config["default_color"])
                    color_name = self.get_color_name(color_config)
                    summary += "  Revision {}: {} clouds ({})\n".format(revision_number, count, color_name)
            else:
                summary += "  No clouds were colored.\n"
            
            NOTIFICATION.messenger(summary)
            
        except Exception as e:
            t.RollBack()
            ERROR_HANDLE.print_note("Failed to apply colors: {}".format(e))
    
    def remove_colors_from_revision_clouds(self):
        """Remove custom colors from revision clouds using graphic overrides"""
        clouds = self.get_all_revision_clouds()
        if not clouds:
            NOTIFICATION.messenger("No revision clouds found in the document.")
            return
        
        # Get all views to remove overrides
        all_views = list(DB.FilteredElementCollector(self.doc).OfClass(DB.View).WhereElementIsNotElementType().ToElements())
        
        # Track clouds processed per revision
        revision_cloud_counts = {}
        total_clouds_processed = 0
        
        t = DB.Transaction(self.doc, "Remove Revision Cloud Colors")
        t.Start()
        
        try:
            for view in all_views:
                # Skip views that don't support graphic overrides
                if not hasattr(view, 'SetElementOverrides'):
                    continue
                
                for cloud in clouds:
                    revision_id = cloud.RevisionId
                    if revision_id:
                        revision = self.doc.GetElement(revision_id)
                        if revision:
                            revision_number = revision.RevisionNumber
                            
                            # Create default override settings (black color, normal weight)
                            override_settings = DB.OverrideGraphicSettings()
                            override_settings.SetProjectionLineColor(DB.Color(0, 0, 0))
                            override_settings.SetProjectionLineWeight(1)
                            
                            # Apply default override to the cloud in this view
                            view.SetElementOverrides(cloud.Id, override_settings)
                            
                            # Track this cloud for the revision
                            if revision_number not in revision_cloud_counts:
                                revision_cloud_counts[revision_number] = 0
                            revision_cloud_counts[revision_number] += 1
                            total_clouds_processed += 1
            
            t.Commit()
            
            # Create summary message
            summary = "Removed colors from {} revision clouds across {} views.\n\n".format(total_clouds_processed, len(all_views))
            summary += "Summary by Revision:\n"
            
            if revision_cloud_counts:
                for revision_number in sorted(revision_cloud_counts.keys()):
                    count = revision_cloud_counts[revision_number]
                    summary += "  Revision {}: {} clouds (reset to default)\n".format(revision_number, count)
            else:
                summary += "  No clouds were processed.\n"
            
            NOTIFICATION.messenger(summary)
            
        except Exception as e:
            t.RollBack()
            ERROR_HANDLE.print_note("Failed to remove colors: {}".format(e))
    
    def manage_revision_colors(self):
        """Manage colors for individual revisions"""
        revisions = self.get_all_revisions()
        if not revisions:
            NOTIFICATION.messenger("No revisions found in the document.")
            return
        
        # Create options for revision selection with current colors
        options = []
        for rev in revisions:
            revision_number = rev.RevisionNumber
            current_color = self.config["revision_colors"].get(revision_number, self.config["default_color"])
            color_name = self.get_color_name(current_color)
            
            class RevisionOption(forms.TemplateListItem):
                def __init__(self, item, color_name):
                    super(RevisionOption, self).__init__(item)
                    self.color_name = color_name
                
                @property
                def name(self):
                    return "{} - {} ({})".format(self.item.RevisionNumber, self.item.Description, self.color_name)
            
            options.append(RevisionOption(rev, color_name))
        
        selected_revision = forms.SelectFromList.show(
            options,
            title="Select Revision to Set Color",
            button_name="Select"
        )
        
        if not selected_revision:
            return
        
        revision = selected_revision.item
        revision_number = revision.RevisionNumber
        
        # Show current color or pick new one
        current_color = self.config["revision_colors"].get(revision_number, self.config["default_color"])
        current_color_name = self.get_color_name(current_color)
        
        color_options = [
            "Pick New Color",
            "Use Default Color",
            "Remove Custom Color"
        ]
        
        choice = forms.SelectFromList.show(
            color_options,
            title="Color for Revision {} (Current: {})".format(revision_number, current_color_name),
            button_name="Select"
        )
        
        if choice == "Pick New Color":
            new_color = self.pick_color("Pick Color for Revision {}".format(revision_number))
            self.config["revision_colors"][revision_number] = new_color
            self.save_config()
            color_name = self.get_color_name(new_color)
            NOTIFICATION.messenger("Revision {} color set to {}.".format(revision_number, color_name))
            
        elif choice == "Use Default Color":
            if revision_number in self.config["revision_colors"]:
                del self.config["revision_colors"][revision_number]
                self.save_config()
            NOTIFICATION.messenger("Revision {} now uses default color.".format(revision_number))
            
        elif choice == "Remove Custom Color":
            if revision_number in self.config["revision_colors"]:
                del self.config["revision_colors"][revision_number]
                self.save_config()
            NOTIFICATION.messenger("Custom color removed for revision {}.".format(revision_number))
    
    def set_default_color(self):
        """Set the default color for revisions without custom colors"""
        new_color = self.pick_color("Pick Default Color for Revisions")
        self.config["default_color"] = new_color
        self.save_config()
        NOTIFICATION.messenger("Default color set to RGB({},{},{})".format(
            new_color["R"], new_color["G"], new_color["B"]))
    
    def show_current_config(self):
        """Show current configuration"""
        config_text = "Revision Cloud Color Manager Configuration:\n\n"
        config_text += "Enabled: {}\n".format(self.config["enabled"])
        config_text += "Default Color: RGB({},{},{})\n\n".format(
            self.config["default_color"]["R"],
            self.config["default_color"]["G"], 
            self.config["default_color"]["B"])
        
        if self.config["revision_colors"]:
            config_text += "Custom Colors:\n"
            for rev_num, color in self.config["revision_colors"].items():
                config_text += "  Revision {}: RGB({},{},{})\n".format(
                    rev_num, color["R"], color["G"], color["B"])
        else:
            config_text += "No custom colors set.\n"
        
        forms.alert(config_text, title="Current Configuration")
    
    def run_main_menu(self):
        """Run the main menu interface"""
        while True:
            options = {
                "1. Apply Colors to Revision Clouds": self.apply_colors_to_revision_clouds,
                "2. Reset All Colors from Revision Clouds": self.remove_colors_from_revision_clouds,
                "3. Pick Color Mapping for Revisions": self.manage_revision_colors,
                "4. Advanced Options": self.show_advanced_menu,
                "5. Exit": None
            }
            
            selection = forms.SelectFromList.show(
                sorted(options.keys()),
                title="Revision Cloud Color Manager",
                button_name="Select"
            )
            
            if not selection or "Exit" in selection:
                break
            
            if selection in options and options[selection]:
                options[selection]()
    
    def show_advanced_menu(self):
        """Show advanced options menu"""
        while True:
            options = {
                "1. Enable/Disable Color Management": self.toggle_enabled,
                "2. Set Default Color": self.set_default_color,
                "3. Assign Colors to New Revisions": self.assign_colors_to_new_revisions,
                "4. Show Current Configuration": self.show_current_config,
                "5. Back to Main Menu": None
            }
            
            selection = forms.SelectFromList.show(
                sorted(options.keys()),
                title="Advanced Options",
                button_name="Select"
            )
            
            if not selection or "Back to Main Menu" in selection:
                break
            
            if selection in options and options[selection]:
                options[selection]()
    
    def toggle_enabled(self):
        """Toggle the enabled state of color management"""
        self.config["enabled"] = not self.config["enabled"]
        self.save_config()
        status = "enabled" if self.config["enabled"] else "disabled"
        NOTIFICATION.messenger("Revision cloud color management {}.".format(status))

    def get_color_name(self, color_config):
        """Get a human-readable name for a color"""
        r, g, b = color_config["R"], color_config["G"], color_config["B"]
        
        # Define common color names
        color_names = {
            (255, 0, 0): "Red",
            (0, 128, 255): "Blue", 
            (0, 200, 0): "Green",
            (255, 165, 0): "Orange",
            (128, 0, 255): "Purple",
            (255, 0, 255): "Magenta",
            (0, 255, 255): "Cyan",
            (255, 255, 0): "Yellow",
            (128, 128, 128): "Gray",
            (255, 192, 203): "Pink",
            (165, 42, 42): "Brown",
            (0, 128, 128): "Teal",
            (255, 140, 0): "Dark Orange",
            (75, 0, 130): "Indigo",
            (220, 20, 60): "Crimson",
            (34, 139, 34): "Forest Green"
        }
        
        return color_names.get((r, g, b), "RGB({},{},{})".format(r, g, b))

@LOG.log(__file__, __title__)
@ERROR_HANDLE.try_catch_error()
def revision_cloud_color_manager():
    """Main function to run the revision cloud color manager"""
    manager = RevisionCloudColorManager(doc)
    manager.run_main_menu()

################## main code below #####################
output = script.get_output()
output.close_others()

if __name__ == "__main__":
    revision_cloud_color_manager() 