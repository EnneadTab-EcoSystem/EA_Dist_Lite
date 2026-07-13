__doc__ = """Sync every open model with central in one click and keep working.

All open documents are synchronized and left open, so your changes reach the team
without interrupting what you are doing. Worth running regularly through the day
instead of hoarding a whole afternoon of work."""
__title__ = "Sync All\nOpen Proj"
__post_link__ = "https://ei.ennead.com/_layouts/15/Updates/ViewPost.aspx?ItemID=28744"
__tip__ = True
from pyrevit import  script

import proDUCKtion # pyright: ignore 
proDUCKtion.validify()
from EnneadTab.REVIT import REVIT_APPLICATION

doc = REVIT_APPLICATION.get_doc()



from EnneadTab.REVIT import REVIT_SYNC
from EnneadTab import SOUND, ERROR_HANDLE, LOG



@LOG.log(__file__, __title__)
@ERROR_HANDLE.try_catch_error()
def main():
    

    REVIT_SYNC.sync_and_close(close_others = False)
    SOUND.play_sound()
    output = script.get_output()
    killtime = 30
    output.self_destruct(killtime)
################## main code below #####################
if __name__ == "__main__":

    main()
