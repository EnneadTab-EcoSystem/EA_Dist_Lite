# -*- coding: utf-8 -*-
__title__ = "ARVROverlay"
__doc__ = """EnneadTab-ARVR: Zero-Install Mobile Camera AR Overlay for 3D Models.

Beam your 3D models onto your smartphone camera in augmented reality:
- Pick objects in the viewport right from this dialog if nothing is preselected
- Export selected Rhino objects to .GLB
- Stage model in local temp folder
- Direct upload to cloud room session
- Shows the phone-ready QR code and link right here, no browser hop needed
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
        self.dialog.Height = 660

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
        self.status_lbl.Font = Eto.Drawing.Font("Consolas", 9)
        status_layout.AddRow(self.status_lbl)
        self._refresh_selection_status()

        # Pick objects directly from this dialog when nothing is preselected,
        # instead of forcing a Cancel-reselect-reopen round trip.
        self.btn_pick = Eto.Forms.Button()
        self.btn_pick.Text = "PICK OBJECTS IN VIEWPORT"
        self.btn_pick.Font = Eto.Drawing.Font("Arial", 8)
        self.btn_pick.BackgroundColor = self.col_bg
        self.btn_pick.TextColor = self.col_green
        self.btn_pick.Height = 26
        self.btn_pick.Click += self.on_pick_click
        status_layout.AddRow(self.btn_pick)

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

        # Share Link / inline QR -- populated after a successful send so the
        # phone can scan right here, instead of the user hopping to the web
        # hub in a browser just to find the QR code shown there.
        result_box = Eto.Forms.GroupBox()
        result_box.Text = "Share Link"
        result_box.TextColor = self.col_green
        result_box.BackgroundColor = self.col_panel
        result_box.Padding = Eto.Drawing.Padding(10)

        result_layout = Eto.Forms.DynamicLayout()
        result_layout.Spacing = Eto.Drawing.Size(6, 6)

        self.qr_view = Eto.Forms.ImageView()
        self.qr_view.Size = Eto.Drawing.Size(150, 150)
        result_layout.AddRow(None, self.qr_view, None)

        self.link_tb = Eto.Forms.TextBox()
        self.link_tb.ReadOnly = True
        self.link_tb.PlaceholderText = "Send or browse a model above to get a phone-ready link"
        self.link_tb.TextColor = self.col_cyan
        self.link_tb.BackgroundColor = self.col_bg
        result_layout.AddRow(self.link_tb)

        result_box.Content = result_layout
        layout.AddRow(result_box)

        # Footer close button (same full-width treatment as the buttons above,
        # so the button block presents one consistent left/right edge)
        btn_close = Eto.Forms.Button()
        btn_close.Text = "CLOSE"
        btn_close.Font = Eto.Drawing.Font("Arial", 9)
        btn_close.BackgroundColor = self.col_bg
        btn_close.TextColor = self.col_dim
        btn_close.Height = 32
        btn_close.Click += lambda s, e: self.dialog.Close(False)
        layout.AddRow(btn_close)

        self.dialog.Content = layout

    def show(self):
        return self.dialog.ShowModal(Rhino.UI.RhinoEtoApp.MainWindow)

    def _refresh_selection_status(self):
        sel_count = len(self.sel_objs) if self.sel_objs else 0
        if sel_count > 0:
            self.status_lbl.Text = ">> {} object(s) selected ready to export".format(sel_count)
            self.status_lbl.TextColor = self.col_green
        else:
            self.status_lbl.Text = ">> No objects selected (use Pick below, or Browse a local file)"
            self.status_lbl.TextColor = self.col_yellow

    def on_pick_click(self, sender, e):
        # Hide the modal dialog so the Rhino viewport can accept clicks;
        # ShowModal's nested message loop keeps pumping underneath, so
        # re-showing after GetObjects() returns resumes right where we left off.
        self.dialog.Visible = False
        try:
            objs = rs.GetObjects("Select objects to beam to AR/VR", preselect=False, select=True)
        finally:
            self.dialog.Visible = True

        self.sel_objs = objs if objs else []
        self._refresh_selection_status()

    def _handle_upload_result(self, ok, room_id, url, err):
        if not ok:
            self.status_lbl.Text = ">> Upload failed: {}".format(err or "unknown error")
            self.status_lbl.TextColor = self.col_magenta
            return

        self.status_lbl.Text = ">> Beamed to Room {} - scan the QR below on your phone".format(room_id)
        self.status_lbl.TextColor = self.col_green
        self.link_tb.Text = url

        qr_path = ARVR.download_qr_code(url)
        if qr_path:
            try:
                self.qr_view.Image = Eto.Drawing.Bitmap(qr_path)
            except Exception:
                pass

    def on_export_click(self, sender, e):
        objs = rs.SelectedObjects()
        if not objs:
            rs.Command("-_SelAll ")
            objs = rs.SelectedObjects()
            if not objs:
                NOTIFICATION.messenger("No objects found to export. Please select objects in Rhino first, or use Pick Objects above.")
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
        ok, room_id, url, err = ARVR.stage_and_upload(out_path, room_id=room_input, auto_open_browser=False)
        self._handle_upload_result(ok, room_id, url, err)

    def on_browse_click(self, sender, e):
        filter_str = "3D Models (*.glb;*.gltf;*.usdz)|*.glb;*.gltf;*.usdz|All Files (*.*)|*.*"
        filepath = rs.OpenFileName("Select 3D Model to Beam to AR/VR", filter_str)
        if not filepath or not os.path.exists(filepath):
            return

        room_input = self.room_tb.Text.strip() if self.room_tb.Text else None
        ok, room_id, url, err = ARVR.stage_and_upload(filepath, room_id=room_input, auto_open_browser=False)
        self._handle_upload_result(ok, room_id, url, err)

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
