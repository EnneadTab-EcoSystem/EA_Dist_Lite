#!/usr/bin/python
# -*- coding: utf-8 -*-



__doc__ = "Create new sheets based on data from Excel.\nIf you need help on what kind of Excel to prepare, you can open a sample excel and begin from there."
__title__ = "Create Sheets\nBy Excel"
__tip__ = True
__is_popular__ = True
from pyrevit import forms #
from pyrevit import script #


import proDUCKtion # pyright: ignore 
proDUCKtion.validify()
from EnneadTab.REVIT import REVIT_APPLICATION
from EnneadTab import NOTIFICATION, ERROR_HANDLE, LOG
from Autodesk.Revit import DB # pyright: ignore 
# from Autodesk.Revit import UI # pyright: ignore
uidoc = REVIT_APPLICATION.get_uidoc()
doc = REVIT_APPLICATION.get_doc()

# Import helper functions
from excel_sheet_helper import (
    read_excel_data,
    find_filter_column,
    find_sheet_number_column,
    parse_excel_data,
    filter_data_by_yes,
    extract_sheet_numbers,
    create_sheet_from_row_data
)
        


def is_new_sheet_number_ok(new_sheet_numbers):       
    all_sheets = DB.FilteredElementCollector(doc).OfCategory(DB.BuiltInCategory.OST_Sheets).WhereElementIsNotElementType().ToElements()
    all_sheet_numbers = [x.SheetNumber for x in all_sheets]
    
    # get the intersection between the new sheet numbers and the existing sheet numbers
    # if the intersection is empty, then the new sheet numbers are all unique
    intersection = set(new_sheet_numbers) & set(all_sheet_numbers)
    
    if intersection:
        print ("The following sheet numbers are already in use: {}".format(intersection))

        NOTIFICATION.messenger(main_text="You have {} sheet numbers that are already in use. Please check the sheet numbers and try again.".format(len(intersection)))

        return False
    return True
    

@LOG.log(__file__, __title__)
@ERROR_HANDLE.try_catch_error()
def excel_sheet_creator():
    """Main orchestrator function for creating sheets from Excel data."""
    # Configuration
    HEADER_ROW = 4  # Headers are in row 4 (1-based)
    WORKSHEET_NAME = "SheetList"
    
    # Step 1: Get Excel file path
    excel_path = forms.pick_excel_file(title="Where is the excel that has the new sheet data?")   
    
    if not excel_path:
        print("No Excel file selected. Operation cancelled.")
        return
    
    # Step 2: Read and parse Excel data
    raw_data, header_map = read_excel_data(excel_path, WORKSHEET_NAME, HEADER_ROW)
    if not raw_data or not header_map:
        return
    
    # Step 3: Find filter column (for "YES" values)
    filter_column = find_filter_column(header_map)
    
    # Step 4: Find Sheet Number column
    sheet_number_col, sheet_number_header = find_sheet_number_column(header_map)
    if sheet_number_col is None:
        NOTIFICATION.messenger(main_text="Cannot find 'Sheet Number' column in excel headers.")
        return
    
    # Step 5: Parse Excel data into structured format
    parsed_data = parse_excel_data(raw_data, sheet_number_header, HEADER_ROW)
    
    # Step 6: Filter data to only include rows marked with "YES"
    filtered_data = filter_data_by_yes(raw_data, parsed_data, filter_column, sheet_number_col, HEADER_ROW)
    if not filtered_data:
        NOTIFICATION.messenger(main_text="No rows found with 'YES' in filter column, or no valid sheet numbers found.")
        return
    
    # Step 7: Extract sheet numbers for validation
    new_sheet_numbers = extract_sheet_numbers(filtered_data, sheet_number_header)
    if not is_new_sheet_number_ok(new_sheet_numbers):
        return

    # Step 8: Get titleblock selection
    titleblock_type_id = forms.select_titleblocks(title="Pick the titleblock that will be used for the new sheets.")
    if not titleblock_type_id:
        return
    
    # Step 9: Create sheets in transaction
    t = DB.Transaction(doc, __title__)
    t.Start()
    try:
        for row_data in filtered_data:
            print(row_data)
            sheet = create_sheet_from_row_data(doc, row_data, titleblock_type_id, sheet_number_header)
            if sheet is None:
                continue
        t.Commit()
    except Exception as e:
        t.RollBack()
        raise e


################## main code below #####################
output = script.get_output()
output.close_others()


if __name__ == "__main__":
    excel_sheet_creator()
    











