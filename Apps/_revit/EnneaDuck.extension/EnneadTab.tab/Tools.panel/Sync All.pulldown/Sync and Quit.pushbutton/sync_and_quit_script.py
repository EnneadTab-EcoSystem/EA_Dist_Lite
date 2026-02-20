__doc__ = "Sync all open projects with central, then quit Revit. One-click end-of-day: sync every open document, close them, and exit Revit. Use when you are done for the day and want to leave nothing open."
__title__ = "Sync and Quit"
__post_link__ = "https://ei.ennead.com/_layouts/15/Updates/ViewPost.aspx?ItemID=28744"
__tip__ = True
__is_popular__ = True
import random
import proDUCKtion # pyright: ignore
proDUCKtion.validify()
from EnneadTab.REVIT import REVIT_APPLICATION, REVIT_SYNC, REVIT_EVENT
from EnneadTab import ERROR_HANDLE, LOG, NOTIFICATION
from pyrevit import script

QUIT_MESSAGES = [
    "I quit!!!!",
    "Last time touching Revit today.",
    "Peace out. Not opening you again until tomorrow.",
    "Sync done. My soul is free.",
    "Closing Revit before Revit closes me.",
    "That's it. I'm done. Bye.",
    "See you never (until tomorrow).",
    "Revit closed. Mental health restored.",
    "Logging off before the model logs me off.",
]

uidoc = REVIT_APPLICATION.get_uidoc()
doc = REVIT_APPLICATION.get_doc()


@LOG.log(__file__, __title__)
@ERROR_HANDLE.try_catch_error()
def main():
    REVIT_EVENT.set_all_sync_closing(True)
    REVIT_SYNC.sync_and_close()
    REVIT_EVENT.set_all_sync_closing(False)

    output = script.get_output()
    killtime = 30
    output.self_destruct(killtime)

    msg = random.choice(QUIT_MESSAGES)
    NOTIFICATION.messenger(msg)

    REVIT_APPLICATION.close_revit_app()


################## main code below #####################
if __name__ == "__main__":
    main()
