#!/usr/bin/python
# -*- coding: utf-8 -*-



__doc__ = """Push selected sheets to a Miro board and keep markup alive across sheet updates.

Because each sheet image is replaced in place, comments and redlines stay stuck
to the drawing instead of being thrown away with the old PDF every time the
background changes. Review history survives the whole set of revisions.

Features:
- Sheets new to the board are flagged with a blue cross
- Sheets whose background changed are flagged with an orange star
- The last board URL you used is remembered for next time"""
__title__ = "Review\nOn Miro"
__tip__ = True
import shutil
from pyrevit import forms #
from pyrevit import script #


import proDUCKtion # pyright: ignore 
proDUCKtion.validify()
from EnneadTab.REVIT import REVIT_EXPORT, REVIT_APPLICATION, REVIT_SYNC
from EnneadTab import EXE, DATA_FILE, ENVIRONMENT,  NOTIFICATION, ERROR_HANDLE, FOLDER, LOG
from Autodesk.Revit import DB # pyright: ignore 
import os
# from Autodesk.Revit import UI # pyright: ignore
# uidoc = REVIT_APPLICATION.get_uidoc()
doc = REVIT_APPLICATION.get_doc()
            
   
@LOG.log(__file__, __title__)
@ERROR_HANDLE.try_catch_error()
def update_miro():

    print ("Note: At the moment CBI does not allow me to connect to Miro, so your team can ask me for a board on my personal account.")
    key = "recent_miro_url"
    recent_url = DATA_FILE.get_sticky(key,"https://miro.com/app/board/uXjVNsgWNfA=/")
    miro_url = forms.ask_for_string(
        prompt = "Please input the Miro board URL:",
        default= recent_url,
        title = "Makrup Sheet In Miro")

    print ("Miro URL: " + miro_url)
    DATA_FILE.set_sticky(key, miro_url)

    sheets = forms.select_sheets(title = "Select sheets to update")
    if not sheets:
        return



    res = REVIT_SYNC.do_you_want_to_sync_and_close_after_done()

    dump_folder = "{}\\miro_dump".format(FOLDER.DUMP_FOLDER)

    # make sure everytig is the lastest in this folder

    try:
        if os.path.exists(dump_folder):
            shutil.rmtree(dump_folder)

        if not os.path.exists(dump_folder):
            os.makedirs(dump_folder)
    except:
        pass

    for i, sheet in enumerate(sheets):
        sheet_name = sheet.Name
        sheet_num = sheet.SheetNumber
        guid = sheet.UniqueId
        file = "{}^{}^{}.jpg".format(guid,
                                    sheet_num,
                                    sheet_name)

        NOTIFICATION.messenger ("Exporting image {}/{}==> {}:{}".format(i + 1, len(sheets), sheet_num, sheet_name))
        REVIT_EXPORT.export_image(sheet, file, dump_folder)
    
    NOTIFICATION.duck_pop("Image Export done!\nPreparing to upload to Miro!")
    
    with DATA_FILE.update_data("miro") as data:
        data['url'] = miro_url
        data["images"] = [os.path.join(dump_folder, f) for f in sorted(os.listdir(dump_folder), key=lambda x: x.split("^")[1])]
        data["app"] = "revit_sheet"

    EXE.open_exe("MIRO")


    if res:
        REVIT_SYNC.sync_and_close()
    


################## main code below #####################


if __name__ == "__main__":
    output = script.get_output()
    output.close_others()
    update_miro()
    







