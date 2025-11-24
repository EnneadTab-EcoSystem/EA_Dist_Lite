#!/usr/bin/python
# -*- coding: utf-8 -*-

__doc__ = """Purge unused elements from selected families and optionally standardize units. Processes nested families recursively.
EnneadTab dump folder when the original path is unavailable.
"""
__title__ = "CleanUp\nFamily"
__tip__ = True

import os
import time
import traceback
from pyrevit import script
from pyrevit.revit import ErrorSwallower
import proDUCKtion  # pyright: ignore
proDUCKtion.validify()
from EnneadTab import ENVIRONMENT, NOTIFICATION, ERROR_HANDLE, LOG
from EnneadTab.REVIT import REVIT_APPLICATION, REVIT_FAMILY, REVIT_SELECTION, REVIT_FORMS, REVIT_SYNC, REVIT_UNIT
from Autodesk.Revit import DB  # pyright: ignore
from System.Collections.Generic import List, HashSet  # pyright: ignore

# Get current document
uidoc = REVIT_APPLICATION.get_uidoc()
doc = REVIT_APPLICATION.get_doc()


UNIT_MODE_IDS = {
    "metric": {
        "length": "millimeters",
        "area": "squareMeters"
    },
    "imperial": {
        "length": "feetFractionalInches",
        "area": "squareFeet"
    }
}


def _get_unit_id_safe(unit_name):
    try:
        unit_id = REVIT_UNIT.lookup_unit_id(unit_name)
        if unit_id is not None:
            return unit_id
    except Exception:
        pass
    return None


def _get_spec_id_safe(spec_name):
    try:
        spec_id = REVIT_UNIT.lookup_unit_spec_id(spec_name)
        if spec_id is not None:
            return spec_id
    except Exception:
        pass

    fallback_specs = {
        "length": DB.SpecTypeId.Length,
        "area": DB.SpecTypeId.Area,
        "number": DB.SpecTypeId.Number
    }
    return fallback_specs.get(spec_name)


def change_document_units(doc_obj, unit_mode):
    if not doc_obj or unit_mode not in UNIT_MODE_IDS:
        return False

    transaction = DB.Transaction(doc_obj, "EnneadTab Set Family Units")
    try:
        transaction.Start()

        project_units = doc_obj.GetUnits()
        unit_types = UNIT_MODE_IDS[unit_mode]

        for unit_type_key in unit_types:
            unit_name = unit_types[unit_type_key]
            unit_id = _get_unit_id_safe(unit_name)
            spec_id = _get_spec_id_safe(unit_type_key)

            if unit_id is None or spec_id is None:
                continue

            try:
                format_options = DB.FormatOptions(unit_id)
                project_units.SetFormatOptions(spec_id, format_options)
            except Exception as format_error:
                ERROR_HANDLE.print_note(
                    "Warning: Could not set format for {} in '{}': {}".format(
                        unit_type_key,
                        doc_obj.Title,
                        str(format_error)
                    )
                )

        doc_obj.SetUnits(project_units)
        transaction.Commit()
        return True
    except Exception as change_error:
        if transaction.HasStarted():
            transaction.RollBack()
        ERROR_HANDLE.print_note(
            "Error converting units in '{}': {}".format(
                doc_obj.Title,
                str(change_error)
            )
        )
        return False



class FamilyCleanupProcessor:
    """Handles the cleanup process for families and their nested families."""
    
    def __init__(self):
        self.output = script.get_output()
        self.output.close_others()
        self.processed_families = set()  # Track processed families to avoid duplicates
        self.cleanup_results = []  # Store cleanup results for reporting
        self.total_elements_deleted = 0
        self.families_processed = 0
        self.families_failed = 0
        self.unit_mode = None
        self.unit_action_desc = "Keep current family units"
        self.unit_attempted = 0
        self.unit_success = 0

    def set_unit_mode(self, unit_mode, description):
        self.unit_mode = unit_mode
        self.unit_action_desc = description

    def _apply_unit_mode(self, family_doc):
        if not self.unit_mode:
            return
        self.unit_attempted += 1
        if change_document_units(family_doc, self.unit_mode):
            self.unit_success += 1
        else:
            ERROR_HANDLE.print_note(
                "Unit change failed for '{}'.".format(family_doc.Title)
            )

    def _save_family_document(self, family_doc, family_name):
        original_path = family_doc.PathName

        if original_path:
            try:
                family_doc.Save()
                return original_path
            except Exception as save_error:
                ERROR_HANDLE.print_note(
                    "Could not save '{}' to original location '{}': {}".format(
                        family_name,
                        original_path,
                        str(save_error)
                    )
                )

        temp_folder = os.path.join(ENVIRONMENT.DUMP_FOLDER, "family_cleanup")
        if not os.path.exists(temp_folder):
            os.makedirs(temp_folder)

        temp_path = os.path.join(temp_folder, family_name + ".rfa")
        save_as_options = DB.SaveAsOptions()
        save_as_options.OverwriteExistingFile = True

        try:
            family_doc.SaveAs(temp_path, save_as_options)
            NOTIFICATION.messenger(
                "Saved '{}' to temporary location because the original path was unavailable or read-only:\n{}".format(
                    family_name,
                    temp_path
                )
            )
            return temp_path
        except Exception as save_as_error:
            ERROR_HANDLE.print_note(
                "Failed to save '{}' to temporary location '{}': {}".format(
                    family_name,
                    temp_path,
                    str(save_as_error)
                )
            )
            raise
        
    def select_families_from_project(self):
        """Prompt user to select families from the project.
        
        Returns:
            list: Selected Family objects, or None if cancelled
        """
        # Use EnneadTab's REVIT_SELECTION to pick families
        selected = REVIT_SELECTION.pick_family(
            doc=doc,
            multi_select=True,
            include_2D=True,
            include_3D=True
        )
        
        if not selected:
            return None
            
        # Filter to only editable families
        editable_families = []
        for family in selected:
            if not family:
                continue
            # Skip in-place families
            if family.IsInPlace:
                continue
            # Only include editable families
            if not family.IsEditable:
                NOTIFICATION.messenger(
                    "Family '{}' cannot be edited and will be skipped.".format(family.Name)
                )
                continue
                
            editable_families.append(family)
        
        if not editable_families:
            NOTIFICATION.messenger("None of the selected families can be edited!")
            return None
            
        return editable_families
    
    def purge_unused_elements(self, family_doc):
        """Purge all unused elements from a family document repeatedly until none remain.
        
        Args:
            family_doc: The family document to purge
            
        Returns:
            int: Total number of elements deleted
        """
        if not family_doc:
            return 0
            
        total_deleted = 0
        iteration = 0
        max_iterations = 50  # Safety limit to prevent infinite loops
        
        # Keep purging until no more unused elements are found
        while iteration < max_iterations:
            iteration += 1
            
            # Use transaction to delete unused elements
            t = DB.Transaction(family_doc, "Purge Unused Elements - Pass {}".format(iteration))
            t.Start()
            
            try:
                # Get all unused elements using Revit API
                # GetUnusedElements(ISet<ElementId>) returns an ICollection<ElementId> of purgeable elements
                # Pass an empty ISet to get all unused elements
                unused_element_ids = family_doc.GetUnusedElements(HashSet[DB.ElementId]())
                
                if unused_element_ids and unused_element_ids.Count > 0:
                    # Convert to list for deletion
                    ids_to_delete = list(unused_element_ids)
                    deleted_count = len(ids_to_delete)
                    
                    # Delete the unused elements
                    family_doc.Delete(List[DB.ElementId](ids_to_delete))
                    
                    total_deleted += deleted_count
                    
                    t.Commit()
                    
                    # Log progress for debugging
                    if iteration > 1:
                        print("  Purge pass {}: {} elements deleted".format(iteration, deleted_count))
                else:
                    # No more unused elements, we're done
                    t.RollBack()
                    break
                
            except Exception as e:
                t.RollBack()
                ERROR_HANDLE.print_note(
                    "Error purging elements from '{}' on pass {}: {}".format(
                        family_doc.Title, iteration, str(e)
                    )
                )
                break
        
        if iteration >= max_iterations:
            ERROR_HANDLE.print_note(
                "WARNING: Reached maximum purge iterations ({}) for '{}'".format(
                    max_iterations, family_doc.Title
                )
            )
        
        return total_deleted
    
    def get_nested_families(self, family_doc):
        """Get all nested families within a family document.
        
        Args:
            family_doc: The family document to search
            
        Returns:
            list: List of nested Family objects
        """
        if not family_doc:
            return []
            
        nested_families = []
        
        try:
            # Collect all families in the family document
            families_collector = DB.FilteredElementCollector(family_doc).OfClass(DB.Family)
            
            for family in families_collector:
                if not family:
                    continue
                # Skip if already processed
                if family.Name in self.processed_families:
                    continue
                # Only include editable families
                if family.IsEditable and family.IsUserCreated:
                    nested_families.append(family)
                    
        except Exception as e:
            ERROR_HANDLE.print_note(
                "Error getting nested families from '{}': {}".format(
                    family_doc.Title, str(e)
                )
            )
        
        return nested_families
    
    def cleanup_family_recursive(self, family, parent_doc, indentation_level=0):
        """Recursively clean up a family and all its nested families.
        
        Args:
            family: The Family object to clean up
            parent_doc: The parent document that contains this family
            indentation_level: Current nesting level for display purposes
            
        Returns:
            tuple: (success, elements_deleted)
        """
        family_name = family.Name
        
        # Skip if already processed
        if family_name in self.processed_families:
            return True, 0
        
        family_doc = None
        total_deleted = 0
        
        try:
            # Mark as being processed
            self.processed_families.add(family_name)
            
            # Notify user which family is being processed
            indent = "  " * indentation_level
            NOTIFICATION.messenger("{}Processing: {}".format(indent, family_name))
            
            # Open the family document for editing
            family_doc = parent_doc.EditFamily(family)
            
            if not family_doc:
                raise Exception("Could not open family document")
            
            self._apply_unit_mode(family_doc)

            # Step 1: Get and process nested families first (bottom-up approach)
            nested_families = self.get_nested_families(family_doc)
            
            if nested_families:
                for nested_family in nested_families:
                    try:
                        # Recursively process nested family
                        _, deleted = self.cleanup_family_recursive(
                            nested_family, 
                            family_doc, 
                            indentation_level + 1
                        )
                        total_deleted += deleted
                        
                    except Exception as e:
                        ERROR_HANDLE.print_note(
                            "Error processing nested family '{}': {}".format(
                                nested_family.Name, str(e)
                            )
                        )
            
            # Step 2: Purge unused elements from current family
            deleted_count = self.purge_unused_elements(family_doc)
            total_deleted += deleted_count
            
            # Step 3: Save the family document with clear fallback messaging
            try:
                self._save_family_document(family_doc, family_name)
            except Exception as save_failure:
                raise Exception("Unable to save family '{}': {}".format(family_name, str(save_failure)))
            
            # Step 4: Load family back into parent document
            family_doc.LoadFamily(parent_doc, REVIT_FAMILY.EnneadTabFamilyLoadingOption())
            
            # Step 5: Close family document
            family_doc.Close(False)
            family_doc = None
            
            self.families_processed += 1
            self.total_elements_deleted += total_deleted
            
            # Notify completion
            NOTIFICATION.messenger("{}Completed: {} ({} elements deleted)".format(
                indent, family_name, deleted_count
            ))
            
            # Record result
            self.cleanup_results.append({
                'name': family_name,
                'level': indentation_level,
                'deleted': deleted_count,
                'status': 'Success'
            })
            
            return True, total_deleted
            
        except Exception as e:
            self.families_failed += 1
            error_msg = str(e)
            ERROR_HANDLE.print_note(traceback.format_exc())
            
            # Notify failure
            NOTIFICATION.messenger("FAILED: {} - {}".format(family_name, error_msg))
            
            # Record failure
            self.cleanup_results.append({
                'name': family_name,
                'level': indentation_level,
                'deleted': 0,
                'status': 'Failed: ' + error_msg
            })
            
            # Make sure to close family doc if it was opened
            if family_doc:
                try:
                    family_doc.Close(False)
                except:
                    pass
            
            return False, 0
    
    def process_selected_families(self, families):
        """Process all selected families.
        
        Args:
            families: List of Family objects to process
        """
        if not families:
            return
        
        start_time = time.time()
        
        # Notify start of processing
        NOTIFICATION.messenger("Starting cleanup of {} families...".format(len(families)))
        if self.unit_action_desc:
            NOTIFICATION.messenger("Unit preference: {}".format(self.unit_action_desc))
        
        # Process each selected family
        for family in families:
            try:
                self.cleanup_family_recursive(family, doc, 0)
            except Exception as e:
                ERROR_HANDLE.print_note(
                    "Unexpected error processing '{}': {}".format(
                        family.Name, str(e)
                    )
                )
                ERROR_HANDLE.print_note(traceback.format_exc())
        
        # Calculate elapsed time
        elapsed_time = time.time() - start_time
        
        # Display summary
        self.display_summary(elapsed_time)
    
    def display_summary(self, elapsed_time):
        """Display cleanup summary.
        
        Args:
            elapsed_time: Time taken in seconds
        """
        print("\n" + "=" * 80)
        print("CLEANUP SUMMARY")
        print("=" * 80)
        print("Families Processed: {}".format(self.families_processed))
        print("Families Failed: {}".format(self.families_failed))
        print("Total Elements Deleted: {}".format(self.total_elements_deleted))
        if self.unit_mode:
            unit_success_text = "{} of {}".format(self.unit_success, self.unit_attempted)
            print("Unit Preference: {}".format(self.unit_action_desc))
            print("Unit Changes Applied: {}".format(unit_success_text))
        print("Time Elapsed: {:.2f} seconds".format(elapsed_time))
        print("=" * 80)
        
        # Create detailed table
        if self.cleanup_results:
            table_data = []
            for result in self.cleanup_results:
                indent = "  " * result['level']
                table_data.append([
                    indent + result['name'],
                    result['deleted'],
                    result['status']
                ])
            
            self.output.print_table(
                table_data=table_data,
                title="Family Cleanup Details",
                columns=["Family Name", "Elements Deleted", "Status"],
                formats=['', '', '']
            )
        
        # Show completion message
        if self.unit_mode:
            unit_summary = "\nUnits: {} ({} of {} families updated)".format(
                self.unit_action_desc,
                self.unit_success,
                self.unit_attempted
            )
        else:
            unit_summary = ""

        if self.families_failed > 0:
            msg = (
                "Cleanup completed with {} failures.\n\n"
                "See output window for details.{}"
            ).format(
                self.families_failed,
                unit_summary
            )
        else:
            msg = (
                "Cleanup completed successfully!\n\n"
                "Processed: {} families\nDeleted: {} elements{}"
            ).format(
                self.families_processed,
                self.total_elements_deleted,
                unit_summary
            )
        
        NOTIFICATION.messenger(msg)


@LOG.log(__file__, __title__)
@ERROR_HANDLE.try_catch_error()
def main():
    """Main entry point for the script."""
    
    # Check if we're in a project document
    if doc.IsFamilyDocument:  # pyright: ignore
        NOTIFICATION.messenger(
            "This tool is designed to work in project documents, not family documents.\n\n"
            "Please open a project document and try again."
        )
        return
    
    # Create processor
    processor = FamilyCleanupProcessor()
    
    # Select families to clean up
    selected_families = processor.select_families_from_project()
    
    if not selected_families:
        return
    
    unit_options = [
        ("Keep current family units", None, "Keep current family units"),
        ("Set to Metric (millimeters)", "metric", "Set units to Metric (millimeters)"),
        ("Set to Imperial (feet-inches)", "imperial", "Set units to Imperial (feet-inches)")
    ]

    unit_labels = [option[0] for option in unit_options]
    unit_choice = REVIT_FORMS.dialogue(
        title="Family Unit Preference",
        main_text="Select unit system to apply to cleaned families:",
        sub_text=None,
        options=unit_labels
    )

    if unit_choice is None:
        unit_choice = unit_labels[0]

    for option in unit_options:
        if option[0] == unit_choice:
            processor.set_unit_mode(option[1], option[2])
            break

    # Ask if user wants to sync and close after completion
    will_sync_and_close = REVIT_SYNC.do_you_want_to_sync_and_close_after_done()
    
    # Confirm action using EnneadTab dialog
    main_text = "You are about to clean up {} families.".format(len(selected_families))
    unit_line = "- Units: {}".format(processor.unit_action_desc)
    sub_text = (
        "This will:\n"
        "- Purge all unused elements from each family\n"
        "- Recursively process all nested families\n"
        "- Save and reload families after cleanup\n"
        "{}\n\n"
        "This operation may take several minutes.\n\n"
        "Do you want to continue?"
    ).format(unit_line)
    
    result = REVIT_FORMS.dialogue(
        title="Confirm Family Cleanup",
        main_text=main_text,
        sub_text=sub_text,
        options=["Yes, Continue", "No, Cancel"],
        icon="warning"
    )
    
    if result != "Yes, Continue":
        return
    
    # Process families with error swallowing
    with ErrorSwallower():
        processor.process_selected_families(selected_families)
    
    # Sync and close if requested
    if will_sync_and_close:
        REVIT_SYNC.sync_and_close()


####################################
if __name__ == "__main__":
    main()

