
from pyrevit import  EXEC_PARAMS
# pyRevit hook engines do not inherit the .lib search path that button scripts get,
# so put KingDuck.lib on sys.path before importing proDUCKtion (the EnneadTab bootstrap).
import os, sys
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "..", "KingDuck.lib")))
import proDUCKtion # pyright: ignore 
proDUCKtion.validify()
from EnneadTab import ERROR_HANDLE, NOTIFICATION
args = EXEC_PARAMS.event_args
doc = args.ActiveDocument 



@ERROR_HANDLE.try_catch_error(is_silent=True)
def main():

    # if doc.IsFamilyDocument:
    #     return
    
    # if EnneadTab.USER.USER_NAME == "yumeng.an" and EnneadTab.TIME.get_YYYYMMDD() == "231215":
    #     return
    # if EnneadTab.USER.USER_NAME == "hjlee" and EnneadTab.TIME.get_YYYYMMDD() < "240315":
        
    #     return
    NOTIFICATION.duck_pop(main_text = "EnneaDuck dislikes [UserKeynote], that tag will not link to other database! Quack!\nOnly use [UserKeynote] when you have ABSOLUTELY no choice.")
    print("this duck is enforced and will not be turned off by setting.")
    args.Cancel = False

                                        
############################

if __name__ == '__main__':
    main()