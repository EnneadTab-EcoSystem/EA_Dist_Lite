# -*- coding: utf-8 -*-
__title__ = "ARVROverlay"
__doc__ = """EnneadTab-ARVR: Zero-Install Mobile Camera AR Overlay for 3D Models.

Beam your 3D models onto your smartphone camera in augmented reality:
- Export selected Rhino objects to .GLB
- Direct upload to active cloud room session
- Pick existing local .GLB / .GLTF / .USDZ file to beam
- Instant mobile camera AR pairing via QR code
- Launch Web Hub (https://enneadtab.com/arvr)
"""

__is_popular__ = True

import os
import webbrowser

try:
    import Rhino # pyright: ignore
    import rhinoscriptsyntax as rs # pyright: ignore
    import scriptcontext as sc # pyright: ignore
    import Eto # pyright: ignore
except:
    pass

from EnneadTab import ERROR_HANDLE, LOG, NOTIFICATION, FOLDER, ARVR
from EnneadTab.RHINO import RHINO_UI

class ARVRExportDialog(object):
    """Arcade-styled dialog for Rhino ARVR Export & Web Beaming."""

    def __init__(self):
        self.dialog = Eto.Forms.Dialog[bool]()
        self.dialog.Title = "EnneadTab-ARVR :: Mobile AR Overlay Hub"
        self.dialog.Resizable = False
        self.dialog.Padding = Eto.Drawing.Padding(16)
        self.dialog.Width = 480
        self.dialog.Height = 440

        # Colors
        self.col_bg = RHINO_UI.hex_to_eto_color("#0A0E1A")
        self.col_panel = RHINO_UI.hex_to_eto_color("#121829")
        self.col_cyan = RHINO_UI.hex_to_eto_color("#00F0FF")
        self.col_magenta = RHINO_UI.hex_to_eto_color("#FF007F")
        self.col_yellow = RHINO_UI.hex_to_eto_color("#FFE600")
        self.col_green = RHINO_UI.hex_to_eto_color("#00FF66")
        self.col_white = RHINO_UI.hex_to_eto_color("#FFFFFF")
        self.col_dim = RHINO_UI.hex_to_eto_color("#8A99AD")

        self.dialog.BackgroundColor = self.col_bg

        layout = Eto.Forms.DynamicLayout()
        layout.Padding = Eto.Drawing.Padding(10)
        layout.Spacing = Eto.Drawing.Size(8, 8)

        # Header Title
        title_lbl = Eto.Forms.Label()
        title_lbl.Text = "[ AR/VR SPATIAL OVERLAY ]"
        title_lbl.Font = Eto.Drawing.Font("Consolas", 14, Eto.Drawing.FontStyle.Bold)
        title_lbl.TextColor = self.col_cyan
        title_lbl.TextAlignment = Eto.Forms.TextAlignment.Center
        layout.AddRow(title_lbl)

        # Subtitle
        sub_lbl = Eto.Forms.Label()
        sub_lbl.Text = "Zero-install mobile camera AR beam for Rhino 3D models"
        sub_lbl.Font = Eto.Drawing.Font("Arial", 9)
        sub_lbl.TextColor = self.col_dim
        sub_lbl.TextAlignment = Eto.Forms.TextAlignment.Center
        layout.AddRow(sub_lbl)
        layout.AddSeparateRow()

        # Selection Status
        self.sel_objs = rs.SelectedObjects() if 'rs' in globals() else []
        sel_count = len(self.sel_objs) if self.sel_objs else 0

        status_box = Eto.Forms.GroupBox()
        status_box.Text = "Selection Status"
        status_box.TextColor = self.col_yellow
        status_box.BackgroundColor = self.col_panel
        status_box.Padding = Eto.Drawing.Padding(10)

        status_layout = Eto.Forms.DynamicLayout()
        status_layout.Spacing = Eto.Drawing.Size(6, 6)

        self.status_lbl = Eto.Forms.Label()
        if sel_count > 0:
            self.status_lbl.Text = ">> {} object(s) selected ready to export".format(sel_count)
            self.status_lbl.TextColor = self.col_green
        else:
            self.status_lbl.Text = ">> No objects selected (Select objects first or browse .glb)"
            self.status_lbl.TextColor = self.col_yellow
        self.status_lbl.Font = Eto.Drawing.Font("Consolas", 9)
        status_layout.AddRow(self.status_lbl)

        # Room ID input
        room_row = Eto.Forms.DynamicLayout()
        room_row.Spacing = Eto.Drawing.Size(6, 6)
        r_lbl = Eto.Forms.Label()
        r_lbl.Text = "Room Code (Optional):"
        r_lbl.TextColor = self.col_dim
        r_lbl.Font = Eto.Drawing.Font("Arial", 9)
        self.room_tb = Eto.Forms.TextBox()
        self.room_tb.PlaceholderText = "Auto-generated (or enter 6-char code)"
        self.room_tb.BackgroundColor = self.col_bg
        self.room_tb.TextColor = self.col_cyan
        self.room_tb.Width = 240
        room_row.AddRow(r_lbl, self.room_tb)
        status_layout.AddRow(room_row)

        status_box.Content = status_layout
        layout.AddRow(status_box)
        layout.AddSeparateRow()

        # Action Buttons
        self.btn_export = Eto.Forms.Button()
        self.btn_export.Text = "⚡ EXPORT SELECTED & BEAM TO MOBILE AR"
        self.btn_export.Font = Eto.Drawing.Font("Arial", 10, Eto.Drawing.FontStyle.Bold)
        self.btn_export.BackgroundColor = self.col_magenta
        self.btn_export.TextColor = self.col_white
        self.btn_export.Height = 36
        self.btn_export.Click += self.on_export_click
        layout.AddRow(self.btn_export)

        self.btn_browse = Eto.Forms.Button()
        self.btn_browse.Text = "📁 BROWSE LOCAL 3D MODEL (.GLB/.GLTF/.USDZ) & BEAM"
        self.btn_browse.Font = Eto.Drawing.Font("Arial", 9)
        self.btn_browse.BackgroundColor = self.col_panel
        self.btn_browse.TextColor = self.col_cyan
        self.btn_browse.Height = 32
        self.btn_browse.Click += self.on_browse_click
        layout.AddRow(self.btn_browse)

        self.btn_web = Eto.Forms.Button()
        self.btn_web.Text = "🌐 OPEN AR/VR WEB HUB (BROWSER)"
        self.btn_web.Font = Eto.Drawing.Font("Arial", 9)
        self.btn_web.BackgroundColor = self.col_panel
        self.btn_web.TextColor = self.col_yellow
        self.btn_web.Height = 32
        self.btn_web.Click += self.on_web_click
        layout.AddRow(self.btn_web)

        # Footer close button
        btn_close = Eto.Forms.Button()
        btn_close.Text = "CLOSE"
        btn_close.Font = Eto.Drawing.Font("Arial", 9)
        btn_close.BackgroundColor = self.col_bg
        btn_close.TextColor = self.col_dim
        btn_close.Click += lambda s, e: self.dialog.Close(False)
        layout.AddRow(None, btn_close)

        self.dialog.Content = layout

    def show(self):
        return self.dialog.ShowModal(Rhino.UI.RhinoEtoApp.MainWindow)

    def on_export_click(self, sender, e):
        objs = rs.SelectedObjects()
        if not objs:
            rs.Command("-_SelAll ")
            objs = rs.SelectedObjects()
            if not objs:
                NOTIFICATION.messenger("No objects found to export. Please select objects in Rhino first.")
                return

        # Prepare export target path
        doc_name = rs.DocumentName()
        if doc_name:
            clean_name = os.path.splitext(doc_name)[0]
        else:
            clean_name = "Rhino_Model"

        dump_dir = FOLDER.get_local_dump_folder_folder("ARVR_Exports")
        if not os.path.exists(dump_dir):
            try:
                os.makedirs(dump_dir)
            except:
                pass

        out_path = os.path.join(dump_dir, clean_name + ".glb")
        
        # Try export using Rhino 8 GLB export or fallback to OBJ
        cmd = '-_Export "{}" _Enter _Enter'.format(out_path.replace("\\", "/"))
        rs.Command(cmd, echo=False)

        if not os.path.exists(out_path) or os.path.getsize(out_path) == 0:
            # Try with obj if glb direct native export was not recognized
            out_obj = os.path.join(dump_dir, clean_name + ".obj")
            cmd_obj = '-_Export "{}" _Enter _Enter'.format(out_obj.replace("\\", "/"))
            rs.Command(cmd_obj, echo=False)
            if os.path.exists(out_obj) and os.path.getsize(out_obj) > 0:
                out_path = out_obj

        if not os.path.exists(out_path) or os.path.getsize(out_path) == 0:
            NOTIFICATION.messenger("Could not export geometry. Please check Rhino export formats or use Browse.")
            return

        self.perform_upload(out_path)

    def on_browse_click(self, sender, e):
        filter_str = "3D Models (*.glb;*.gltf;*.usdz)|*.glb;*.gltf;*.usdz|All Files (*.*)|*.*"
        filepath = rs.OpenFileName("Select 3D Model to Beam to AR/VR", filter_str)
        if not filepath or not os.path.exists(filepath):
            return
        self.perform_upload(filepath)

    def perform_upload(self, filepath):
        room_input = self.room_tb.Text.strip() if self.room_tb.Text else None
        if not room_input:
            room_input = ARVR.generate_room_id()

        NOTIFICATION.messenger("Uploading 3D model to ARVR room {}...".format(room_input))

        ok, room_id, web_url, err = ARVR.upload_model_file(filepath, room_id=room_input)
        if ok:
            NOTIFICATION.messenger(
                "3D Model beamed successfully to Room {}!\nOpening pairing hub...".format(room_id))
            webbrowser.open(web_url)
            self.dialog.Close(True)
        else:
            NOTIFICATION.messenger("Upload error: {}\nOpening default web hub instead.".format(err))
            webbrowser.open(ARVR.ARVR_URL_BASE)

    def on_web_click(self, sender, e):
        room_input = self.room_tb.Text.strip() if self.room_tb.Text else None
        ARVR.open_web_hub(room_input)
        self.dialog.Close(True)

@LOG.log(__file__, __title__)
@ERROR_HANDLE.try_catch_error()
def arvr_overlay():
    dlg = ARVRExportDialog()
    dlg.show()

if __name__ == "__main__":
    arvr_overlay()
