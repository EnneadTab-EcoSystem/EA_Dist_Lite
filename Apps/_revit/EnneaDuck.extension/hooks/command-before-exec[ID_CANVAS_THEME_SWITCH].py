
# from pyrevit import  EXEC_PARAMS, script
# pyRevit hook engines do not inherit the .lib search path that button scripts get,
# so put KingDuck.lib on sys.path before importing proDUCKtion (the EnneadTab bootstrap).
import os, sys
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "..", "KingDuck.lib")))
import proDUCKtion # pyright: ignore 
proDUCKtion.validify()
from EnneadTab import ERROR_HANDLE, NOTIFICATION, SOUND
# from Autodesk.Revit import DB # pyright: ignore
from Autodesk.Revit import UI # pyright: ignore
# args = EXEC_PARAMS.event_args
# doc = args.ActiveDocument 
# uidoc = UI.UIDocument(doc)
# uiapp = UI.UIApplication(doc.Application)
# uiapp.PostCommand(args.CommandId)

@ERROR_HANDLE.try_catch_error(is_silent=True)
def main():
    
    if UI.UIThemeManager.CurrentCanvasTheme == UI.UITheme.Dark:
        NOTIFICATION.duck_pop("Wake up!!!")
    else:
        NOTIFICATION.duck_pop("Go to sleep!!!")
    
    SOUND.play_sound("sound_effect_notification_new.wav")
    
############################


if __name__ == '__main__':
    main()