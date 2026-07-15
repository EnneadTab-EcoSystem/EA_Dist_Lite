from pyrevit import EXEC_PARAMS
# pyRevit hook engines do not inherit the .lib search path that button scripts get,
# so put KingDuck.lib on sys.path before importing proDUCKtion (the EnneadTab bootstrap).
import os, sys
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "..", "KingDuck.lib")))
import proDUCKtion # pyright: ignore 
proDUCKtion.validify()
from EnneadTab import VERSION_CONTROL, ERROR_HANDLE
from EnneadTab.REVIT import REVIT_SYNC
import random

doc = EXEC_PARAMS.event_args.Document

def remove_last_sync_data_file(doc):
    REVIT_SYNC.remove_last_sync_data_file(doc)



def update_pyrevit():
    # occasionally update the pyrevit. Do it here becasue normally when you close doc you are relaxed and not care if it take too long
    if random.random() > 0.01:
        return
        
    from pyrevit.versionmgr import updater
    if updater.check_for_updates():
        updater.update_pyrevit()

@ERROR_HANDLE.try_catch_error(is_silent=True)
def main():
    if doc.IsFamilyDocument:
        return
    remove_last_sync_data_file(doc)
    update_pyrevit()

    if random.random() < 0.1 and VERSION_CONTROL is not None:
        VERSION_CONTROL.update_dist_repo()


###################################################
if __name__ == '__main__':
    main()
    
    
