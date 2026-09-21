# -*- coding: utf-8 -*-
__title__ = "ARVROverlay"
__doc__ = """EnneadTab-ARVR: Zero-Install Mobile Camera AR Overlay for 3D Models.

Beam your 3D models onto your smartphone camera in augmented reality:
- Export selected Rhino objects to .GLB
- Stage model in local temp folder
- Direct upload to cloud room session
- Pick existing local .GLB / .GLTF / .USDZ file to beam
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
    """Arcade-styled dialog for Rhino ARVR Export, Staging & Web Beaming."""

    def __init__(self):
        self.dialog = Eto.Forms.Dialog[bool]()
        self.dialog.Title = "EnneadTab-ARVR :: Mobile AR Overlay Hub"
        self.dialog.Resizable = False
        self.dialog.Padding = Eto.Drawing.Padding(16)
        self.dialog.Width = 560
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
        title_lbl.Text = "View Model in AR / VR"
        title_lbl.Font = Eto.Drawing.Font("Consolas", 14, Eto.Drawing.FontStyle.Bold)
        title_lbl.TextColor = self.col_cyan
        title_lbl.TextAlignment = Eto.Forms.TextAlignment.Center
        layout.AddRow(title_lbl)

        # Subtitle
        sub_lbl = Eto.Forms.Label()
        sub_lbl.Text = "Send your Rhino model to your phone - no app install needed"
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
            self.status_lbl.Text = ">> No objects selected (select objects first, or use Browse below)"
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
        self.room_tb.Width = 320
        room_row.AddRow(r_lbl, self.room_tb)
        status_layout.AddRow(room_row)

        status_box.Content = status_layout
        layout.AddRow(status_box)
        layout.AddSeparateRow()

        # Action Buttons
        self.btn_export = Eto.Forms.Button()
        self.btn_export.Text = "SEND SELECTED OBJECTS TO YOUR PHONE"
        self.btn_export.Font = Eto.Drawing.Font("Arial", 10, Eto.Drawing.FontStyle.Bold)
        self.btn_export.BackgroundColor = self.col_magenta
        self.btn_export.TextColor = self.col_white
        self.btn_export.Height = 36
        self.btn_export.Click += self.on_export_click
        layout.AddRow(self.btn_export)

        self.btn_browse = Eto.Forms.Button()
        self.btn_browse.Text = "BROWSE LOCAL MODEL (.GLB/.GLTF/.USDZ) && BEAM"
        self.btn_browse.Font = Eto.Drawing.Font("Arial", 9)
        self.btn_browse.BackgroundColor = self.col_panel
        self.btn_browse.TextColor = self.col_cyan
        self.btn_browse.Height = 32
        self.btn_browse.Click += self.on_browse_click
        layout.AddRow(self.btn_browse)

        self.btn_web = Eto.Forms.Button()
        self.btn_web.Text = "OPEN AR/VR WEB HUB (BROWSER)"
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

        # Prepare export target path in staging folder
        doc_name = rs.DocumentName()
        if doc_name:
            clean_name = os.path.splitext(doc_name)[0]
        else:
            clean_name = "Rhino_Model"

        staging_dir = ARVR.get_staging_directory()
        out_path = os.path.join(staging_dir, clean_name + ".glb")

        # Delete any leftover file from a previous run first. Without this, a
        # failed export here would silently re-upload a stale .glb from an
        # earlier successful export instead of reporting failure.
        if os.path.exists(out_path):
            try:
                os.remove(out_path)
            except Exception:
                pass

        # Use RhinoDoc.ExportSelected directly (same proven pattern as
        # File.tab/external_trimmer.button) instead of scripting -_Export
        # with blind _Enter presses -- that macro approach has no way to
        # know how many dialogs a given selection will trigger.
        rs.SelectObjects(objs)
        try:
            exported = sc.doc.ExportSelected(out_path)
        except Exception as export_err:
            exported = False
            NOTIFICATION.messenger("Export raised an error: {}".format(export_err))

        if not exported or not os.path.exists(out_path) or os.path.getsize(out_path) == 0:
            NOTIFICATION.messenger("Could not export geometry to .GLB. Please check Rhino export formats or use Browse.")
            return

        room_input = self.room_tb.Text.strip() if self.room_tb.Text else None
        ok, room_id, url, err = ARVR.stage_and_upload(out_path, room_id=room_input, auto_open_browser=True)
        if ok:
            self.dialog.Close(True)

    def on_browse_click(self, sender, e):
        filter_str = "3D Models (*.glb;*.gltf;*.usdz)|*.glb;*.gltf;*.usdz|All Files (*.*)|*.*"
        filepath = rs.OpenFileName("Select 3D Model to Beam to AR/VR", filter_str)
        if not filepath or not os.path.exists(filepath):
            return

        room_input = self.room_tb.Text.strip() if self.room_tb.Text else None
        ok, room_id, url, err = ARVR.stage_and_upload(filepath, room_id=room_input, auto_open_browser=True)
        if ok:
            self.dialog.Close(True)

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
