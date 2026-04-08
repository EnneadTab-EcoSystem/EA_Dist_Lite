#!/usr/bin/python
# -*- coding: utf-8 -*-

__doc__ = "AI-powered view rendering. Captures the current Revit view and transforms it into a polished architectural rendering using EnneaDuck AI (Gemini). Select a style preset or write your own prompt."
__title__ = "AI\nRender"

import System # pyright: ignore
import os
import time
import base64
import shutil

from pyrevit import script
from pyrevit.forms import WPFWindow # pyright: ignore

from System.Threading import Thread, ThreadStart # pyright: ignore
from System.Windows import Visibility # pyright: ignore
from Autodesk.Revit import DB # pyright: ignore

import proDUCKtion # pyright: ignore
proDUCKtion.validify()
from EnneadTab.REVIT import REVIT_FORMS
from EnneadTab import ERROR_HANDLE, AUTH, AI, SOUND, IMAGE, LOG, FOLDER

uidoc = __revit__.ActiveUIDocument
doc = __revit__.ActiveUIDocument.Document # pyright: ignore

# Fallback presets when API is unreachable
LOCAL_PRESETS = [
    {"name": "Professional Exterior", "category": "Architectural Styles",
     "prompt": "Professional architecture exterior rendering, warm natural lighting, high quality, detailed materials, landscape context, award-winning architectural photography style"},
    {"name": "Professional Interior", "category": "Architectural Styles",
     "prompt": "Professional architecture interior rendering, natural light streaming through windows, warm atmosphere, detailed furniture and materials, high quality"},
    {"name": "Dramatic Dusk", "category": "Lighting",
     "prompt": "Dramatic dusk lighting, golden hour, architecture rendering, moody atmosphere, city lights beginning to glow, high contrast, cinematic"},
    {"name": "Watercolor Sketch", "category": "Graphic Style",
     "prompt": "Architectural watercolor sketch, hand-drawn feel, soft washes of color, loose lines, artistic interpretation, white paper background"},
    {"name": "Diagram / Axonometric", "category": "Graphic Style",
     "prompt": "Clean architectural diagram, white background, minimal shadows, flat colors, technical illustration style, clear and readable"},
    {"name": "Photorealistic", "category": "Architectural Styles",
     "prompt": "Photorealistic architecture rendering, 8K quality, ray-traced lighting, physically accurate materials, ultra detailed, professional photography"},
    {"name": "Black & White", "category": "Graphic Style",
     "prompt": "Black and white architectural rendering, high contrast, dramatic shadows, monochrome, fine art photography style"},
]

RELEVANT_CATEGORIES = [
    "Architectural Styles", "Graphic Style", "Lighting", "Weather",
    "Exteriors", "Interiors", "Materials & Textures",
]

# Prevent duplicate form instances
_active_form = [None]


def _load_presets():
    """Load presets from API or fall back to local."""
    try:
        token = AUTH.get_token()
        api_presets = AI.get_render_presets(token=token)
        if api_presets:
            filtered = [p for p in api_presets if p.get("category") in RELEVANT_CATEGORIES]
            if filtered:
                return filtered
    except Exception:
        pass
    return LOCAL_PRESETS


def _load_bmp_image(path):
    """Load a file path into a WPF BitmapImage."""
    from System.Windows.Media.Imaging import BitmapImage as WpfBitmapImage # pyright: ignore
    bmp = WpfBitmapImage()
    bmp.BeginInit()
    bmp.UriSource = System.Uri(os.path.abspath(path))
    bmp.CacheOption = System.Windows.Media.Imaging.BitmapCacheOption.OnLoad
    bmp.EndInit()
    return bmp


class AiRenderForm(WPFWindow):

    @ERROR_HANDLE.try_catch_error()
    def __init__(self):
        xaml_file_name = "AiRenderForm.xaml"
        WPFWindow.__init__(self, xaml_file_name)

        self.Title = "EnneaDuck: AI View Render"
        self.title_text.Text = "EnneaDuck: AI View Render"
        self.sub_text.Text = "Capture your current view and transform it into a polished rendering."

        logo_file = IMAGE.get_image_path_by_name("logo_vertical_light.png")
        self.set_image_source(self.logo_img, logo_file)

        # Load presets
        self._presets = _load_presets()
        self._categories = sorted(set(p.get("category", "Other") for p in self._presets))

        # Populate category dropdown
        self.cb_category.Items.Add("All")
        for cat in self._categories:
            self.cb_category.Items.Add(cat)
        self.cb_category.SelectedIndex = 0
        self._update_style_list()

        # State
        self._style_ref_path = None
        self._result_path = None
        self._original_preview = None  # BitmapImage of exported view
        self._result_preview = None    # BitmapImage of AI result
        self._showing_result = False
        self._rendering = False
        self._form_closed = False
        self._session_folder = None
        self._input_path = None
        self._render_prompt = None

        self.Height = 800
        self.debug_textbox.Text = "Ready. Click 'Send to EnneaDuck' to render."
        self.Closed += self._on_closed
        self.Show()

    def _on_closed(self, sender, e):
        self._form_closed = True
        _active_form[0] = None

    def _update_style_list(self):
        """Update style dropdown based on selected category."""
        self.cb_style.Items.Clear()
        cat_idx = self.cb_category.SelectedIndex
        cat = "All" if cat_idx <= 0 else self._categories[cat_idx - 1]
        if cat == "All":
            self._filtered_presets = list(self._presets)
        else:
            self._filtered_presets = [p for p in self._presets if p.get("category") == cat]
        for p in self._filtered_presets:
            self.cb_style.Items.Add(p.get("name", "?"))
        if self._filtered_presets:
            self.cb_style.SelectedIndex = 0
            self.tbox_prompt.Text = self._filtered_presets[0].get("prompt", "")

    def category_changed(self, sender, e):
        self._update_style_list()

    def style_changed(self, sender, e):
        idx = self.cb_style.SelectedIndex
        if 0 <= idx < len(self._filtered_presets):
            self.tbox_prompt.Text = self._filtered_presets[idx].get("prompt", "")

    def mouse_down_main_panel(self, sender, args):
        sender.DragMove()

    def close_Click(self, sender, args):
        self.Close()

    # --- Style reference ---

    @ERROR_HANDLE.try_catch_error()
    def browse_style_Click(self, sender, e):
        from Microsoft.Win32 import OpenFileDialog # pyright: ignore
        dlg = OpenFileDialog()
        dlg.Filter = "Images|*.png;*.jpg;*.jpeg"
        dlg.Title = "Select Style Reference Image"
        if dlg.ShowDialog():
            self._set_style_ref(dlg.FileName)

    @ERROR_HANDLE.try_catch_error()
    def paste_style_Click(self, sender, e):
        try:
            if System.Windows.Clipboard.ContainsImage():
                bmp_source = System.Windows.Clipboard.GetImage()
                temp_path = os.path.join(FOLDER.DUMP_FOLDER, "ai_render_style_ref.png")
                if not os.path.exists(FOLDER.DUMP_FOLDER):
                    os.makedirs(FOLDER.DUMP_FOLDER)
                from System.Windows.Media.Imaging import PngBitmapEncoder, BitmapFrame # pyright: ignore
                encoder = PngBitmapEncoder()
                encoder.Frames.Add(BitmapFrame.Create(bmp_source))
                stream = System.IO.FileStream(temp_path, System.IO.FileMode.Create)
                try:
                    encoder.Save(stream)
                finally:
                    stream.Close()
                self._set_style_ref(temp_path)
            else:
                self.debug_textbox.Text = "No image in clipboard."
        except Exception as ex:
            self.debug_textbox.Text = "Paste failed: {}".format(str(ex)[:150])

    def clear_style_Click(self, sender, e):
        self._style_ref_path = None
        self.style_preview.Source = None
        self.bt_clear_style.Visibility = Visibility.Collapsed
        self.debug_textbox.Text = "Style reference cleared."

    def _set_style_ref(self, path):
        self._style_ref_path = path
        self.set_image_source(self.style_preview, path)
        self.bt_clear_style.Visibility = Visibility.Visible
        self.debug_textbox.Text = "Style reference: {}".format(os.path.basename(path))

    # --- Result actions ---

    @ERROR_HANDLE.try_catch_error()
    def toggle_Click(self, sender, e):
        if self._showing_result and self._original_preview:
            self.result_preview.Source = self._original_preview
            self.preview_label.Text = "Original View:"
            self.bt_toggle.Content = "Show AI Result"
            self._showing_result = False
        elif self._result_preview:
            self.result_preview.Source = self._result_preview
            self.preview_label.Text = "AI Result:"
            self.bt_toggle.Content = "Show Original"
            self._showing_result = True

    @ERROR_HANDLE.try_catch_error()
    def copy_image_Click(self, sender, e):
        if not self._result_path or not os.path.exists(self._result_path):
            self.debug_textbox.Text = "No result image to copy."
            return
        try:
            bmp = _load_bmp_image(self._result_path)
            System.Windows.Clipboard.SetImage(bmp)
            self.debug_textbox.Text = "Copied to clipboard."
        except Exception as ex:
            self.debug_textbox.Text = "Copy failed: {}".format(str(ex)[:150])

    @ERROR_HANDLE.try_catch_error()
    def save_image_Click(self, sender, e):
        if not self._result_path or not os.path.exists(self._result_path):
            self.debug_textbox.Text = "No result image to save."
            return
        from Microsoft.Win32 import SaveFileDialog # pyright: ignore
        ext = os.path.splitext(self._result_path)[1]
        dlg = SaveFileDialog()
        dlg.Filter = "Image (*{})|*{}".format(ext, ext)
        dlg.FileName = "EnneaDuck_Render{}".format(ext)
        dlg.Title = "Save Rendered Image"
        if dlg.ShowDialog():
            shutil.copy2(self._result_path, dlg.FileName)
            self.debug_textbox.Text = "Saved to {}".format(dlg.FileName)

    # --- Capture ---

    @ERROR_HANDLE.try_catch_error()
    def capture_Click(self, sender, e):
        """Export current Revit view to JPEG and show in preview."""
        view = doc.ActiveView
        if view is None:
            self.debug_textbox.Text = "No active view."
            return

        session = time.strftime("%Y%m%d-%H%M%S")
        self._session_folder = os.path.join(
            FOLDER.DUMP_FOLDER, "EnneadTab_Ai_Rendering", "Session_{}".format(session))
        if not os.path.exists(self._session_folder):
            os.makedirs(self._session_folder)
        self._input_path = os.path.join(self._session_folder, "Original.jpeg")

        self.debug_textbox.Text = "Exporting view..."

        opts = DB.ImageExportOptions()
        opts.ExportRange = DB.ExportRange.CurrentView
        opts.FilePath = self._input_path
        opts.HLRandWFViewsFileType = DB.ImageFileType.JPEG
        opts.ShadowViewsFileType = DB.ImageFileType.JPEG
        opts.ImageResolution = DB.ImageResolution.DPI_300
        opts.ZoomType = DB.ZoomFitType.FitToPage
        opts.PixelSize = 1500
        doc.ExportImage(opts)

        # Revit appends view name to filename
        actual_file = None
        for f in os.listdir(self._session_folder):
            if f.lower().endswith((".jpg", ".jpeg")):
                actual_file = os.path.join(self._session_folder, f)
                break
        if not actual_file or not os.path.exists(actual_file):
            self.debug_textbox.Text = "Failed to export view image."
            return

        self._input_path = actual_file
        self._original_preview = _load_bmp_image(actual_file)
        self.result_preview.Source = self._original_preview
        self.preview_label.Text = "Captured: {}".format(view.Name)
        self.bt_render.IsEnabled = True
        self._result_preview = None
        self._showing_result = False
        self.result_buttons.Visibility = Visibility.Collapsed
        self.debug_textbox.Text = "View captured. Review it above, then click 'Send to EnneaDuck'."

    # --- Render ---

    @ERROR_HANDLE.try_catch_error()
    def render_Click(self, sender, e):
        if self._rendering:
            return
        if not self._input_path or not os.path.exists(self._input_path):
            self.debug_textbox.Text = "Please capture the view first."
            return
        prompt = self.tbox_prompt.Text
        if not prompt or not prompt.strip():
            self.debug_textbox.Text = "Please enter a rendering prompt."
            return

        self._render_prompt = prompt
        self._rendering = True
        self.bt_render.IsEnabled = False
        self.progress_bar.Visibility = Visibility.Visible
        self.debug_textbox.Text = "Starting..."

        # Run in background thread
        thread = Thread(ThreadStart(self._render_worker))
        thread.IsBackground = True
        thread.Start()

    def _invoke_ui(self, fn):
        """Run fn on Revit UI (WPF dispatcher) thread. Safe if form is closed."""
        if self._form_closed:
            return
        try:
            self.Dispatcher.Invoke(System.Action(fn))
        except Exception:
            pass

    def _render_worker(self):
        """Background: auth + API call."""
        try:
            self._invoke_ui(lambda: setattr(self.debug_textbox, 'Text', 'Authenticating...'))
            token = AUTH.get_token()
            if not token:
                if not AUTH.is_auth_in_progress():
                    AUTH.request_auth()
                max_wait = 120
                elapsed = 0
                while elapsed < max_wait and not self._form_closed:
                    self._invoke_ui(
                        lambda e=elapsed, m=max_wait: setattr(
                            self.debug_textbox, 'Text',
                            'Waiting for browser sign-in... {}s/{}s'.format(e, m)))
                    time.sleep(1)
                    elapsed += 1
                    token = AUTH.get_token()
                    if token:
                        break
                if not token:
                    self._invoke_ui(lambda: setattr(self.debug_textbox, 'Text', 'Sign-in timed out.'))
                    return

            if self._form_closed:
                return

            def update_status(msg):
                self._invoke_ui(lambda m=msg: setattr(self.debug_textbox, 'Text', m))

            update_status("Uploading to EnneaDuck...")

            images = AI.render_image_with_token(
                token, self._input_path, self._render_prompt,
                style_image_path=self._style_ref_path,
                progress_callback=update_status)

            saved = []
            for i, img in enumerate(images):
                b64 = img.get("b64", "")
                mime = img.get("mime", "image/png")
                ext = ".png" if "png" in mime else ".jpeg"
                out_path = os.path.join(self._session_folder, "Result_{}{}".format(i + 1, ext))
                with open(out_path, "wb") as f:
                    f.write(base64.b64decode(b64))
                saved.append(out_path)

            if self._form_closed:
                return

            def show_result():
                SOUND.play_sound("sound_effect_popup_msg3.wav")
                self.debug_textbox.Text = "Done! {} image(s) saved.".format(len(saved))
                if saved:
                    self._result_path = saved[0]
                    self._result_preview = _load_bmp_image(saved[0])
                    self.result_preview.Source = self._result_preview
                    self.preview_label.Text = "AI Result:"
                    self.result_buttons.Visibility = Visibility.Visible
                    self._showing_result = True
                    self.bt_toggle.Content = "Show Original"
            self._invoke_ui(show_result)

        except AI.AIRequestError as e:
            if e.status_code == 401:
                AUTH.clear_token()
                self._invoke_ui(lambda: setattr(self.debug_textbox, 'Text', 'Token expired. Try again.'))
            else:
                self._invoke_ui(
                    lambda ex=e: setattr(self.debug_textbox, 'Text',
                                         'Render failed: {}'.format(str(ex)[:200])))
        except Exception as e:
            self._invoke_ui(
                lambda ex=e: setattr(self.debug_textbox, 'Text',
                                     'Error: {}'.format(str(ex)[:200])))
        finally:
            self._rendering = False
            try:
                def cleanup():
                    self.bt_render.IsEnabled = True
                    self.progress_bar.Visibility = Visibility.Collapsed
                self._invoke_ui(cleanup)
            except Exception:
                pass


@LOG.log(__file__, __title__)
@ERROR_HANDLE.try_catch_error()
def main():
    # Prevent duplicate form
    if _active_form[0] is not None:
        try:
            _active_form[0].Focus()
        except Exception:
            _active_form[0] = None
        if _active_form[0] is not None:
            return

    output = script.get_output()
    output.close_others()
    form = AiRenderForm()
    _active_form[0] = form


if __name__ == "__main__":
    main()
