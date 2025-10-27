#!/usr/bin/python
# -*- coding: utf-8 -*-

__doc__ = "Convert area/room boundaries into loadable Revit mass families by using boundary segment curve loops to build mass extrusions in mass family, then load into project using internal coordinates like Block2Family."
__title__ = "Area2Mass"

import proDUCKtion # pyright: ignore 
proDUCKtion.validify()

import os
import math
import traceback
import clr # pyright: ignore 
from pyrevit import forms # pyright: ignore 
from pyrevit.revit import ErrorSwallower # pyright: ignore 
from pyrevit import script # pyright: ignore
import datetime

from EnneadTab import ERROR_HANDLE, FOLDER, DATA_FILE, NOTIFICATION, LOG, ENVIRONMENT, UI, SAMPLE_FILE
from EnneadTab.REVIT import REVIT_APPLICATION, REVIT_FAMILY, REVIT_UNIT, REVIT_SELECTION, REVIT_FORMS
from EnneadTab import ENVIRONMENT
from Autodesk.Revit import DB # pyright: ignore 
from Autodesk.Revit import ApplicationServices # pyright: ignore 

# Import modular classes
try:
    from data_extractors import ElementInfoExtractor, BoundaryDataExtractor
    from template_finder import TemplateFinder
    from mass_family_creator import MassFamilyCreator
    from family_loader import FamilyLoader
    from instance_placer import FamilyInstancePlacer
except ImportError as e:
    print("Error importing modules: {}".format(str(e)))
    print("Please ensure all required modules are available in the same directory.")
    # Show error message if modules can't be imported
    print("Failed to import required modules. Check console for details.")

UIDOC = REVIT_APPLICATION.get_uidoc()
DOC = REVIT_APPLICATION.get_doc()


# =============================================================================
# MAIN CONVERTER CLASS
# =============================================================================

class Area2MassConverter:
    """Main class for converting areas/rooms to mass families."""
    
    def __init__(self):
        """Initialize the Area2Mass converter."""
        self.doc = DOC
        self.uidoc = UIDOC
        self.areas = []
        self.rooms = []
        self.success_count = 0
        self.total_count = 0
        self.template_path = None
        self.created_families = []
        self.selected_scheme = None
        self.element_mode = None  # "Areas" or "Rooms"
        
    def _sanitize_name_component(self, text):
        """Sanitize a component for use in a Revit family name."""
        if text is None:
            return "NA"
        # Ensure string
        value = str(text)
        # Replace invalid chars per Revit naming rules
        invalid_chars = ['<', '>', ':', '"', '/', '\\', '|', '?', '*']
        for ch in invalid_chars:
            value = value.replace(ch, '_')
        value = value.strip()
        if not value:
            return "NA"
        return value

    def run(self):
        """Main execution method with step-by-step process."""
        try:
            # Step 1: Validate environment
            if not self._step_01_validate_environment():
                return False

            # Housekeeping: purge stale AreaMass_/RoomMass_ families older than 7 days
            self._purge_stale_masses(days=7)
                
            # Step 2: Get and filter selection
            if not self._step_02_get_and_filter_selection():
                return False
            
            # Step 2b: Select color scheme for material assignment in project
            if not self._step_02b_select_color_scheme():
                return False
                
            # Step 3: Get template
            if not self._step_03_get_template():
                return False

            # Apply project material colors according to selected color scheme (preparation)
            self._apply_project_material_colors_from_scheme()

            # Step 4: Process spatial elements (each family loads in its own transaction)
            if not self._step_04_process_spatial_elements():
                return False
                
            # Step 5: Show results
            self._step_05_show_results()
            return True
            
        except Exception as e:
            NOTIFICATION.messenger("Error in Area2Mass conversion: {}".format(str(e)))
            print("Error in Area2Mass conversion: {}".format(str(e)))
            return False
    
    @ERROR_HANDLE.try_catch_error()
    def _step_01_validate_environment(self):
        """Step 1: Validate that we're in the right environment."""
        if not self.doc:
            NOTIFICATION.messenger("No active document found.")
            return False
            
        if self.doc.IsFamilyDocument:
            NOTIFICATION.messenger("This tool only works in project documents, not family documents.")
            return False
            
        return True
    
    @ERROR_HANDLE.try_catch_error()
    def _step_02_get_and_filter_selection(self):
        """Step 2: Get selected elements and filter for areas/rooms."""
        # Use REVIT_FORMS.dialogue to get user input
        # Ask user what type of spatial elements they want to process
        options = ["Areas", "Rooms"]
        user_choice = REVIT_FORMS.dialogue(
            title="Area2Mass - Select Element Type",
            main_text="What type of spatial elements would you like to convert to mass families?",
            options=options
        )
        
        if not user_choice or user_choice == "Close" or user_choice == "Cancel":
            NOTIFICATION.messenger("Operation cancelled by user.")
            return False
        
        # Process based on user choice
        if user_choice == "Areas":
            if not self._process_areas():
                return False
        elif user_choice == "Rooms":
            if not self._process_rooms():
                return False
        
        # Check if we have any elements to process
        if not self.areas and not self.rooms:
            NOTIFICATION.messenger("No areas or rooms found to process.")
            return False
        
        self.total_count = len(self.areas) + len(self.rooms)
        NOTIFICATION.messenger("Found {} areas and {} rooms to convert.".format(len(self.areas), len(self.rooms)))
        return True
    
    @ERROR_HANDLE.try_catch_error()
    def _process_areas(self):
        """Process areas with area scheme selection."""
        
        # Get all area schemes in the project
        area_schemes = DB.FilteredElementCollector(self.doc).OfClass(DB.AreaScheme).ToElements()
        
        if not area_schemes:
            NOTIFICATION.messenger("No area schemes found in project.")
            return False
        
        # Let user select which area scheme to process using pyRevit SelectFromList
        # This handles longer lists better than the old dialogue (which was limited to ~4 items)
        scheme_options = []
        for scheme in area_schemes:
            scheme_name = scheme.Name if scheme.Name else "Unnamed Scheme"
            scheme_options.append(scheme_name)
        
        selected_scheme_name = forms.SelectFromList.show(
            scheme_options,
            multiselect=False,
            title="Area2Mass - Select Area Scheme",
            button_name="Select Area Scheme"
        )
        
        if not selected_scheme_name:
            return False
        
        # Find the selected scheme by matching the name
        selected_scheme = None
        for scheme in area_schemes:
            scheme_name = scheme.Name if scheme.Name else "Unnamed Scheme"
            if scheme_name == selected_scheme_name:
                selected_scheme = scheme
                break
        
        if not selected_scheme:
            return False
        
        # Get all areas from the selected scheme using SpatialElement
        spatial_elements = DB.FilteredElementCollector(self.doc).OfClass(DB.SpatialElement).ToElements()
        scheme_areas = []
        
        for element in spatial_elements:
            # Check if it's an Area and belongs to the selected scheme
            if hasattr(element, 'AreaScheme') and element.AreaScheme.Id == selected_scheme.Id:
                scheme_areas.append(element)
        
        if not scheme_areas:
            NOTIFICATION.messenger("No areas found in the selected area scheme.")
            return False
        
        # Process all areas automatically
        self.areas = scheme_areas
        self.element_mode = "Areas"
        
        return True
    
    @ERROR_HANDLE.try_catch_error()
    def _process_rooms(self):
        """Process all rooms in the project."""
        
        # Get all rooms in the project using SpatialElement
        spatial_elements = DB.FilteredElementCollector(self.doc).OfClass(DB.SpatialElement).ToElements()
        rooms = []
        
        for element in spatial_elements:
            # Check if it's a Room
            if hasattr(element, 'Number'):  # Rooms have Number parameter
                rooms.append(element)
        
        if not rooms:
            NOTIFICATION.messenger("No rooms found in project.")
            return False
        
        # Process all rooms automatically
        self.rooms = rooms
        self.element_mode = "Rooms"
        
        return True

    @ERROR_HANDLE.try_catch_error()
    def _step_02b_select_color_scheme(self):
        """Prompt user to select a Color Fill Scheme for Areas or Rooms and store it."""
        # Determine category by mode
        if self.element_mode == "Areas":
            target_cat_id = DB.Category.GetCategory(self.doc, DB.BuiltInCategory.OST_Areas).Id
        elif self.element_mode == "Rooms":
            target_cat_id = DB.Category.GetCategory(self.doc, DB.BuiltInCategory.OST_Rooms).Id
        else:
            return False

        # Collect schemes for the target category
        schemes = list(DB.FilteredElementCollector(self.doc).OfClass(DB.ColorFillScheme))
        schemes = [s for s in schemes if hasattr(s, 'CategoryId') and s.CategoryId == target_cat_id]
        if not schemes:
            return True  # optional; no scheme selection available

        # Build options from scheme names
        opts = []
        name_map = {}
        for s in schemes:
            try:
                nm = s.Name
            except:
                # Use Value property for Revit 2024+, fallback to IntegerValue for older versions
                try:
                    nm = str(s.Id.Value)
                except AttributeError:
                    nm = str(s.Id.IntegerValue)
            opts.append(nm)
            name_map[nm] = s

        choice = forms.SelectFromList.show(
            opts,
            multiselect=False,
            title="Area2Mass - Select Color Scheme",
            button_name="Select Color Scheme"
        )
        if not choice:
            return True  # treat as optional; proceed without scheme

        self.selected_scheme = name_map.get(choice)
        return True

    def _apply_project_material_colors_from_scheme(self):
        """Apply material colors in project by matching scheme entry names to material names.
        Expects materials to be named 'AreaMass_{Department}' or 'RoomMass_{Department}'."""
        try:
            if not self.selected_scheme:
                return
            prefix = "AreaMass_" if self.element_mode == "Areas" else "RoomMass_"

            # Attempt to get entries from scheme
            get_entries = getattr(self.selected_scheme, 'GetEntries', None)
            if not get_entries:
                return
            entries = list(self.selected_scheme.GetEntries())
            if not entries:
                return

            # Build material settings dict {material_name: settings}
            mat_settings = {}
            for entry in entries:
                try:
                    # Try to get the display name for matching (often Department value)
                    entry_name = None
                    if hasattr(entry, 'GetName'):
                        entry_name = entry.GetName()
                    elif hasattr(entry, 'Name'):
                        entry_name = entry.Name
                    if not entry_name:
                        continue

                    # Get color
                    col = None
                    if hasattr(entry, 'Color') and entry.Color:
                        col = entry.Color
                    elif hasattr(entry, 'GetColor'):
                        col = entry.GetColor()
                    if not col:
                        continue

                    r, g, b = col.Red, col.Green, col.Blue
                    mat_name = prefix + str(entry_name)
                    mat_settings[mat_name] = {
                        "Color": (r, g, b),
                        "Transparency": 30,
                        "SurfaceForegroundPatternIsSolid": True,
                        "SurfaceForegroundPatternColor": (r, g, b)
                    }
                except Exception:
                    continue

            if not mat_settings:
                return

            # Apply to project document using REVIT_MATERIAL.update_material_setting
            from EnneadTab.REVIT import REVIT_MATERIAL
            try:
                REVIT_MATERIAL.update_material_setting(self.doc, mat_settings)
            except Exception:
                pass
        except Exception:
            pass
    
    @ERROR_HANDLE.try_catch_error()
    def _step_03_get_template(self):
        """Step 3: Get mass family template."""
        template_finder = TemplateFinder()
        self.template_path = template_finder.get_mass_family_template()
        
        if not self.template_path:
            NOTIFICATION.messenger("Failed to get mass family template.")
            return False
        
        return True
    
    @ERROR_HANDLE.try_catch_error()
    def _step_04_process_spatial_elements(self):
        """Step 4: Process each spatial element to create mass families."""
        # Process areas
        for i, area in enumerate(self.areas):
            NOTIFICATION.messenger("Processing area {} of {}".format(i+1, len(self.areas)))
            if not self._process_single_element(area, "Area"):
                continue
        
        # Process rooms
        for i, room in enumerate(self.rooms):
            NOTIFICATION.messenger("Processing room {} of {}".format(i+1, len(self.rooms)))
            if not self._process_single_element(room, "Room"):
                continue
        
        if not self.created_families:
            NOTIFICATION.messenger("No mass families were created successfully.")
            return False
        return True
    
    def _process_single_element(self, element, element_type):
        """Process a single spatial element to create a mass family."""
        # Extract boundary data
        extractor = BoundaryDataExtractor(element)
        if not extractor.is_valid():
            print("Failed to extract boundary data for {}: {}".format(element_type, element.Id))
            return False
        
        # Get element info for naming
        info_extractor = ElementInfoExtractor(element, element_type)
        element_info = info_extractor._extract_info()
        
        if not element_info or not element_info.get('name'):
            return False

        # Determine extrusion height from next level above current level
        extrusion_height = 10.0
        try:
            current_level_info = element_info.get('level') if element_info else None
            if current_level_info and 'elevation' in current_level_info:
                current_elev = current_level_info['elevation']
                # Collect and sort all levels by elevation
                levels = DB.FilteredElementCollector(self.doc).OfClass(DB.Level).ToElements()
                sorted_levels = sorted([lvl for lvl in levels if hasattr(lvl, 'Elevation')], key=lambda l: l.Elevation)
                # Find first level above current elevation
                next_level = None
                for lvl in sorted_levels:
                    if lvl.Elevation > current_elev:
                        next_level = lvl
                        break
                if next_level is not None:
                    extrusion_height = next_level.Elevation - current_elev
                else:
                    # Keep default extrusion height
                    pass
        except Exception as _:
            # Keep default if anything unexpected
            pass

        # Build family name per spec
        level_name = self._sanitize_name_component((element_info.get('level') or {}).get('name') if element_info else None)
        department = self._sanitize_name_component(element_info.get('department') if element_info else None)
        # Use Value property for Revit 2024+, fallback to IntegerValue for older versions
        try:
            element_id_str = str(element.Id.Value)
        except AttributeError:
            element_id_str = str(element.Id.IntegerValue)
        if element_type == "Area":
            scheme_name = self._sanitize_name_component(getattr(element.AreaScheme, 'Name', None))
            family_name_with_id = "AreaMass_{}_{}_{}_{}".format(scheme_name, level_name, department, element_id_str)
        else:
            family_name_with_id = "RoomMass_{}_{}_{}".format(level_name, department, element_id_str)

        # Create mass family
        mass_creator = MassFamilyCreator(
            self.template_path,
            family_name_with_id,
            extrusion_height,
            element_type=element_type,
            department=element_info.get('department') if element_info else None
        )
        
        family_doc = mass_creator.create_from_boundaries(extractor.segments)
        
        if not family_doc:
            return False
        
        # Load family into project in its own transaction (commits immediately)
        family_loader = FamilyLoader(family_doc, family_name_with_id)
        load_result = family_loader.load_into_project(self.doc)
        if not load_result:
            return False
        
        # Get the updated family name (which may have changed during SaveAs)
        actual_family_name = family_loader.family_name
        
        # Place instance in a separate transaction (can rollback without affecting loaded family)
        try:
            placer = FamilyInstancePlacer(self.doc, actual_family_name, element)
            placement_result = placer.place_instance()
            
            if not placement_result:
                # Note: Family is already loaded and committed, so we don't return False here
                # Instead, we mark it as loaded but placement failed
                self.created_families.append({
                    'element_id': element.Id,
                    'element_type': element_type,
                    'family_name': actual_family_name,
                    'success': True,
                    'placement_failed': True
                })
                return True  # Return True since family was loaded successfully
        except Exception as e:
            # Mark as failed but continue
            self.created_families.append({
                'element_id': element.Id,
                'element_type': element_type,
                'family_name': actual_family_name,
                'success': True,
                'placement_failed': True
            })
            return True
        
        # Store created family info for successful placement
        self.created_families.append({
            'element_id': element.Id,
            'element_type': element_type,
            'family_name': actual_family_name,
            'success': True
        })
        
        return True
    
    @ERROR_HANDLE.try_catch_error()
    def _step_05_show_results(self):
        """Step 5: Show final results and cleanup."""
        # Only report failures
        failed = [fi for fi in self.created_families if fi.get('placement_failed')]
        if failed:
            output = script.get_output()
            output.print_md("## Placement Failures")
            for family_info in failed:
                output.print_md("**{} {}** → Mass Family '{}' (LOADED but placement FAILED)".format(
                    family_info['element_type'],
                    family_info['element_id'],
                    family_info['family_name']
                ))
        return True


    def _purge_stale_masses(self, days=7):
        """Delete instances and unload families with prefix AreaMass_/RoomMass_ older than N days.
        Timestamp is read from instance 'Mark' parameter if present."""
        try:
            cutoff = datetime.datetime.now() - datetime.timedelta(days=days)
            fam_prefixes = ("AreaMass_", "RoomMass_")

            # Collect instances by family name prefix
            inst_collector = DB.FilteredElementCollector(self.doc).OfClass(DB.FamilyInstance)
            to_delete_inst_ids = []
            touched_family_ids = set()
            for inst in inst_collector:
                try:
                    sym = inst.Symbol
                    fam = sym.Family if sym else None
                    if not fam or not fam.Name:
                        continue
                    if not (fam.Name.startswith(fam_prefixes[0]) or fam.Name.startswith(fam_prefixes[1])):
                        continue

                    # Parse timestamp from Mark parameter
                    ts_ok = False
                    mark = None
                    try:
                        p = inst.LookupParameter("Mark")
                        mark = p.AsString() if p else None
                    except Exception:
                        mark = None
                    if mark:
                        try:
                            ts = datetime.datetime.strptime(mark, "%Y-%m-%d %H:%M:%S")
                            ts_ok = ts < cutoff
                        except Exception:
                            ts_ok = True  # unknown format -> purge to be safe
                    else:
                        ts_ok = True  # no timestamp -> consider stale and purge

                    if ts_ok:
                        to_delete_inst_ids.append(inst.Id)
                        touched_family_ids.add(fam.Id)
                except Exception:
                    continue

            # Delete old instances
            if to_delete_inst_ids:
                t = DB.Transaction(self.doc, "Area2Mass - Purge old instances")
                t.Start()
                try:
                    self.doc.Delete(DB.List[DB.ElementId](to_delete_inst_ids))
                    t.Commit()
                except Exception:
                    t.RollBack()

            # Optionally remove families with no remaining instances
            try:
                fams_to_remove = []
                for fam_id in touched_family_ids:
                    fam = self.doc.GetElement(fam_id)
                    if not fam:
                        continue
                    has_instances = False
                    for sym_id in fam.GetFamilySymbolIds():
                        if DB.FilteredElementCollector(self.doc).OfClass(DB.FamilyInstance).WhereElementIsNotElementType().ToElements():
                            # cheap check: look for any instance using this symbol id
                            for inst in DB.FilteredElementCollector(self.doc).OfClass(DB.FamilyInstance):
                                if inst.Symbol and inst.Symbol.Id == sym_id:
                                    has_instances = True
                                    break
                        if has_instances:
                            break
                    if not has_instances:
                        fams_to_remove.append(fam.Id)

                if fams_to_remove:
                    t2 = DB.Transaction(self.doc, "Area2Mass - Remove unused families")
                    t2.Start()
                    try:
                        self.doc.Delete(DB.List[DB.ElementId](fams_to_remove))
                        t2.Commit()
                    except Exception:
                        t2.RollBack()
            except Exception:
                pass
        except Exception:
            pass


# =============================================================================
# MAIN EXECUTION
# =============================================================================

@LOG.log(__file__, __title__)
@ERROR_HANDLE.try_catch_error()
def area2mass():
    """Main function to convert areas/rooms to mass families."""
    converter = Area2MassConverter()
    return converter.run()


################## main code below #####################
if __name__ == "__main__":
    output = script.get_output()
    output.close_others(True)
    area2mass()
