__doc__ = """Sync every open model with central, then close them, leaving Revit running.

Use it when you are switching projects or stepping away: all your work reaches the
central files and the documents are closed behind you, but Revit stays open so you
can start something else."""
__title__ = "Sync All Open Proj and Close"
__post_link__ = "https://ei.ennead.com/_layouts/15/Updates/ViewPost.aspx?ItemID=28744"
__tip__ = True
__is_popular__ = True
import proDUCKtion # pyright: ignore 
proDUCKtion.validify()
from EnneadTab.REVIT import REVIT_APPLICATION, REVIT_SYNC, REVIT_EVENT
from EnneadTab import ERROR_HANDLE, LOG
from pyrevit import script

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

################## main code below #####################
if __name__ == "__main__":
    main()