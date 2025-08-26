#!/usr/bin/python
# -*- coding: utf-8 -*-

__doc__ = """Export Revit Rooms/Areas to Rhino as color-coded diagrams with XAML GUI.

This tool creates a simplified diagram representation of Rooms or Areas in Rhino:
- Exports boundaries with filleted corners and optional inner offset
- Maintains color coding from Revit color schemes
- Adds text labels for space identifiers
- Creates solid hatches for each space
- Features XAML GUI with persistent settings
- Supports both Rooms and Areas export
- Configurable corner fillet radius and inner offset distance
- Automatic settings save/restore for future use
- Framework ready for drafting view group export (future feature)
"""
__title__ = "RoomOrArea2Diagram"

import traceback
import os
import System # pyright: ignore 

from Autodesk.Revit.UI import IExternalEventHandler, ExternalEvent # pyright: ignore 
from Autodesk.Revit.Exceptions import InvalidOperationException # pyright: ignore 
from pyrevit.forms import WPFWindow
from pyrevit.forms import SelectFromList
from pyrevit import forms
from pyrevit import script 

try:
    import clr  # pyright: ignore
    clr.AddReference('RhinoCommon')
    import Rhino  # pyright: ignore
    clr.AddReference('RhinoInside.Revit')
    from RhinoInside.Revit.Convert.Geometry import GeometryDecoder as RIR_DECODER  # pyright: ignore
    RHINO_INSIDE_IMPORT_OK = True
except:
    RHINO_INSIDE_IMPORT_OK = False

import proDUCKtion # pyright: ignore 
proDUCKtion.validify()

from EnneadTab.REVIT import REVIT_FORMS, REVIT_APPLICATION
from EnneadTab import DATA_FILE, IMAGE, ERROR_HANDLE, LOG, NOTIFICATION
from Autodesk.Revit import DB # pyright: ignore 

uidoc = REVIT_APPLICATION.get_uidoc()
doc = REVIT_APPLICATION.get_doc()
__persistentengine__ = True

output = script.get_output()

# Import shared constants
from shared_constants import ElementType, ExportMethod

# Import the separated process classes
from rhino_process import RhinoProcess
from revit_process import RevitProcess


class InputValidator:
    """Input validation class for protecting processing from invalid inputs."""
    
    # Validation constants
    MIN_FILLET_RADIUS = 0.0
    MAX_FILLET_RADIUS = 100.0  # 100 feet max
    MIN_OFFSET_DISTANCE = 0.0
    MAX_OFFSET_DISTANCE = 50.0  # 50 feet max
    
    @classmethod
    def validate_fillet_radius(cls, value):
        """Validate fillet radius input."""
        try:
            radius = float(value)
            if radius < cls.MIN_FILLET_RADIUS:
                return False, "Fillet radius must be >= {} feet".format(cls.MIN_FILLET_RADIUS)
            if radius > cls.MAX_FILLET_RADIUS:
                return False, "Fillet radius must be <= {} feet".format(cls.MAX_FILLET_RADIUS)
            return True, ""
        except (ValueError, TypeError):
            return False, "Fillet radius must be a valid number"
    
    @classmethod
    def validate_offset_distance(cls, value):
        """Validate offset distance input."""
        try:
            offset = float(value)
            if offset < cls.MIN_OFFSET_DISTANCE:
                return False, "Offset distance must be >= {} feet".format(cls.MIN_OFFSET_DISTANCE)
            if offset > cls.MAX_OFFSET_DISTANCE:
                return False, "Offset distance must be <= {} feet".format(cls.MAX_OFFSET_DISTANCE)
            return True, ""
        except (ValueError, TypeError):
            return False, "Offset distance must be a valid number"
    
    @classmethod
    def validate_all_inputs(cls, fillet_radius, offset_distance):
        """Validate all inputs at once."""
        is_valid, error_msg = cls.validate_fillet_radius(fillet_radius)
        if not is_valid:
            return False, error_msg
        
        is_valid, error_msg = cls.validate_offset_distance(offset_distance)
        if not is_valid:
            return False, error_msg
        
        return True, ""


class ProcessingConfig:
    """Configuration class to hold all processing settings."""
    
    def __init__(self, element_type, export_method, fillet_radius, offset_distance, selected_views=None):
        self.element_type = element_type
        self.export_method = export_method
        self.fillet_radius = fillet_radius
        self.offset_distance = offset_distance
        self.selected_views = selected_views or []


class Shape2Diagram:
    """Main orchestrator class for Room/Area diagram export."""
    
    def __init__(self, revit_doc, config):
        """Initialize exporter with Revit document and configuration."""
        self.revit_doc = revit_doc
        self.config = config
        
        # Initialize appropriate processor
        if self.config.export_method == ExportMethod.RHINO:
            self.processor = RhinoProcess(revit_doc, config.fillet_radius, config.offset_distance)
        else:
            self.processor = RevitProcess(revit_doc, config.fillet_radius, config.offset_distance)
        
    @ERROR_HANDLE.try_catch_error()
    def export_as_diagram(self, level_name=None, source_view=None):
        """Main export function with optional level name and source view parameters."""
        try:
            # Use source view if provided, otherwise use active view
            view_to_process = source_view if source_view else self.revit_doc.ActiveView
            
            # Use BaseProcessor methods for validation and processing
            results = self.processor.process_view_with_elements(
                self.config.element_type, 
                view_to_process, 
                level_name
            )
            
            if results:
                # Delegate to appropriate processor with processed results
                try:
                    self.processor.process_spaces_from_results(results)
                except Exception as e:
                    print("ERROR: Failed to process spaces: {}. Stopping export.".format(str(e)))
                    return
            else:
                print("No results from view processing - skipping export")
                
        except Exception as e:
            print("CRITICAL ERROR in export_as_diagram: {}. Stopping export.".format(str(e)))
            return


# Create a subclass of IExternalEventHandler
class room2diagram_SimpleEventHandler(IExternalEventHandler):
    """
    Simple IExternalEventHandler sample
    """

    # __init__ is used to make function from outside of the class to be executed by the handler. \
    # Instructions could be simply written under Execute method only
    def __init__(self, do_this):
        self.do_this = do_this
        self.kwargs = None
        self.OUT = None

    # Execute method run in Revit API environment.
    def Execute(self, uiapp):
        try:
            try:
                self.OUT = self.do_this(*self.kwargs)
            except:
                print("failed")
                print(traceback.format_exc())
        except InvalidOperationException:
            # If you don't catch this exeption Revit may crash.
            print("InvalidOperationException catched")

    def GetName(self):
        return "simple function executed by an IExternalEventHandler in a Form"


# Global recursion protection
_processing_depth = 0
_MAX_PROCESSING_DEPTH = 5

@ERROR_HANDLE.try_catch_error()
def process_diagram_export(config):
    """Main processing function called by ExternalEventHandler with integrated multiple view processing."""
    global _processing_depth
    
    # RECURSION PROTECTION
    _processing_depth += 1
    if _processing_depth > _MAX_PROCESSING_DEPTH:
        print("ERROR: Maximum processing depth exceeded. Possible recursion detected. Stopping to prevent stack overflow.")
        _processing_depth -= 1
        return
    
    # Class-level error collection for review
    collected_errors = []
    
    try:
        print("Starting Room/Area diagram export...")
        
        # Validate that we have a document
        if not doc:
            error_msg = "No active document available"
            collected_errors.append(error_msg)
            NOTIFICATION.messenger(error_msg)
            return
        
        # Always require views to be selected - no fallback to current view
        if not config.selected_views:
            error_msg = "No views selected. Please use 'Pick Views' button to select views for processing."
            collected_errors.append(error_msg)
            NOTIFICATION.messenger(error_msg)
            return
        
        print("Processing {} views... (depth: {})".format(len(config.selected_views), _processing_depth))
        
        # Filter views by unique levels to avoid duplicate processing
        processed_levels = set()
        unique_level_views = []
        valid_views = []
        
        # First, filter out invalid views
        for view in config.selected_views:
            try:
                if not view:
                    print("Skipping invalid view (null reference)")
                    continue
                
                # SAFEGUARD: Check if view is still valid
                if not view.IsValidObject:
                    print("Skipping invalid view (no longer valid)")
                    continue
                
                if not is_view_suitable_for_processing(view):
                    print("Skipping unsuitable view: {} (type: {})".format(view.Name, view.ViewType))
                    continue
                
                valid_views.append(view)
            except Exception as e:
                error_msg = "Error validating view: {}. Skipping.".format(str(e))
                collected_errors.append(error_msg)
                print(error_msg)
                continue
        
        if not valid_views:
            error_msg = "No valid views found for processing. Please select floor plans, area plans, or similar views."
            collected_errors.append(error_msg)
            print(error_msg)
            REVIT_FORMS.notification(
                main_text="No Valid Views Found",
                sub_text="Please select floor plans or area plans for processing.\nCurrent views are not suitable for room/area diagram export.",
                window_title="EnneadTab - Warning",
                button_name="OK",
                self_destruct=5
            )
            return
        
        print("Found {} valid views for processing...".format(len(valid_views)))
        
        # Now process valid views by unique levels and area schemes
        for view in valid_views:
            try:
                level_name = "Unknown_Level"
                area_scheme_name = "Default"
                
                if view and view.GenLevel:
                    level_name = view.GenLevel.Name
                
                # For area plans, also check the area scheme to avoid conflicts
                if view.ViewType == DB.ViewType.AreaPlan:
                    try:
                        # Use the proper AreaScheme property from ViewPlan
                        if hasattr(view, 'AreaScheme') and view.AreaScheme:
                            area_scheme_name = view.AreaScheme.Name
                        else:
                            area_scheme_name = "Default"
                    except:
                        area_scheme_name = "Default"
                
                # Create a unique identifier combining level and area scheme (only for area plans)
                if view.ViewType == DB.ViewType.AreaPlan:
                    unique_identifier = "{}_AreaScheme_{}".format(level_name, area_scheme_name)
                else:
                    # For floor plans and other view types, just use level name
                    unique_identifier = level_name
                
                if unique_identifier not in processed_levels:
                    processed_levels.add(unique_identifier)
                    unique_level_views.append((view, level_name))
                    if view.ViewType == DB.ViewType.AreaPlan:
                        print("Found unique level/scheme: {} (Level: {}, Area Scheme: {})".format(unique_identifier, level_name, area_scheme_name))
                    else:
                        print("Found unique level: {} (Level: {})".format(unique_identifier, level_name))
            except Exception as e:
                error_msg = "Error processing view {}: {}. Skipping.".format(view.Name if view else "Unknown", str(e))
                collected_errors.append(error_msg)
                print(error_msg)
                continue
        
        print("Processing {} unique levels (filtered from {} views)...".format(len(unique_level_views), len(config.selected_views)))
        
        # Process each unique level with error handling
        for i, (view, level_name) in enumerate(unique_level_views):
            try:
                print("Processing level {}/{}: {} (view: {})".format(i+1, len(unique_level_views), level_name, view.Name))
                
                # SAFEGUARD: Check if view is still valid before processing
                if not view or not view.IsValidObject:
                    error_msg = "View no longer valid, skipping: {}".format(view.Name if view else "Unknown")
                    collected_errors.append(error_msg)
                    print(error_msg)
                    continue
                
                # Process the view with level name using BaseProcessor
                # Create a temporary processor to use its process_single_view method
                if config.export_method == ExportMethod.RHINO:
                    temp_processor = RhinoProcess(doc, config.fillet_radius, config.offset_distance)
                else:
                    temp_processor = RevitProcess(doc, config.fillet_radius, config.offset_distance)
                
                temp_processor.process_single_view(config, view, level_name)
                
                # SAFEGUARD: Force garbage collection after each view
                import gc
                gc.collect()
                
            except Exception as e:
                error_msg = "Error processing level {}: {}. Continuing with next level...".format(level_name, str(e))
                collected_errors.append(error_msg)
                print(error_msg)
                print(traceback.format_exc())
                continue
        
        # Show completion notification with more detailed information
        processed_count = len(unique_level_views)
        total_selected = len(config.selected_views)
        
        # Display collected errors if any
        if collected_errors:
            print("\n" + "="*50)
            print("ERROR SUMMARY - {} errors collected:".format(len(collected_errors)))
            print("="*50)
            for i, error in enumerate(collected_errors, 1):
                print("{}. {}".format(i, error))
            print("="*50)
            print("Full error details have been logged above.")
            print("="*50 + "\n")
        
        if processed_count == total_selected:
            REVIT_FORMS.notification(
                main_text="Batch Processing Complete",
                sub_text="Successfully processed {} views".format(processed_count),
                window_title="EnneadTab",
                button_name="Close",
                self_destruct=10
            )
        else:
            REVIT_FORMS.notification(
                main_text="Batch Processing Complete",
                sub_text="Processed {} of {} selected views\nSome views were skipped due to duplicates or invalid types.".format(processed_count, total_selected),
                window_title="EnneadTab",
                button_name="Close",
                self_destruct=10
            )
        
    except Exception as e:
        error_msg = "CRITICAL ERROR in process_diagram_export: {}. Stopping processing.".format(str(e))
        collected_errors.append(error_msg)
        print(error_msg)
        print(traceback.format_exc())
    finally:
        # Always decrement processing depth
        _processing_depth -= 1

@ERROR_HANDLE.try_catch_error()
def is_view_suitable_for_processing(view):
    """Check if a view is suitable for room/area diagram processing."""
    if not view:
        return False
    
    # Check view type - we want views that can show rooms/areas
    suitable_view_types = [
        DB.ViewType.FloorPlan,
        DB.ViewType.AreaPlan
    ]
    
    return view.ViewType in suitable_view_types







# A simple WPF form used to call the ExternalEvent
class room2diagram_ModelessForm(WPFWindow):
    """
    Simple modeless form sample
    """

    def pre_actions(self):
        self.process_event_handler = room2diagram_SimpleEventHandler(process_diagram_export)
        self.ext_event_process = ExternalEvent.Create(self.process_event_handler)
        return

    @ERROR_HANDLE.try_catch_error()
    def __init__(self):
        self.pre_actions()

        xaml_file_name = "room2diagram_UI.xaml"
        WPFWindow.__init__(self, xaml_file_name)

        self.title_text.Text = "Room/Area to Diagram Exporter"
        self.sub_text.Text = "Configure export settings and pick views for processing. Processing will happen in background."

        self.Title = self.title_text.Text

        logo_file = IMAGE.get_image_path_by_name("logo_vertical_light.png")
        self.set_image_source(self.logo_img, logo_file)

        self.selected_views = []

        self.load_setting()
        self.update_ui_state()

        self.Show()

    @ERROR_HANDLE.try_catch_error()
    def load_setting(self):
        """Load settings from file."""
        data = DATA_FILE.get_data("room2diagram_settings")
        if not data:
            data = {}

        # Set element type - compare with string values
        element_type = data.get("element_type", "Rooms")
        if element_type == "Rooms":
            self.radio_bt_rooms.IsChecked = True
            self.radio_bt_areas.IsChecked = False
        else:
            self.radio_bt_rooms.IsChecked = False
            self.radio_bt_areas.IsChecked = True
        
        # Set export method - compare with string values
        export_method = data.get("export_method", "Rhino")

        if export_method == "Rhino":
            self.radio_bt_rhino.IsChecked = True
            self.radio_bt_drafting.IsChecked = False
        else:
            self.radio_bt_rhino.IsChecked = False
            self.radio_bt_drafting.IsChecked = True
        
        # Set geometry settings with validation
        fillet_radius = data.get("fillet_radius", "12")
        offset_distance = data.get("offset_distance", "2")
        
        # Validate saved settings and use defaults if invalid
        is_valid, _ = InputValidator.validate_all_inputs(fillet_radius, offset_distance)
        if not is_valid:
            print("Invalid saved settings detected. Using default values.")
            fillet_radius = "12"
            offset_distance = "2"
        
        self.textbox_fillet_radius.Text = str(fillet_radius)
        self.textbox_offset_distance.Text = str(offset_distance)

    @ERROR_HANDLE.try_catch_error()
    def save_setting(self):
        """Save current settings to file."""
        # Create a clean data dictionary with only string values
        clean_data = {}
        
        # Save element type as string values
        if self.radio_bt_rooms.IsChecked:
            clean_data["element_type"] = "Rooms"
        else:
            clean_data["element_type"] = "Areas"
        
        # Save export method as string values
        if self.radio_bt_rhino.IsChecked:
            clean_data["export_method"] = "Rhino"
        else:
            clean_data["export_method"] = "Revit"
        
        # Save geometry settings with validation
        fillet_radius_text = self.textbox_fillet_radius.Text
        offset_distance_text = self.textbox_offset_distance.Text
        
        # Only save if values are valid
        is_valid, _ = InputValidator.validate_all_inputs(fillet_radius_text, offset_distance_text)
        if is_valid:
            clean_data["fillet_radius"] = fillet_radius_text
            clean_data["offset_distance"] = offset_distance_text
        else:
            print("Invalid values detected. Settings not saved.")
            return
        
        # Save the clean data
        DATA_FILE.set_data(clean_data, "room2diagram_settings")

    def update_ui_state(self):
        """Update UI state based on current selections."""
        if self.radio_bt_drafting.IsChecked:
            self.debug_textbox.Text = "Ready to export - Please pick views first"
        else:
            self.debug_textbox.Text = "Ready to export to Rhino..."
        # Always enable export button - validation will happen on click
        self.bt_export.IsEnabled = True

    @ERROR_HANDLE.try_catch_error()
    def element_type_changed(self, sender, e):
        """Handle element type radio button changes."""
        self.update_ui_state()

    @ERROR_HANDLE.try_catch_error()
    def export_method_changed(self, sender, e):
        """Handle export method radio button changes."""
        self.update_ui_state()

    @ERROR_HANDLE.try_catch_error()
    def fillet_radius_changed(self, sender, e):
        """Handle fillet radius text changes."""
        pass

    @ERROR_HANDLE.try_catch_error()
    def offset_distance_changed(self, sender, e):
        """Handle offset distance text changes."""
        pass

    @ERROR_HANDLE.try_catch_error()
    def pick_views_click(self, sender, e):
        """Handle pick views button click."""
        self.pick_views()

    @ERROR_HANDLE.try_catch_error()
    def pick_views(self):
        """
        Pick views for processing - Simple and robust approach.
        
        This method:
        1. Collects all views from the document
        2. Filters for eligible views (Floor Plans and Area Plans with levels)
        3. Creates user-friendly display names
        4. Shows selection dialog to user
        5. Maps selected names back to view objects
        """
        try:
            # ============================================================================
            # STEP 1: VALIDATE DOCUMENT
            # ============================================================================
            if not doc or not doc.IsValidObject:
                self.debug_textbox.Text = "ERROR: Document is no longer valid"
                return
            
            # ============================================================================
            # STEP 2: COLLECT ALL VIEWS
            # ============================================================================
            all_views = DB.FilteredElementCollector(doc).OfClass(DB.View).ToElements()
            
            # ============================================================================
            # STEP 3: FILTER AND CREATE DISPLAY MAPPING
            # ============================================================================
            view_dict = {}  # Dictionary: display_name -> view_object
            
            for view in all_views:
                try:
                    # Validate view object
                    if not self._is_view_valid(view):
                        continue
                    
                    # Check if view type is suitable for room/area processing
                    if not self._is_view_type_suitable(view):
                        continue
                    
                    # Create user-friendly display name
                    display_name = self._create_display_name(view)
                    
                    # Store mapping
                    view_dict[display_name] = view
                    
                except Exception as e:
                    # Skip problematic views silently
                    continue
            
            # ============================================================================
            # STEP 4: CHECK IF ANY ELIGIBLE VIEWS FOUND
            # ============================================================================
            if not view_dict:
                self.selected_views = []
                self.debug_textbox.Text = "No eligible views found - Please ensure you have floor plans or area plans with levels"
                return
            
            # ============================================================================
            # STEP 5: SHOW SELECTION DIALOG
            # ============================================================================
            display_names = sorted(list(view_dict.keys()))  # Sort for better UX
            selected_names = SelectFromList.show(
                display_names,
                title="Select Views for Room/Area Diagram Export",
                button_name="Select Views",
                multiselect=True
            )
            
            # ============================================================================
            # STEP 6: PROCESS USER SELECTION
            # ============================================================================
            if selected_names:
                selected_views, view_details = self._process_user_selection(selected_names, view_dict)
                
                self.selected_views = selected_views
                self._update_debug_text(selected_views, view_details)
            else:
                self.selected_views = []
                self.debug_textbox.Text = "No views selected - Please pick views to continue"
                
        except Exception as e:
            self.debug_textbox.Text = "ERROR in pick_views: {}. Please try again.".format(str(e))
            self.selected_views = []
    
    def _is_view_valid(self, view):
        """Check if a view object is valid and can be processed."""
        return (view and 
                view.IsValidObject and 
                not view.IsTemplate and 
                view.GenLevel is not None)
    
    def _is_view_type_suitable(self, view):
        """Check if view type is suitable for room/area diagram processing."""
        suitable_types = [DB.ViewType.FloorPlan, DB.ViewType.AreaPlan]
        return view.ViewType in suitable_types
    
    def _create_display_name(self, view):
        """
        Create user-friendly display name for view selection.
        
        Format: [ViewType][AreaScheme if available][LevelName] View Name
        
        Args:
            view: Revit view object
            
        Returns:
            str: Formatted display name
        """
        # Extract basic information
        level_name = view.GenLevel.Name if view.GenLevel else "Unknown"
        view_name = view.Name if view.Name else "Unknown"
        view_type = view.ViewType.ToString()
        
        if view.ViewType == DB.ViewType.AreaPlan:
            # For area plans, include area scheme information
            area_scheme = self._get_area_scheme_name(view)
            return "[{}][{}][{}] {}".format(view_type, area_scheme, level_name, view_name)
        else:
            # For floor plans, no area scheme needed
            return "[{}][{}] {}".format(view_type, level_name, view_name)
    
    def _get_area_scheme_name(self, view):
        """Safely extract area scheme name from view."""
        try:
            if hasattr(view, 'AreaScheme') and view.AreaScheme:
                return view.AreaScheme.Name
        except:
            pass
        return "Default"
    
    def _process_user_selection(self, selected_names, view_dict):
        """
        Process user's view selection and map back to view objects.
        
        Args:
            selected_names: List of display names selected by user
            view_dict: Dictionary mapping display names to view objects
            
        Returns:
            tuple: (selected_views, view_details)
        """
        selected_views = []
        view_details = []
        
        for selected_name in selected_names:
            try:
                # Get view object from dictionary
                view = view_dict.get(selected_name)
                if view and view.IsValidObject:
                    selected_views.append(view)
                    view_details.append("• {}".format(selected_name))
            except:
                continue
        
        return selected_views, view_details
    
    def _update_debug_text(self, selected_views, view_details):
        """Update debug textbox with selection summary."""
        if len(view_details) <= 5:
            # Show all views if 5 or fewer
            display_text = "Selected {} views:\n{}".format(
                len(selected_views), 
                "\n".join(view_details)
            )
        else:
            # Show first 3 and summary if more than 5
            display_text = "Selected {} views:\n{}\n... and {} more views".format(
                len(selected_views), 
                "\n".join(view_details[:3]), 
                len(selected_views) - 3
            )
        
        self.debug_textbox.Text = display_text

    @ERROR_HANDLE.try_catch_error()
    def export_click(self, sender, e):
        """Handle export button click - start processing via external event."""
        # Validate inputs before processing
        is_valid, error_message = InputValidator.validate_all_inputs(
            self.textbox_fillet_radius.Text,
            self.textbox_offset_distance.Text
        )
        
        if not is_valid:
            print("Input Validation Error: {}".format(error_message))
            return
        
        # Convert to float after validation
        fillet_radius = float(self.textbox_fillet_radius.Text)
        offset_distance = float(self.textbox_offset_distance.Text)
        
        # Save settings
        self.save_setting()
        
        # Get current settings - convert UI state to class constants
        element_type = ElementType.ROOMS if self.radio_bt_rooms.IsChecked else ElementType.AREAS
        export_method = ExportMethod.RHINO if self.radio_bt_rhino.IsChecked else ExportMethod.REVIT
        

        
        # Always require views to be selected
        selected_views = getattr(self, 'selected_views', [])
        if not selected_views:
            REVIT_FORMS.notification(
                main_text="No Views Selected",
                sub_text="Please use 'Pick Views' button to select views for processing.",
                window_title="EnneadTab",
                button_name="Close",
                self_destruct=5
            )
            return
        
        # Create configuration object
        config = ProcessingConfig(
            element_type=element_type,
            export_method=export_method,
            fillet_radius=fillet_radius,
            offset_distance=offset_distance,
            selected_views=getattr(self, 'selected_views', [])
        )
        
        # Start processing via external event
        self.process_event_handler.kwargs = config,  # pyright: ignore
        self.ext_event_process.Raise()
        
        # Update UI
        self.debug_textbox.Text = "Processing started in background..."
        print("Room/Area diagram export started...")

    @ERROR_HANDLE.try_catch_error()
    def close_Click(self, sender, e):
        """Handle close button click."""
        self.save_setting()
        self.Close()

    @ERROR_HANDLE.try_catch_error()
    def mouse_down_main_panel(self, sender, e):
        """Handle mouse down for window dragging."""
        self.DragMove()


@LOG.log(__file__, __title__)
@ERROR_HANDLE.try_catch_error()
def room2diagram(doc):
    """Main entry point for the Room/Area diagram export tool."""
    
    # Check if Rhino Inside is available - if not, block execution completely
    if not RHINO_INSIDE_IMPORT_OK:
        print("Rhino Inside Required.\nPlease initiate Rhino Inside first for this tool to work.")

        return
    
    # Show the GUI for settings and view selection
    room2diagram_ModelessForm()


################## main code below #####################
output = script.get_output()
output.close_others()

if __name__ == "__main__":
    room2diagram(doc)







