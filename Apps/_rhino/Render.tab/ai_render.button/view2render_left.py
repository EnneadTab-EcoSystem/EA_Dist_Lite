# -*- coding: utf-8 -*-
__title__ = "AiRenderingFromView"
__doc__ = """Renders Rhino views using Gemini AI via EnneaDuck.

Captures current viewport, sends it with a style prompt to ennead-ai.com,
and returns a polished architectural rendering. No local GPU required.
"""

import time
import os

import Rhino # pyright: ignore
import scriptcontext as sc
import Eto # pyright: ignore
import System # pyright: ignore

from EnneadTab import NOTIFICATION, FOLDER, SOUND, IMAGE
from EnneadTab import LOG, ERROR_HANDLE, AUTH, AI
from EnneadTab.RHINO import RHINO_UI


STYLE_PRESETS = {
    "Professional Exterior": "Professional architecture exterior rendering, warm natural lighting, high quality, detailed materials, landscape context, award-winning architectural photography style",
    "Professional Interior": "Professional architecture interior rendering, natural light streaming through windows, warm atmosphere, detailed furniture and materials, high quality",
    "Dramatic Dusk": "Dramatic dusk lighting, golden hour, architecture rendering, moody atmosphere, city lights beginning to glow, high contrast, cinematic",
    "Watercolor Sketch": "Architectural watercolor sketch, hand-drawn feel, soft washes of color, loose lines, artistic interpretation, white paper background",
    "Diagram / Axonometric": "Clean architectural diagram, white background, minimal shadows, flat colors, technical illustration style, clear and readable",
    "Photorealistic": "Photorealistic architecture rendering, 8K quality, ray-traced lighting, physically accurate materials, ultra detailed, professional photography",
    "Aerial Perspective": "Aerial view architectural rendering, bird's eye perspective, masterplan visualization, landscape integration, professional urban design rendering",
    "Black & White": "Black and white architectural rendering, high contrast, dramatic shadows, monochrome, fine art photography style, stark and elegant",
}


class ViewCaptureDialog(Eto.Forms.Form):

    def __init__(self):
        self.Title = "EnneaDuck: AI View Render"
        self.Padding = Eto.Drawing.Padding(10)

        layout = Eto.Forms.DynamicLayout()
        layout.Padding = Eto.Drawing.Padding(10)
        layout.Spacing = Eto.Drawing.Size(5, 5)

        # Logo
        logo_view = Eto.Forms.ImageView()
        logo_path = IMAGE.get_image_path_by_name("logo_vertical_light.png")
        if logo_path and os.path.exists(logo_path):
            bmp = Eto.Drawing.Bitmap(logo_path)
            logo_view.Image = bmp.WithSize(200, 30)
        layout.AddSeparateRow(None, logo_view)

        # Preview
        self.m_label = Eto.Forms.Label(Text="Capture your view below:")
        layout.AddRow(self.m_label)
        self.m_image_view = Eto.Forms.ImageView()
        self.preview_w, self.preview_h = 500, 350
        self.m_image_view.Size = Eto.Drawing.Size(self.preview_w, self.preview_h)
        layout.AddRow(self.m_image_view)

        # Style preset dropdown
        layout.AddRow(Eto.Forms.Label(Text="\nRendering Style:"))
        self.cb_style = Eto.Forms.ComboBox()
        self.cb_style.DataStore = list(STYLE_PRESETS.keys())
        self.cb_style.SelectedIndex = 0
        self.cb_style.SelectedIndexChanged += self.on_style_changed
        layout.AddRow(self.cb_style)

        # Custom prompt
        layout.AddRow(Eto.Forms.Label(Text="\nPrompt (edit or write your own):"))
        self.tbox_prompt = Eto.Forms.TextArea()
        self.tbox_prompt.Size = Eto.Drawing.Size(500, 80)
        self.tbox_prompt.Text = list(STYLE_PRESETS.values())[0]
        layout.AddRow(self.tbox_prompt)

        # Buttons
        bt_capture = Eto.Forms.Button(Text="Update Capture")
        bt_capture.Click += self.on_capture
        bt_render = Eto.Forms.Button(Text="Send to AI")
        bt_render.Click += self.on_render
        bt_close = Eto.Forms.Button(Text="Close")
        bt_close.Click += self.on_close
        bt_open_folder = Eto.Forms.Button(Text="Open Output Folder")
        bt_open_folder.Click += self.on_open_folder

        btn_layout = Eto.Forms.DynamicLayout()
        btn_layout.AddSeparateRow(bt_capture, None, bt_render, bt_close)
        btn_layout.AddSeparateRow(None, bt_open_folder)
        layout.AddRow(btn_layout)

        # Status
        self.status_label = Eto.Forms.Label(Text="Ready.")
        layout.AddRow(self.status_label)

        self.Content = layout
        self.capture_view()

        RHINO_UI.apply_dark_style(self)
        self.Closed += self.on_form_closed

    def on_style_changed(self, sender, e):
        key = self.cb_style.DataStore[self.cb_style.SelectedIndex]
        self.tbox_prompt.Text = STYLE_PRESETS.get(key, "")

    def on_form_closed(self, sender, e):
        if sc.sticky.has_key("EA_AI_RENDER_CAPTURE_FORM"):
            sc.sticky.Remove("EA_AI_RENDER_CAPTURE_FORM")

    def capture_view(self):
        view = sc.doc.Views.ActiveView
        original_size = view.Size
        view.Size = System.Drawing.Size(self.preview_w, self.preview_h)
        self.m_image_view.Image = Rhino.UI.EtoExtensions.ToEto(view.CaptureToBitmap())
        self.m_image_view.Size = Eto.Drawing.Size(self.preview_w, self.preview_h)
        view.Size = original_size
        self.m_label.Text = "Captured: {}".format(view.ActiveViewport.Name)

    def on_capture(self, sender, e):
        self.capture_view()

    @ERROR_HANDLE.try_catch_error()
    def on_render(self, sender, e):
        # Save viewport to file
        session = time.strftime("%Y%m%d-%H%M%S")
        session_folder = os.path.join(FOLDER.DUMP_FOLDER, "EnneadTab_Ai_Rendering", "Session_{}".format(session))
        if not os.path.exists(session_folder):
            os.makedirs(session_folder)
        input_path = os.path.join(session_folder, "Original.jpeg")

        view = sc.doc.Views.ActiveView
        view_capture = Rhino.Display.ViewCapture()
        view_capture.Width = self.preview_w
        view_capture.Height = self.preview_h
        view_capture.ScaleScreenItems = False
        view_capture.DrawAxes = False
        view_capture.DrawGrid = False
        view_capture.DrawGridAxes = False
        view_capture.TransparentBackground = False
        bitmap = view_capture.CaptureToBitmap(view)
        bitmap.Save(input_path, System.Drawing.Imaging.ImageFormat.Jpeg)

        # Auth
        self.status_label.Text = "Authenticating..."
        token = AUTH.get_token()
        if not token:
            if not AUTH.is_auth_in_progress():
                AUTH.request_auth()
            max_wait = 120
            elapsed = 0
            while elapsed < max_wait:
                self.status_label.Text = "Waiting for browser sign-in... {}s/{}s".format(elapsed, max_wait)
                time.sleep(1)
                elapsed += 1
                token = AUTH.get_token()
                if token:
                    break
            if not token:
                self.status_label.Text = "Sign-in timed out."
                return

        # Send to AI
        prompt = self.tbox_prompt.Text

        def update_status(msg):
            self.status_label.Text = msg

        update_status("Uploading to AI...")

        try:
            images = AI.render_image_with_token(token, input_path, prompt, progress_callback=update_status)
        except AI.AIRequestError as e:
            if e.status_code == 401:
                AUTH.clear_token()
                self.status_label.Text = "Token expired. Please try again."
                return
            self.status_label.Text = "Render failed: {}".format(str(e)[:200])
            return

        if not images:
            self.status_label.Text = "No images returned. Try a different prompt."
            return

        # Save results
        import base64
        saved = []
        for i, img in enumerate(images):
            b64 = img.get("b64", "")
            mime = img.get("mime", "image/png")
            ext = ".png" if "png" in mime else ".jpeg"
            out_path = os.path.join(session_folder, "Result_{}{}".format(i + 1, ext))
            with open(out_path, "wb") as f:
                f.write(base64.b64decode(b64))
            saved.append(out_path)

        SOUND.play_sound("sound_effect_popup_msg3.wav")
        self.status_label.Text = "Done! {} image(s) saved to {}".format(len(saved), session_folder)

        # Open the first result
        if saved:
            os.startfile(saved[0])

    def on_open_folder(self, sender, e):
        folder = os.path.join(FOLDER.DUMP_FOLDER, "EnneadTab_Ai_Rendering")
        if os.path.exists(folder):
            os.startfile(folder)
        else:
            self.status_label.Text = "No output folder yet."

    def on_close(self, sender, e):
        self.Close()

    def Close(self):
        if sc.sticky.has_key("EA_AI_RENDER_CAPTURE_FORM"):
            form = sc.sticky["EA_AI_RENDER_CAPTURE_FORM"]
            if form:
                form.Dispose()
            sc.sticky.Remove("EA_AI_RENDER_CAPTURE_FORM")


@LOG.log(__file__, __title__)
@ERROR_HANDLE.try_catch_error()
def view2render():
    if sc.sticky.has_key("EA_AI_RENDER_CAPTURE_FORM"):
        return

    form = ViewCaptureDialog()
    form.Owner = Rhino.UI.RhinoEtoApp.MainWindow
    form.Show()
    sc.sticky["EA_AI_RENDER_CAPTURE_FORM"] = form


if __name__ == "__main__":
    view2render()
