
from pyrevit import EXEC_PARAMS
# pyRevit hook engines do not inherit the .lib search path that button scripts get,
# so put KingDuck.lib on sys.path before importing proDUCKtion (the EnneadTab bootstrap).
import os, sys
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "..", "KingDuck.lib")))
import proDUCKtion # pyright: ignore 
proDUCKtion.validify()
from EnneadTab import ERROR_HANDLE
from EnneadTab.REVIT import REVIT_SYNC



########## main code below ############
# this varaible is set to True only after    use sync and close all is run ealier. So if user open new docs, we shoudl resume default False,


@ERROR_HANDLE.try_catch_error(is_silent=True)
def main():

    doc = EXEC_PARAMS.event_args.Document


    if doc is None:
        return

    if doc.IsFamilyDocument:
        return
    
    
    REVIT_SYNC.update_last_sync_data_file(doc)






############################
if __name__ == "__main__":
    main()
