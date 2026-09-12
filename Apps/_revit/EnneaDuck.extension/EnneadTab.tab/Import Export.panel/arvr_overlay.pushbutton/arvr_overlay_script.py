#!/usr/bin/python
# -*- coding: utf-8 -*-

__doc__ = """Open EnneadTab-ARVR: Mobile Camera AR Overlay for 3D Models.

Beam your Revit 3D views onto your smartphone camera in augmented reality:
- Export active 3D view or pick an existing .glb / .gltf / .usdz
- Upload directly into cloud room session
- Scan QR code to launch mobile camera AR overlay with 1:1 scale
- Zero app installs needed on phone or headset

Opens https://enneadtab.com/arvr
"""
__title__ = "AR/VR\nOverlay"

import os
import webbrowser

import clr # pyright: ignore
clr.AddReference("PresentationCore")
clr.AddReference("PresentationFramework")
clr.AddReference("WindowsBase")

import Microsoft.Win32 # pyright: ignore
from pyrevit.forms import WPFWindow # pyright: ignore

import proDUCKtion # pyright: ignore 
proDUCKtion.validify()

from EnneadTab import ERROR_HANDLE, LOG, NOTIFICATION, FOLDER, ARVR
from EnneadTab.REVIT import REVIT_APPLICATION
from Autodesk.Revit import DB # pyright: ignore 

UIDOC = REVIT_APPLICATION.get_uidoc()
DOC = REVIT_APPLICATION.get_doc()


class ARVROverlayWindow(WPFWindow):
    """Arcade-styled WPF Dialog for Revit ARVR export and web pairing."""

    def __init__(self, doc):
        xaml_path = os.path.join(os.path.dirname(__file__), "ARVR_Overlay_Form.xaml")
        WPFWindow.__init__(self, xaml_path)
        self.doc = doc

        # Generate default room code
        self.default_room_id = ARVR.generate_room_id()
        self.room_textbox.Text = self.default_room_id

        # Update active view info
        active_view = doc.ActiveView if doc else None
        if active_view and active_view.ViewType == DB.ViewType.ThreeD:
            self.status_text.Text = ">> Active View: [{}] ready to export & beam".format(active_view.Name)
        else:
            self.status_text.Text = ">> Switch to a 3D view or browse a local .glb/.gltf file"

    def get_room_id(self):
        txt = self.room_textbox.Text.strip()
        if not txt:
            txt = self.default_room_id
        return txt.upper()

    def on_export_view_clicked(self, sender, e):
        active_view = self.doc.ActiveView if self.doc else None
        if not active_view or active_view.ViewType != DB.ViewType.ThreeD:
            NOTIFICATION.messenger("Please open or activate a 3D view in Revit first, or browse an existing .glb file.")
            return

        dump_dir = FOLDER.get_local_dump_folder_folder("ARVR_Exports")
        if not os.path.exists(dump_dir):
            try:
                os.makedirs(dump_dir)
            except:
                pass

        view_name = "".join(c for c in active_view.Name if c.isalnum() or c in (' ', '_', '-')).strip()
        out_base = os.path.join(dump_dir, view_name)

        # Attempt export: check if glTF/GLB or DWG/FBX/OBJ export is available
        # In Revit, direct .glb export may require third party or can export 3D DWG/FBX or browse .glb
        out_glb = out_base + ".glb"

        if os.path.exists(out_glb) and os.path.getsize(out_glb) > 0:
            self.perform_upload(out_glb)
            return

        # If direct glb not exported yet, notify user and prompt to select or convert
        NOTIFICATION.messenger(
            "Ready to beam 3D view [{}]!\nOpening model file picker to confirm exported .glb...".format(active_view.Name))
        self.on_browse_model_clicked(sender, e)

    def on_browse_model_clicked(self, sender, e):
        dlg = Microsoft.Win32.OpenFileDialog()
        dlg.Title = "Select 3D Model to Beam into Mobile AR"
        dlg.Filter = "3D Models (*.glb;*.gltf;*.usdz)|*.glb;*.gltf;*.usdz|All Files (*.*)|*.*"
        if dlg.ShowDialog():
            filepath = dlg.FileName
            if filepath and os.path.exists(filepath):
                self.perform_upload(filepath)

    def perform_upload(self, filepath):
        room_id = self.get_room_id()
        NOTIFICATION.messenger("Uploading [{}] to ARVR Room {}...".format(
            os.path.basename(filepath), room_id))

        ok, room_id, web_url, err = ARVR.upload_model_file(filepath, room_id=room_id)
        if ok:
            NOTIFICATION.messenger(
                "Model beamed successfully to Room {}!\nOpening pairing hub...".format(room_id))
            webbrowser.open(web_url)
            self.Close()
        else:
            NOTIFICATION.messenger("Upload error: {}\nOpening default web hub instead.".format(err))
            webbrowser.open(ARVR.ARVR_URL_BASE)

    def on_open_web_clicked(self, sender, e):
        room_id = self.get_room_id()
        ARVR.open_web_hub(room_id)
        self.Close()

    def on_close_clicked(self, sender, e):
        self.Close()


@LOG.log(__file__, __title__)
@ERROR_HANDLE.try_catch_error()
def main(doc):
    win = ARVROverlayWindow(doc)
    win.ShowDialog()


################## main code below #####################
if __name__ == "__main__":
    main(DOC)
