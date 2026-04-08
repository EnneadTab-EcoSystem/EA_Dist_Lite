#!/usr/bin/python
# -*- coding: utf-8 -*-

__doc__ = "AI-powered view rendering. Captures the current Revit view and transforms it into a polished architectural rendering using EnneaDuck AI (Gemini). Select a style preset or write your own prompt."
__title__ = "AI\nRender"

import System # pyright: ignore
import os
import time
import random
import base64

from pyrevit import script
from pyrevit.forms import WPFWindow # pyright: ignore

from System.Net import WebRequest, ServicePointManager, SecurityProtocolType # pyright: ignore
from System.IO import StreamReader # pyright: ignore
from System.Text import Encoding # pyright: ignore
from Autodesk.Revit import DB # pyright: ignore

import proDUCKtion # pyright: ignore
proDUCKtion.validify()
from EnneadTab.REVIT import REVIT_FORMS
from EnneadTab import ERROR_HANDLE, AUTH, AI, SOUND, IMAGE, LOG, JOKE, FOLDER

uidoc = __revit__.ActiveUIDocument
doc = __revit__.ActiveUIDocument.Document # pyright: ignore

STYLE_PRESETS = [
    ("Professional Exterior", "Professional architecture exterior rendering, warm natural lighting, high quality, detailed materials, landscape context, award-winning architectural photography style"),
    ("Professional Interior", "Professional architecture interior rendering, natural light streaming through windows, warm atmosphere, detailed furniture and materials, high quality"),
    ("Dramatic Dusk", "Dramatic dusk lighting, golden hour, architecture rendering, moody atmosphere, city lights beginning to glow, high contrast, cinematic"),
    ("Watercolor Sketch", "Architectural watercolor sketch, hand-drawn feel, soft washes of color, loose lines, artistic interpretation, white paper background"),
    ("Diagram / Axonometric", "Clean architectural diagram, white background, minimal shadows, flat colors, technical illustration style, clear and readable"),
    ("Photorealistic", "Photorealistic architecture rendering, 8K quality, ray-traced lighting, physically accurate materials, ultra detailed, professional photography"),
    ("Black & White", "Black and white architectural rendering, high contrast, dramatic shadows, monochrome, fine art photography style"),
]


class AiRenderForm(WPFWindow):

    @ERROR_HANDLE.try_catch_error()
    def __init__(self):
        xaml_file_name = "AiRenderForm.xaml"
        WPFWindow.__init__(self, xaml_file_name)

        self.Title = "EnneaDuck: AI View Render"
        self.title_text.Text = "EnneaDuck: AI View Render"
        self.sub_text.Text = "Capture your current view and transform it into a polished rendering with AI."

        logo_file = IMAGE.get_image_path_by_name("logo_vertical_light.png")
        self.set_image_source(self.logo_img, logo_file)

        # Populate style presets
        for name, _ in STYLE_PRESETS:
            self.cb_style.Items.Add(name)
        self.cb_style.SelectedIndex = 0
        self.tbox_prompt.Text = STYLE_PRESETS[0][1]

        self.Height = 600
        self.debug_textbox.Text = "Ready. Click 'Send to AI' to render."
        self.Show()

    def style_changed(self, sender, e):
        idx = self.cb_style.SelectedIndex
        if 0 <= idx < len(STYLE_PRESETS):
            self.tbox_prompt.Text = STYLE_PRESETS[idx][1]

    def mouse_down_main_panel(self, sender, args):
        sender.DragMove()

    def close_Click(self, sender, args):
        self.Close()

    @ERROR_HANDLE.try_catch_error()
    def render_Click(self, sender, e):
        prompt = self.tbox_prompt.Text
        if not prompt or not prompt.strip():
            self.debug_textbox.Text = "Please enter a rendering prompt."
            return

        # Export current view to temporary JPEG
        self.debug_textbox.Text = "Exporting current view..."
        view = doc.ActiveView
        if view is None:
            self.debug_textbox.Text = "No active view."
            return

        session = time.strftime("%Y%m%d-%H%M%S")
        session_folder = os.path.join(FOLDER.DUMP_FOLDER, "EnneadTab_Ai_Rendering", "Session_{}".format(session))
        if not os.path.exists(session_folder):
            os.makedirs(session_folder)
        input_path = os.path.join(session_folder, "Original.jpeg")

        # Use Revit's ImageExportOptions to capture the view
        opts = DB.ImageExportOptions()
        opts.ExportRange = DB.ExportRange.CurrentView
        opts.FilePath = input_path
        opts.HLRandWFViewsFileType = DB.ImageFileType.JPEG
        opts.ShadowViewsFileType = DB.ImageFileType.JPEG
        opts.ImageResolution = DB.ImageResolution.DPI_300
        opts.ZoomType = DB.ZoomFitType.FitToPage
        opts.PixelSize = 1500

        doc.ExportImage(opts)

        # Revit appends view name to filename - find the actual file
        actual_file = None
        for f in os.listdir(session_folder):
            if f.lower().endswith((".jpg", ".jpeg")):
                actual_file = os.path.join(session_folder, f)
                break

        if not actual_file or not os.path.exists(actual_file):
            self.debug_textbox.Text = "Failed to export view image."
            return

        # Auth
        self.debug_textbox.Text = "Authenticating..."
        session_token = AUTH.get_token()
        if not session_token:
            if not AUTH.is_auth_in_progress():
                AUTH.request_auth()
            max_wait = 120
            elapsed = 0
            while elapsed < max_wait:
                self.debug_textbox.Text = "Waiting for browser sign-in... {}s/{}s".format(elapsed, max_wait)
                time.sleep(1)
                elapsed += 1
                session_token = AUTH.get_token()
                if session_token:
                    break
            if not session_token:
                self.debug_textbox.Text = "Sign-in timed out. Please try again."
                return

        # Send to AI
        self.debug_textbox.Text = JOKE.random_loading_message()

        try:
            images = AI.render_image_with_token(session_token, actual_file, prompt)
        except AI.AIRequestError as e:
            if e.status_code == 401:
                AUTH.clear_token()
                self.debug_textbox.Text = "Token expired. Please try again."
                return
            self.debug_textbox.Text = "Render failed: {}".format(str(e)[:200])
            return

        if not images:
            self.debug_textbox.Text = "No images returned. Try a different prompt."
            return

        # Save results
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
        self.debug_textbox.Text = "Done! {} image(s) saved.".format(len(saved))

        # Open the first result
        if saved:
            os.startfile(saved[0])


@LOG.log(__file__, __title__)
@ERROR_HANDLE.try_catch_error()
def main():
    output = script.get_output()
    output.close_others()
    AiRenderForm()


if __name__ == "__main__":
    main()
