#!/usr/bin/python
# -*- coding: utf-8 -*-

__doc__ = """Random deselection tool for Revit elements.

This tool allows you to randomly deselect a portion of your currently selected elements.
Perfect for when you have too many elements selected and want to reduce the selection
to a manageable subset for further operations.

Features:
- Uses PyRevit input slider to control percentage of elements to keep
- Random selection ensures unbiased element reduction
- Preserves original selection order for consistency
- Safe operation with proper error handling

Usage:
1. Select elements you want to work with
2. Run this tool
3. Use the slider to set percentage of elements to keep (0-100%)
4. Confirm to apply random deselection
"""
__title__ = "Random\nDeselect"
__tip__ = True
__is_popular__ = True

import random
from pyrevit import forms, script
import proDUCKtion # pyright: ignore 
proDUCKtion.validify()

from EnneadTab import ERROR_HANDLE, LOG, NOTIFICATION, DATA_CONVERSION
from EnneadTab.REVIT import REVIT_SELECTION, REVIT_APPLICATION
from Autodesk.Revit import DB, UI # pyright: ignore 

uidoc = REVIT_APPLICATION.get_uidoc()
doc = REVIT_APPLICATION.get_doc()

class Solution:
    
    @ERROR_HANDLE.try_catch_error()
    def random_deselect(self):
        """Main function to perform random deselection of selected elements."""
        
        # Get currently selected elements
        selected_elements = REVIT_SELECTION.get_selection(uidoc)
        
        if not selected_elements:
            NOTIFICATION.messenger("No elements are currently selected. Please select some elements first.")
            return
            
        total_elements = len(selected_elements)
        print("Total selected elements: {}".format(total_elements))
        
        # Show input slider for percentage to keep
        keep_percentage = forms.ask_for_string(
            default="80",
            prompt="Enter percentage of elements to KEEP (0-100):",
            title="Random Deselect Tool"
        )
        
        if not keep_percentage:
            return
            
        try:
            keep_percentage = float(keep_percentage)
            if keep_percentage < 0 or keep_percentage > 100:
                NOTIFICATION.messenger("Percentage must be between 0 and 100.")
                return
        except ValueError:
            NOTIFICATION.messenger("Please enter a valid number between 0 and 100.")
            return
            
        # Calculate how many elements to keep
        elements_to_keep = int(round(total_elements * keep_percentage / 100.0))
        
        if elements_to_keep >= total_elements:
            NOTIFICATION.messenger("All elements will be kept (no deselection needed).")
            return
            
        if elements_to_keep <= 0:
            # Confirm if user wants to deselect all elements
            if not forms.alert("This will deselect ALL elements. Are you sure?", 
                             title="Confirm Full Deselection", 
                             yes=True, no=True):
                return
            elements_to_keep = 0
        
        # Randomly select elements to keep
        elements_to_keep_list = random.sample(selected_elements, elements_to_keep)
        
        # Show confirmation with details
        confirmation_msg = "Will keep {} out of {} elements ({}%)\n\nElements to keep:".format(
            elements_to_keep, total_elements, keep_percentage
        )
        
        # Show preview of elements to keep
        output = script.get_output()
        output.freeze()
        for i, element in enumerate(elements_to_keep_list[:10]):  # Show first 10
            if element.Category:
                print("{} - {} ({})".format(i + 1, output.linkify(element.Id), element.Category.Name))
            else:
                print("{} - {} (No Category)".format(i + 1, output.linkify(element.Id)))
        
        if len(elements_to_keep_list) > 10:
            print("... and {} more elements".format(len(elements_to_keep_list) - 10))
        output.unfreeze()
        
        # Confirm the operation
        if not forms.alert(confirmation_msg, 
                          title="Confirm Random Deselection", 
                          yes=True, no=True):
            return
        
        # Perform the deselection
        self._perform_deselection(elements_to_keep_list)
        
        # Show results
        elements_deselected = total_elements - elements_to_keep
        NOTIFICATION.messenger("Random deselection completed!\nKept: {} elements\nDeselected: {} elements".format(
            elements_to_keep, elements_deselected
        ))
        
        print("\n=== Random Deselection Results ===")
        print("Original selection: {} elements".format(total_elements))
        print("Elements kept: {} elements".format(elements_to_keep))
        print("Elements deselected: {} elements".format(elements_deselected))
        print("Keep percentage: {}%".format(keep_percentage))
    
    def _perform_deselection(self, elements_to_keep):
        """Perform the actual deselection operation."""
        try:
            # Clear current selection
            uidoc.Selection.SetElementIds(DATA_CONVERSION.list_to_system_list([]))
            
            # Add back only the elements we want to keep
            if elements_to_keep:
                element_ids = [element.Id for element in elements_to_keep]
                print("Converting {} element IDs to .NET collection...".format(len(element_ids)))
                
                # Use the same pattern as REVIT_SELECTION.set_selection()
                system_element_ids = DATA_CONVERSION.list_to_system_list([x.Id for x in elements_to_keep])
                print("Successfully converted to .NET collection: {}".format(type(system_element_ids)))
                
                uidoc.Selection.SetElementIds(system_element_ids)
                print("Selection updated successfully")
                
        except Exception as e:
            NOTIFICATION.messenger("Error during deselection: {}".format(str(e)))
            print("Error details: {}".format(str(e)))
            raise

@LOG.log(__file__, __title__)
@ERROR_HANDLE.try_catch_error()
def main():
    """Main entry point for the script."""
    Solution().random_deselect()

################## main code below #####################

if __name__ == "__main__":
    output = script.get_output()
    output.close_others()
    main() 