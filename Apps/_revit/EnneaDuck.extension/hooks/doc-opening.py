from pyrevit import EXEC_PARAMS
from pyrevit.coreutils import envvars
# pyRevit hook engines do not inherit the .lib search path that button scripts get,
# so put KingDuck.lib on sys.path before importing proDUCKtion (the EnneadTab bootstrap).
import os, sys
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "..", "KingDuck.lib")))
import proDUCKtion # pyright: ignore 
proDUCKtion.validify()
from EnneadTab import ERROR_HANDLE, FOLDER, ARCADE
from EnneadTab.REVIT import REVIT_FORMS, REVIT_EVENT





def check_is_template_folder():
    if REVIT_EVENT.is_L_drive_alert_hook_depressed:
        return
    path = EXEC_PARAMS.event_args.PathName
    extension = FOLDER.get_file_extension_from_path(path)
    #print extension
    if extension not in [".rft", ".rfa"]:
        return
    if r"L:\4b_Applied Computing\01_Revit\02_Template" in path or r"L:\4b_Applied Computing\01_Revit\03_Library" in path:
        REVIT_FORMS.notification(self_destruct = 5,main_text = "This family is currently saved in L drive\nRepath to your project folder to avoid affecting the original.", sub_text = path)

@ERROR_HANDLE.try_catch_error(is_silent=True)
def main():
    check_is_template_folder()
    # A document open can freeze Revit as long as a sync does. Arm the arcade wait-watcher;
    # doc-opened deletes the flag when the open resolves. Contract: EnneadTab/ARCADE.py.
    doc_name = ""
    try:
        doc_name = os.path.basename(EXEC_PARAMS.event_args.PathName or "")
    except Exception:
        pass
    ARCADE.start_wait_watch("open", doc_name)

##########################################

if __name__ == '__main__':
    main()