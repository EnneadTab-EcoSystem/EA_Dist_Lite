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
        """Create a default configuration"""
        config = {
            "revision_colors": {},
            "default_color": {"R": 255, "G": 0, "B": 0}  # Default red
        }
        
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
    

    

    
    def apply_colors_to_revision_clouds(self):
        """Apply colors to revision clouds based on configuration using element graphic overrides"""
        
        clouds = self.get_all_revision_clouds()
        if not clouds:
            NOTIFICATION.messenger("No revision clouds found in the document.")
            return
        
        # Track clouds colored per revision
        revision_cloud_counts = {}
        total_clouds_colored = 0
        debug_info = []
        
        # Apply colors using element graphic overrides
        t = DB.Transaction(self.doc, "Apply Revision Cloud Colors")
        t.Start()
        
        try:
            # Process each cloud individually using its owner view
            for cloud in clouds:
                try:
                    # Get the view that owns this cloud
                    owner_view_id = cloud.OwnerViewId
                    if not owner_view_id or owner_view_id == DB.ElementId.InvalidElementId:
                        debug_info.append("Cloud {} has no valid owner view".format(cloud.Id))
                        continue
                    
                    owner_view = self.doc.GetElement(owner_view_id)
                    if not owner_view:
                        debug_info.append("Could not get owner view for cloud {}".format(cloud.Id))
                        continue
                    
                    # Skip views that don't support element overrides
                    if not hasattr(owner_view, 'SetElementOverrides'):
                        debug_info.append("View {} does not support element overrides".format(owner_view.Name))
                        continue
                    
                    # Get revision for this cloud
                    revision_id = cloud.RevisionId
                    if not revision_id:
                        debug_info.append("Cloud {} has no revision ID".format(cloud.Id))
                        continue
                    
                    revision = self.doc.GetElement(revision_id)
                    if not revision:
                        debug_info.append("Could not get revision for cloud {}".format(cloud.Id))
                        continue
                    
                    revision_number = revision.RevisionNumber
                    
                    # Get color for this revision
                    color_config = self.config["revision_colors"].get(revision_number, self.config["default_color"])
                    revit_color = DB.Color(color_config["R"], color_config["G"], color_config["B"])
                    
                    # Create override settings with comprehensive properties
                    override_settings = DB.OverrideGraphicSettings()
                    override_settings.SetProjectionLineColor(revit_color)
                    override_settings.SetProjectionLineWeight(8)
                    override_settings.SetProjectionLinePatternId(DB.ElementId.InvalidElementId)  # Solid pattern
                    override_settings.SetCutLineColor(revit_color)
                    override_settings.SetCutLineWeight(8)
                    override_settings.SetCutLinePatternId(DB.ElementId.InvalidElementId)
                    
                    # Apply override to this cloud in its owner view
                    owner_view.SetElementOverrides(cloud.Id, override_settings)
                    
                    # Track this revision
                    if revision_number not in revision_cloud_counts:
                        revision_cloud_counts[revision_number] = 0
                    revision_cloud_counts[revision_number] += 1
                    total_clouds_colored += 1
                    
                except Exception as e:
                    debug_info.append("Error applying color to cloud {}: {}".format(cloud.Id, str(e)))
            
            t.Commit()
            
            # Create summary message
            summary = "Applied colors to {} revision clouds.\n\n".format(total_clouds_colored)
            summary += "Summary by Revision:\n"
            
            if revision_cloud_counts:
                for revision_number in sorted(revision_cloud_counts.keys()):
                    count = revision_cloud_counts[revision_number]
                    color_config = self.config["revision_colors"].get(revision_number, self.config["default_color"])
                    color_name = self.get_color_name(color_config)
                    summary += "  Revision {}: {} clouds ({})\n".format(revision_number, count, color_name)
            else:
                summary += "  No clouds were colored.\n"
            
            # Add debug info if there were issues
            if debug_info:
                summary += "\nDebug Information:\n"
                for info in debug_info[:10]:  # Limit to first 10 debug messages
                    summary += "  {}\n".format(info)
                if len(debug_info) > 10:
                    summary += "  ... and {} more debug messages\n".format(len(debug_info) - 10)
            
            NOTIFICATION.messenger(summary)
            
        except Exception as e:
            t.RollBack()
            ERROR_HANDLE.print_note("Failed to apply colors: {}".format(e))
            # Show debug info even on error
            if debug_info:
                debug_summary = "Debug information:\n"
                for info in debug_info[:5]:
                    debug_summary += "  {}\n".format(info)
                NOTIFICATION.messenger(debug_summary)
    
    def remove_colors_from_revision_clouds(self):
        """Remove custom colors from revision clouds and restore system defaults"""
        clouds = self.get_all_revision_clouds()
        if not clouds:
            NOTIFICATION.messenger("No revision clouds found in the document.")
            return
        
        # Track clouds processed per revision
        revision_cloud_counts = {}
        total_clouds_processed = 0
        debug_info = []
        
        t = DB.Transaction(self.doc, "Remove Revision Cloud Colors")
        t.Start()
        
        try:
            # Process each cloud individually using its owner view
            for cloud in clouds:
                try:
                    # Get the view that owns this cloud
                    owner_view_id = cloud.OwnerViewId
                    if not owner_view_id or owner_view_id == DB.ElementId.InvalidElementId:
                        debug_info.append("Cloud {} has no valid owner view".format(cloud.Id))
                        continue
                    
                    owner_view = self.doc.GetElement(owner_view_id)
                    if not owner_view:
                        debug_info.append("Could not get owner view for cloud {}".format(cloud.Id))
                        continue
                    
                    # Skip views that don't support element overrides
                    if not hasattr(owner_view, 'SetElementOverrides'):
                        debug_info.append("View {} does not support element overrides".format(owner_view.Name))
                        continue
                    
                    # Get revision for this cloud
                    revision_id = cloud.RevisionId
                    if not revision_id:
                        debug_info.append("Cloud {} has no revision ID".format(cloud.Id))
                        continue
                    
                    revision = self.doc.GetElement(revision_id)
                    if not revision:
                        debug_info.append("Could not get revision for cloud {}".format(cloud.Id))
                        continue
                    
                    revision_number = revision.RevisionNumber
                    
                    # Create empty override settings to restore system defaults
                    override_settings = DB.OverrideGraphicSettings()
                    
                    # Apply default override to this cloud in its owner view
                    owner_view.SetElementOverrides(cloud.Id, override_settings)
                    
                    # Track this revision
                    if revision_number not in revision_cloud_counts:
                        revision_cloud_counts[revision_number] = 0
                    revision_cloud_counts[revision_number] += 1
                    total_clouds_processed += 1
                    
                except Exception as e:
                    debug_info.append("Error resetting colors for cloud {}: {}".format(cloud.Id, str(e)))
            
            t.Commit()
            
            # Create summary message
            summary = "Removed colors from {} revision clouds.\n\n".format(total_clouds_processed)
            summary += "Summary by Revision:\n"
            
            if revision_cloud_counts:
                for revision_number in sorted(revision_cloud_counts.keys()):
                    count = revision_cloud_counts[revision_number]
                    summary += "  Revision {}: {} clouds (restored to system default)\n".format(revision_number, count)
            else:
                summary += "  No clouds were processed.\n"
            
            # Add debug info if there were issues
            if debug_info:
                summary += "\nDebug Information:\n"
                for info in debug_info[:10]:  # Limit to first 10 debug messages
                    summary += "  {}\n".format(info)
                if len(debug_info) > 10:
                    summary += "  ... and {} more debug messages\n".format(len(debug_info) - 10)
            
            NOTIFICATION.messenger(summary)
            
        except Exception as e:
            t.RollBack()
            ERROR_HANDLE.print_note("Failed to remove colors: {}".format(e))
            # Show debug info even on error
            if debug_info:
                debug_summary = "Debug information:\n"
                for info in debug_info[:5]:
                    debug_summary += "  {}\n".format(info)
                NOTIFICATION.messenger(debug_summary)
    
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
        
        # Handle both TemplateListItem and direct object returns
        if hasattr(selected_revision, 'item'):
            revision = selected_revision.item
        else:
            revision = selected_revision
            
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
    
    def test_color_application(self):
        """Test method to verify color application is working"""
        # First run debug to see current state
        self.debug_revision_clouds()
        
        # Ask user if they want to proceed with test
        proceed = forms.alert(
            "This will apply a bright red color to all revision clouds to test if the system is working.\n\n"
            "Do you want to proceed with the test?",
            title="Test Color Application",
            yes=True,
            no=True
        )
        
        if not proceed:
            return
        
        # Temporarily set all revisions to bright red for testing
        original_colors = self.config["revision_colors"].copy()
        
        revisions = self.get_all_revisions()
        for revision in revisions:
            revision_number = revision.RevisionNumber
            self.config["revision_colors"][revision_number] = {"R": 255, "G": 0, "B": 0}  # Bright red
        
        self.save_config()
        
        # Apply the test colors
        self.apply_colors_to_revision_clouds()
        
        # Restore original colors
        self.config["revision_colors"] = original_colors
        self.save_config()
        
        NOTIFICATION.messenger("Test completed. If you saw bright red revision clouds, the system is working correctly.")
    
    def run_main_menu(self):
        """Run the main menu interface"""
        # Show helpful note about the simplified approach
        REVIT_FORMS.dialogue(
            "Welcome",
            "Revision Cloud Color Manager\n\n"
            "This tool applies colors to existing revision clouds based on their revision numbers.\n\n"
            "IMPORTANT: If you add new revision clouds or modify existing ones, you need to re-run this tool to apply colors to the new/modified clouds.\n\n"
            "The tool will only color clouds that currently exist in the document."
        )
        
        while True:
            options = {
                "1. Apply Colors to Revision Clouds": self.apply_colors_to_revision_clouds,
                "2. Reset All Colors from Revision Clouds": self.remove_colors_from_revision_clouds,
                "3. Pick Color Mapping for Revisions": self.manage_revision_colors,
                "4. Test Color Application": self.test_color_application,
                "5. Advanced Options": self.show_advanced_menu,
                "6. Exit": None
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
    
    def debug_revision_clouds(self):
        """Debug method to help diagnose revision cloud color issues"""
        debug_info = []
        
        # Check revision clouds
        clouds = self.get_all_revision_clouds()
        debug_info.append("Found {} revision clouds in document".format(len(clouds)))
        
        if clouds:
            # Check revisions
            revisions = self.get_all_revisions()
            debug_info.append("Found {} revisions in document".format(len(revisions)))
            
            # Check clouds by revision
            clouds_by_revision = {}
            orphaned_clouds = 0
            for cloud in clouds:
                revision_id = cloud.RevisionId
                if revision_id:
                    revision = self.doc.GetElement(revision_id)
                    if revision:
                        revision_number = revision.RevisionNumber
                        if revision_number not in clouds_by_revision:
                            clouds_by_revision[revision_number] = 0
                        clouds_by_revision[revision_number] += 1
                    else:
                        orphaned_clouds += 1
                else:
                    orphaned_clouds += 1
            
            debug_info.append("Clouds by revision:")
            for rev_num, count in clouds_by_revision.items():
                debug_info.append("  Revision {}: {} clouds".format(rev_num, count))
            
            if orphaned_clouds > 0:
                debug_info.append("  Orphaned clouds (no revision): {}".format(orphaned_clouds))
        
        # Check cloud owner views
        owner_views = set()
        for cloud in clouds:
            owner_view_id = cloud.OwnerViewId
            if owner_view_id and owner_view_id != DB.ElementId.InvalidElementId:
                owner_view = self.doc.GetElement(owner_view_id)
                if owner_view:
                    owner_views.add(owner_view.Name)
        
        debug_info.append("Revision clouds are in {} different views: {}".format(len(owner_views), ", ".join(sorted(owner_views))))
        
        # Check configuration
        debug_info.append("Configuration:")
        debug_info.append("  Default color: RGB({},{},{})".format(
            self.config["default_color"]["R"],
            self.config["default_color"]["G"],
            self.config["default_color"]["B"]))
        debug_info.append("  Custom colors: {}".format(len(self.config["revision_colors"])))
        
        for rev_num, color in self.config["revision_colors"].items():
            debug_info.append("    Revision {}: RGB({},{},{})".format(
                rev_num, color["R"], color["G"], color["B"]))
        
        # Show debug info
        debug_text = "\n".join(debug_info)
        forms.alert(debug_text, title="Revision Cloud Debug Information")
    
    def show_advanced_menu(self):
        """Show advanced options menu"""
        while True:
            options = {
                "1. Set Default Color": self.set_default_color,
                "2. Show Current Configuration": self.show_current_config,
                "3. Debug Revision Clouds": self.debug_revision_clouds,
                "4. Back to Main Menu": None
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