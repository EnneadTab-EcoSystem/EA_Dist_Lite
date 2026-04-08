# -*- coding: utf-8 -*-
__title__ = "AiRenderingFromView"
__doc__ = """Renders Rhino views using Gemini AI via EnneaDuck.

Captures current viewport, sends it with a style prompt to ennead-ai.com,
and returns a polished architectural rendering. No local GPU required.
"""

import time
import os
import base64

import Rhino # pyright: ignore
import scriptcontext as sc
import Eto # pyright: ignore
import System # pyright: ignore
from System.Threading import Thread, ThreadStart # pyright: ignore

from EnneadTab import NOTIFICATION, FOLDER, SOUND, IMAGE
from EnneadTab import LOG, ERROR_HANDLE, AUTH, AI
from EnneadTab.RHINO import RHINO_UI


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
    {"name": "Aerial Perspective", "category": "Architectural Styles",
     "prompt": "Aerial view architectural rendering, bird's eye perspective, masterplan visualization, landscape integration, professional urban design rendering"},
    {"name": "Black & White", "category": "Graphic Style",
     "prompt": "Black and white architectural rendering, high contrast, dramatic shadows, monochrome, fine art photography style, stark and elegant"},
]

# Categories we care about for desktop render tool
RELEVANT_CATEGORIES = [
    "Architectural Styles", "Graphic Style", "Lighting", "Weather",
    "Exteriors", "Interiors", "Materials & Textures",
]


def _load_presets():
    """Load presets from API (cached) or fall back to local."""
    cache_key = "EA_AI_RENDER_PRESETS"
    if sc.sticky.has_key(cache_key):
        return sc.sticky[cache_key]

    try:
        token = AUTH.get_token()
        api_presets = AI.get_render_presets(token=token)
        if api_presets:
            filtered = [p for p in api_presets
                        if p.get("category") in RELEVANT_CATEGORIES]
            if filtered:
                sc.sticky[cache_key] = filtered
                return filtered
    except Exception:
        pass

    sc.sticky[cache_key] = LOCAL_PRESETS
    return LOCAL_PRESETS


class ViewCaptureDialog(Eto.Forms.Form):

    def __init__(self):
        self.Title = "EnneaDuck: AI View Render"
        self.Padding = Eto.Drawing.Padding(10)

        # Load presets
        self._presets = _load_presets()
        self._categories = sorted(set(p.get("category", "Other") for p in self._presets))

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

        # Preview image
        self.m_label = Eto.Forms.Label(Text="Capture your view below:")
        layout.AddRow(self.m_label)
        self.m_image_view = Eto.Forms.ImageView()
        self.preview_w, self.preview_h = 500, 350
        self.m_image_view.Size = Eto.Drawing.Size(self.preview_w, self.preview_h)
        layout.AddRow(self.m_image_view)

        # Before/After toggle + result action buttons
        self.bt_toggle = Eto.Forms.Button(Text="Show AI Result")
        self.bt_toggle.Click += self.on_toggle
        self.bt_toggle.Visible = False
        self.bt_copy = Eto.Forms.Button(Text="Copy to Clipboard")
        self.bt_copy.Click += self.on_copy_image
        self.bt_copy.Visible = False
        self.bt_save = Eto.Forms.Button(Text="Save As...")
        self.bt_save.Click += self.on_save_image
        self.bt_save.Visible = False
        layout.AddSeparateRow(self.bt_toggle, None, self.bt_copy, self.bt_save)

        # Category + Style dropdowns
        layout.AddRow(Eto.Forms.Label(Text="\nRendering Style:"))
        self.cb_category = Eto.Forms.ComboBox()
        self.cb_category.DataStore = ["All"] + self._categories
        self.cb_category.SelectedIndex = 0
        self.cb_category.SelectedIndexChanged += self.on_category_changed
        self.cb_style = Eto.Forms.ComboBox()
        self._update_style_list()
        self.cb_style.SelectedIndexChanged += self.on_style_changed
        layout.AddSeparateRow(self.cb_category, self.cb_style)

        # Prompt
        layout.AddRow(Eto.Forms.Label(Text="\nPrompt (edit or write your own):"))
        self.tbox_prompt = Eto.Forms.TextArea()
        self.tbox_prompt.Size = Eto.Drawing.Size(500, 70)
        if self._filtered_presets:
            self.tbox_prompt.Text = self._filtered_presets[0].get("prompt", "")
        layout.AddRow(self.tbox_prompt)

        # Style reference image (optional)
        layout.AddRow(Eto.Forms.Label(Text="\nStyle Reference (optional):"))
        bt_browse_style = Eto.Forms.Button(Text="Browse...")
        bt_browse_style.Click += self.on_browse_style
        bt_paste_style = Eto.Forms.Button(Text="Paste from Clipboard")
        bt_paste_style.Click += self.on_paste_style
        self.bt_clear_style = Eto.Forms.Button(Text="Clear")
        self.bt_clear_style.Click += self.on_clear_style
        self.bt_clear_style.Visible = False
        self._style_preview = Eto.Forms.ImageView()
        self._style_preview.Size = Eto.Drawing.Size(60, 60)
        layout.AddSeparateRow(bt_browse_style, bt_paste_style, self.bt_clear_style,
                              None, self._style_preview)

        # Progress bar (hidden until rendering)
        self.progress_bar = Eto.Forms.ProgressBar()
        self.progress_bar.Indeterminate = True
        self.progress_bar.Visible = False
        layout.AddRow(self.progress_bar)

        # Action buttons
        bt_capture = Eto.Forms.Button(Text="Update Capture")
        bt_capture.Click += self.on_capture
        self.bt_render = Eto.Forms.Button(Text="Send to EnneaDuck")
        self.bt_render.Click += self.on_render
        bt_close = Eto.Forms.Button(Text="Close")
        bt_close.Click += self.on_close
        bt_open_folder = Eto.Forms.Button(Text="Open Output Folder")
        bt_open_folder.Click += self.on_open_folder

        btn_layout = Eto.Forms.DynamicLayout()
        btn_layout.AddSeparateRow(bt_capture, None, self.bt_render, bt_close)
        btn_layout.AddSeparateRow(None, bt_open_folder)
        layout.AddRow(btn_layout)

        # Status
        self.status_label = Eto.Forms.Label(Text="Ready.")
        layout.AddRow(self.status_label)

        self.Content = layout

        # State
        self._capture_bitmap = None
        self._result_bitmap = None
        self._showing_result = False
        self._result_path = None
        self._style_ref_path = None
        self._rendering = False
        self._form_closed = False

        self.capture_view()
        RHINO_UI.apply_dark_style(self)
        self.Closed += self.on_form_closed

    # --- Preset management ---

    def _update_style_list(self):
        """Update style dropdown based on selected category."""
        cat = self.cb_category.DataStore[self.cb_category.SelectedIndex] if self.cb_category.SelectedIndex >= 0 else "All"
        if cat == "All":
            self._filtered_presets = list(self._presets)
        else:
            self._filtered_presets = [p for p in self._presets if p.get("category") == cat]
        self.cb_style.DataStore = [p.get("name", "?") for p in self._filtered_presets]
        if self._filtered_presets:
            self.cb_style.SelectedIndex = 0

    def on_category_changed(self, sender, e):
        self._update_style_list()
        if self._filtered_presets:
            self.tbox_prompt.Text = self._filtered_presets[0].get("prompt", "")

    def on_style_changed(self, sender, e):
        idx = self.cb_style.SelectedIndex
        if 0 <= idx < len(self._filtered_presets):
            self.tbox_prompt.Text = self._filtered_presets[idx].get("prompt", "")

    # --- View capture ---

    def on_form_closed(self, sender, e):
        self._form_closed = True
        if sc.sticky.has_key("EA_AI_RENDER_CAPTURE_FORM"):
            sc.sticky.Remove("EA_AI_RENDER_CAPTURE_FORM")

    def capture_view(self):
        view = sc.doc.Views.ActiveView
        original_size = view.Size
        view.Size = System.Drawing.Size(self.preview_w, self.preview_h)
        eto_bmp = Rhino.UI.EtoExtensions.ToEto(view.CaptureToBitmap())
        self.m_image_view.Image = eto_bmp
        self.m_image_view.Size = Eto.Drawing.Size(self.preview_w, self.preview_h)
        view.Size = original_size
        self.m_label.Text = "Captured: {}".format(view.ActiveViewport.Name)
        self._capture_bitmap = eto_bmp
        self._result_bitmap = None
        self._showing_result = False
        self.bt_toggle.Visible = False
        self.bt_copy.Visible = False
        self.bt_save.Visible = False

    def on_capture(self, sender, e):
        self.capture_view()

    # --- Before/After toggle ---

    def on_toggle(self, sender, e):
        if self._showing_result:
            self.m_image_view.Image = self._capture_bitmap
            self.m_label.Text = "Original Capture"
            self.bt_toggle.Text = "Show AI Result"
            self._showing_result = False
        else:
            self.m_image_view.Image = self._result_bitmap
            self.m_label.Text = "AI Result"
            self.bt_toggle.Text = "Show Original"
            self._showing_result = True

    # --- Copy / Save result ---

    def on_copy_image(self, sender, e):
        if not self._result_path or not os.path.exists(self._result_path):
            self.status_label.Text = "No result image to copy."
            return
        try:
            sys_bmp = System.Drawing.Bitmap(self._result_path)
            try:
                System.Windows.Forms.Clipboard.SetImage(sys_bmp)
            finally:
                sys_bmp.Dispose()
            self.status_label.Text = "Copied to clipboard."
        except Exception:
            try:
                clipboard = Eto.Forms.Clipboard()
                clipboard.Image = self._result_bitmap
                self.status_label.Text = "Copied to clipboard."
            except Exception as ex:
                self.status_label.Text = "Copy failed: {}".format(str(ex)[:150])

    def on_save_image(self, sender, e):
        if not self._result_path or not os.path.exists(self._result_path):
            self.status_label.Text = "No result image to save."
            return
        dlg = Eto.Forms.SaveFileDialog()
        dlg.Title = "Save Rendered Image"
        ext = os.path.splitext(self._result_path)[1]
        dlg.Filters.Add(Eto.Forms.FileFilter("Image (*{})".format(ext), "*{}".format(ext)))
        dlg.FileName = "EnneaDuck_Render{}".format(ext)
        if dlg.ShowDialog(self) == Eto.Forms.DialogResult.Ok:
            import shutil
            shutil.copy2(self._result_path, dlg.FileName)
            self.status_label.Text = "Saved to {}".format(dlg.FileName)

    # --- Style reference ---

    def on_browse_style(self, sender, e):
        dlg = Eto.Forms.OpenFileDialog()
        dlg.Title = "Select Style Reference Image"
        dlg.Filters.Add(Eto.Forms.FileFilter("Images", ".png", ".jpg", ".jpeg"))
        if dlg.ShowDialog(self) == Eto.Forms.DialogResult.Ok:
            self._set_style_ref(dlg.FileName)

    def on_paste_style(self, sender, e):
        try:
            clipboard = Eto.Forms.Clipboard()
            if clipboard.ContainsImage:
                temp_path = os.path.join(FOLDER.DUMP_FOLDER, "ai_render_style_ref.png")
                if not os.path.exists(FOLDER.DUMP_FOLDER):
                    os.makedirs(FOLDER.DUMP_FOLDER)
                eto_img = clipboard.Image
                sys_bmp = Rhino.UI.EtoExtensions.ToSD(eto_img)
                try:
                    sys_bmp.Save(temp_path, System.Drawing.Imaging.ImageFormat.Png)
                finally:
                    sys_bmp.Dispose()
                self._set_style_ref(temp_path)
            else:
                self.status_label.Text = "No image in clipboard."
        except Exception as ex:
            self.status_label.Text = "Paste failed: {}".format(str(ex)[:150])

    def on_clear_style(self, sender, e):
        self._style_ref_path = None
        self._style_preview.Image = None
        self.bt_clear_style.Visible = False
        self.status_label.Text = "Style reference cleared."

    def _set_style_ref(self, path):
        self._style_ref_path = path
        eto_bmp = Eto.Drawing.Bitmap(path)
        self._style_preview.Image = eto_bmp.WithSize(60, 60)
        self.bt_clear_style.Visible = True
        self.status_label.Text = "Style reference: {}".format(os.path.basename(path))

    # --- Render (async) ---

    @ERROR_HANDLE.try_catch_error()
    def on_render(self, sender, e):
        if self._rendering:
            return
        prompt = self.tbox_prompt.Text
        if not prompt or not prompt.strip():
            self.status_label.Text = "Please enter a rendering prompt."
            return

        # Save viewport to file
        session = time.strftime("%Y%m%d-%H%M%S")
        self._session_folder = os.path.join(
            FOLDER.DUMP_FOLDER, "EnneadTab_Ai_Rendering", "Session_{}".format(session))
        if not os.path.exists(self._session_folder):
            os.makedirs(self._session_folder)
        self._input_path = os.path.join(self._session_folder, "Original.jpeg")

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
        try:
            bitmap.Save(self._input_path, System.Drawing.Imaging.ImageFormat.Jpeg)
        finally:
            bitmap.Dispose()

        self._render_prompt = prompt
        self._rendering = True
        self.bt_render.Enabled = False
        self.progress_bar.Visible = True
        self.status_label.Text = "Starting..."

        # Run render in background thread
        thread = Thread(ThreadStart(self._render_worker))
        thread.IsBackground = True
        thread.Start()

    def _invoke_ui(self, fn):
        """Run fn on the UI thread. Safe if form is closed."""
        if self._form_closed:
            return
        try:
            Eto.Forms.Application.Instance.Invoke(System.Action(fn))
        except Exception:
            pass

    def _render_worker(self):
        """Background thread: auth + API call."""
        try:
            # Auth
            self._invoke_ui(lambda: setattr(self.status_label, 'Text', 'Authenticating...'))
            token = AUTH.get_token()
            if not token:
                if not AUTH.is_auth_in_progress():
                    AUTH.request_auth()
                max_wait = 120
                elapsed = 0
                while elapsed < max_wait and not self._form_closed:
                    self._invoke_ui(
                        lambda e=elapsed, m=max_wait: setattr(
                            self.status_label, 'Text',
                            'Waiting for browser sign-in... {}s/{}s'.format(e, m)))
                    time.sleep(1)
                    elapsed += 1
                    token = AUTH.get_token()
                    if token:
                        break
                if not token:
                    self._invoke_ui(lambda: setattr(self.status_label, 'Text', 'Sign-in timed out.'))
                    return

            # Progress callback (runs on background thread, updates UI via invoke)
            def update_status(msg):
                self._invoke_ui(lambda m=msg: setattr(self.status_label, 'Text', m))

            update_status("Uploading to EnneaDuck...")

            images = AI.render_image_with_token(
                token, self._input_path, self._render_prompt,
                style_image_path=self._style_ref_path,
                progress_callback=update_status)

            # Save results
            saved = []
            for i, img in enumerate(images):
                b64 = img.get("b64", "")
                mime = img.get("mime", "image/png")
                ext = ".png" if "png" in mime else ".jpeg"
                out_path = os.path.join(self._session_folder, "Result_{}{}".format(i + 1, ext))
                with open(out_path, "wb") as f:
                    f.write(base64.b64decode(b64))
                saved.append(out_path)

            # Update UI with result
            def show_result():
                SOUND.play_sound("sound_effect_popup_msg3.wav")
                self.status_label.Text = "Done! {} image(s) saved.".format(len(saved))
                if saved:
                    self._result_path = saved[0]
                    result_eto_bmp = Eto.Drawing.Bitmap(saved[0])
                    self._result_bitmap = result_eto_bmp.WithSize(self.preview_w, self.preview_h)
                    self.m_image_view.Image = self._result_bitmap
                    self.m_label.Text = "AI Result"
                    self._showing_result = True
                    self.bt_toggle.Visible = True
                    self.bt_toggle.Text = "Show Original"
                    self.bt_copy.Visible = True
                    self.bt_save.Visible = True
            self._invoke_ui(show_result)

        except AI.AIRequestError as e:
            if e.status_code == 401:
                AUTH.clear_token()
                self._invoke_ui(lambda: setattr(self.status_label, 'Text', 'Token expired. Please try again.'))
            else:
                self._invoke_ui(
                    lambda ex=e: setattr(self.status_label, 'Text',
                                         'Render failed: {}'.format(str(ex)[:200])))
        except Exception as e:
            self._invoke_ui(
                lambda ex=e: setattr(self.status_label, 'Text',
                                     'Error: {}'.format(str(ex)[:200])))
        finally:
            self._rendering = False  # reset immediately (thread-safe for bool)
            try:
                def cleanup():
                    self.bt_render.Enabled = True
                    self.progress_bar.Visible = False
                self._invoke_ui(cleanup)
            except Exception:
                pass

    # --- Misc ---

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
