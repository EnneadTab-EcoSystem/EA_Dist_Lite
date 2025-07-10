#!/usr/bin/python
# -*- coding: utf-8 -*-

__doc__ = "Convert between a typical imperial family and metric family by setting up unit."
__title__ = "Change Family Unit"
__tip__ = True
import proDUCKtion  # pyright: ignore
proDUCKtion.validify()

from EnneadTab import ERROR_HANDLE, LOG
from EnneadTab.REVIT import REVIT_APPLICATION, REVIT_FORMS, REVIT_UNIT, REVIT_FAMILY
from Autodesk.Revit import DB  # pyright: ignore
from pyrevit import forms  # pyright: ignore

# UIDOC = REVIT_APPLICATION.get_uidoc()
DOC = REVIT_APPLICATION.get_doc()

# Global dictionary for unit conversion IDs with fallback values
UNIT_IDS = {
    "metric": {
        "length": "millimeters",
        "area": "squareMeters"
    },
    "imperial": {
        "length": "feetFractionalInches",
        "area": "squareFeet"
    }
}



def get_unit_id_safe(unit_name):
    """Safely get unit ID."""
    try:
        unit_id = REVIT_UNIT.lookup_unit_id(unit_name)
        if unit_id is not None:
            return unit_id
    except:
        pass
    
    return None

def get_spec_id_safe(spec_name):
    """Safely get spec ID."""
    try:
        spec_id = REVIT_UNIT.lookup_unit_spec_id(spec_name)
        if spec_id is not None:
            return spec_id
    except:
        pass
    
    # Fallback to common spec types
    fallback_specs = {
        "length": DB.SpecTypeId.Length,
        "area": DB.SpecTypeId.Area,
        "number": DB.SpecTypeId.Number
    }
    
    return fallback_specs.get(spec_name)

def change_document_units(doc, to_metric):
    """Change document units with error handling."""
    try:
        # Start a transaction
        t = DB.Transaction(doc, 'Convert Units')
        t.Start()

        # Get current document units
        project_units = doc.GetUnits()

        # Determine the conversion mode
        unit_system = "metric" if to_metric else "imperial"

        # List of unit types to convert (length, area)
        unit_types = ["length", "area"]

        # Loop through the unit types and convert each one
        for unit_type in unit_types:
            unit_name = UNIT_IDS[unit_system][unit_type]
            unit_id = get_unit_id_safe(unit_name)
            spec_id = get_spec_id_safe(unit_type)
            
            if unit_id is not None and spec_id is not None:
                try:
                    new_format_options = DB.FormatOptions(unit_id)
                    project_units.SetFormatOptions(spec_id, new_format_options)
                except Exception as e:
                    print("Warning: Could not set format for {}: {}".format(unit_type, e))

        # Apply the updated units to the document
        doc.SetUnits(project_units)

        # Commit the transaction
        t.Commit()
        print("Units conversion completed for {}.".format(doc.Title))

    except Exception as e:
        if 't' in locals() and t.HasStarted():
            t.RollBack()
        print("Error converting units in {}: {}".format(doc.Title, e))
        raise

def get_family_names_from_project():
    """Get all editable family names from the current project using REVIT_FAMILY module."""
    return sorted(REVIT_FAMILY.get_editable_family_names(DOC))

def get_families_by_names(family_names):
    """Get editable family objects by their names using REVIT_FAMILY module."""
    editable_families = REVIT_FAMILY.get_editable_families(DOC)
    selected_families = []
    
    for family in editable_families:
        if family.Name in family_names:
            selected_families.append(family)
    
    return selected_families

def process_family_document(family_doc, to_metric):
    """Process a family document for unit conversion."""
    try:
        # Change units in the family document
        change_document_units(family_doc, to_metric)
        
        # Load the converted family directly back into the project
        loading_opt = REVIT_FAMILY.EnneadTabFamilyLoadingOption()
        REVIT_FAMILY.load_family(family_doc, DOC, loading_opt)
        
        print("Successfully converted and loaded family: {}".format(family_doc.Title))
        
        return True
    except Exception as e:
        print("Error processing family {}: {}".format(family_doc.Title, e))
        return False

def process_nested_families(families, to_metric):
    """Process nested families with better error handling."""
    success_count = 0
    total_count = len(families)
    
    for i, family in enumerate(families, 1):
        family_doc = None
        try:
            print("Processing family {}/{}: {}".format(i, total_count, family.Name))
            
            # Get the family document
            family_doc = DOC.EditFamily(family)
            
            if family_doc is not None:
                # Process the family document
                if process_family_document(family_doc, to_metric):
                    success_count += 1
            else:
                print("Could not open family document for: {}".format(family.Name))
                
        except Exception as e:
            print("Error processing family {}: {}".format(family.Name, e))
        finally:
            # Always close the family document
            if family_doc is not None:
                try:
                    family_doc.Close()
                except:
                    pass
    
    return success_count, total_count

@LOG.log(__file__, __title__)
@ERROR_HANDLE.try_catch_error()
def change_family_unit():
    """Main function to change family units with user selection."""
    
    # User input: choose to convert to Metric or Imperial
    ops = ["Convert To Imperial", "Convert To Metric"]
    res = REVIT_FORMS.dialogue(main_text="Choose the unit conversion mode:", options=ops)

    if res is None:
        return

    to_metric = (res == ops[1])  # True for Metric, False for Imperial
    
    # Get all available family names
    family_names = get_family_names_from_project()
    
    if not family_names:
        REVIT_FORMS.dialogue(main_text="No editable families found in the project.")
        return
    
    # Let user select families
    selected_names = forms.SelectFromList.show(
        family_names,
        title="Select Families to Convert",
        multiselect=True,
        button_name="Select Families"
    )
    
    if not selected_names:
        print("No families selected.")
        return
    
    # Get the selected family objects
    selected_families = get_families_by_names(selected_names)
    
    if not selected_families:
        REVIT_FORMS.dialogue(main_text="No valid families found from selection.")
        return
    
    # Confirm the operation
    unit_type = "Metric" if to_metric else "Imperial"
    confirm_msg = "Convert {} families to {} units?".format(len(selected_families), unit_type)
    confirm_options = ["Yes, proceed", "Cancel"]
    confirm_result = REVIT_FORMS.dialogue(main_text=confirm_msg, options=confirm_options)
    if confirm_result != confirm_options[0]:
        return
    
    # Process the families
    print("Starting conversion of {} families to {} units...".format(len(selected_families), unit_type))
    
    success_count, total_count = process_nested_families(selected_families, to_metric)
    
    # Show results
    result_msg = "Conversion completed!\n\nSuccessfully converted: {}/{} families".format(success_count, total_count)
    if success_count < total_count:
        result_msg += "\nFailed: {} families".format(total_count - success_count)
    
    REVIT_FORMS.dialogue(main_text=result_msg)
    print(result_msg)

################## main code below #####################
if __name__ == "__main__":
    change_family_unit()
