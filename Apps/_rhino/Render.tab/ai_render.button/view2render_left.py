# -*- coding: utf-8 -*-
__title__ = "AiRenderingFromView"
__doc__ = """View rendering for Rhino through Ennead's in-house style library.

Capture the active viewport, queue prompts, and see your full cloud Gallery
across every device (Revit, Rhino, mobile web, desktop web - same items).

All features call the live ennead-ai.com web API. No local fallbacks: when
the web product improves, this dialog improves automatically.
"""

import time
import os
import shutil
import webbrowser

import Rhino # pyright: ignore
import scriptcontext as sc
import Eto # pyright: ignore
import System # pyright: ignore
from System.Threading import Monitor # pyright: ignore

from EnneadTab import FOLDER, IMAGE  # noqa: F401
from EnneadTab import LOG, ERROR_HANDLE, AUTH
from EnneadTab.AI import AI_CHAT, AI_RENDER
from EnneadTab.AI._common import AIRequestError  # noqa: F401
from EnneadTab.RHINO import RHINO_UI

import ai_render_gallery_module as G

# Native Eto image viewer (2026-04-28). Imported at script-load time so a
# missing/broken module surfaces immediately on the Rhino command line
# instead of silently falling through to os.startfile every time the
# user clicks a thumbnail. _SHOW_VIEWER stays None on import failure so
# callers know to use the legacy path.
#
# 2026-04-28 v3 — explicitly invalidate sys.modules entry FOR EVERY
# sibling module on each dialog open. Rhino's IronPython script engine
# holds onto previously-loaded modules even after _-RunPythonScript
# ResetEngine. v2 only invalidated the viewer; gallery_module changes
# (row metadata, materialize_thumb, etc.) were silently no-ops because
# the cached version kept loading.
import sys as _sys
import time as _t_modload
_AI_RENDER_LOAD_TS = _t_modload.strftime("%H:%M:%S")
for _stale in ("ai_render_image_viewer", "ai_render_gallery_module"):
    if _stale in _sys.modules:
        try:
            del _sys.modules[_stale]
        except Exception:
            pass
_SHOW_VIEWER = None
try:
    from ai_render_image_viewer import show_viewer as _SHOW_VIEWER
    Rhino.RhinoApp.WriteLine(
        "[ai_render] view2render_left.py loaded {} (viewer OK)".format(
            _AI_RENDER_LOAD_TS))
except Exception as _viewer_import_ex:
    try:
        Rhino.RhinoApp.WriteLine(
            "[ai_render] native image viewer FAILED to import: {} - "
            "thumbnails will open in the OS default app instead".format(
                _viewer_import_ex))
    except Exception:
        pass


# 2026-04-21 — Crash tracer. Queue Render is currently crashing Rhino with
# no journal/log to point at. _trace() flushes a timestamped breadcrumb to
# disk so the next crash leaves a trail showing exactly where execution
# died (even if the failure is a native AccessViolation Python can't catch).
# Remove these calls once the crash class is identified and stable.
_TRACE_PATH = None
def _trace(msg):
    global _TRACE_PATH
    try:
        if _TRACE_PATH is None:
            base = os.environ.get("APPDATA") or os.path.expanduser("~")
            d = os.path.join(base, "EnneadTab")
            try:
                if not os.path.isdir(d):
                    os.makedirs(d)
            except Exception:
                pass
            _TRACE_PATH = os.path.join(d, "ai_render_trace.log")
        f = open(_TRACE_PATH, "a")
        try:
            from datetime import datetime
            f.write("{}  {}\n".format(
                datetime.now().strftime("%H:%M:%S.%f")[:-3], msg))
            f.flush()
            try:
                os.fsync(f.fileno())
            except Exception:
                pass
        finally:
            f.close()
    except Exception:
        pass


STUDIO_URL = "https://ennead-ai.com"


# ----------------------------------------------------------------------
# Preference persistence (2026-04-28)
# ----------------------------------------------------------------------
# Small JSON file in %APPDATA%/EnneadTab/ remembers checkbox + dropdown
# state across sessions so the user only has to set their preferences once.
# Kept tiny and dependency-free; failures fall back to defaults silently.
_PREF_FILE = None
def _pref_path():
    global _PREF_FILE
    if _PREF_FILE is None:
        base = os.environ.get("APPDATA") or os.path.expanduser("~")
        d = os.path.join(base, "EnneadTab")
        try:
            if not os.path.isdir(d):
                os.makedirs(d)
        except Exception:
            pass
        _PREF_FILE = os.path.join(d, "ai_render_prefs.json")
    return _PREF_FILE

def _load_prefs():
    import json
    try:
        with open(_pref_path(), "r") as f:
            return json.load(f) or {}
    except Exception:
        return {}

def _save_prefs(prefs):
    import json
    try:
        with open(_pref_path(), "w") as f:
            json.dump(prefs, f, indent=2)
    except Exception:
        pass

RESOLUTION_OPTIONS = [
    ("Low (768 px)", 768),
    ("Medium (1024 px)", 1024),
    ("High (1500 px)", 1500),
    ("Ultra (2048 px)", 2048),
]
ASPECT_OPTIONS = ["16:9", "4:3", "3:2", "1:1", "9:16", "21:9"]
DEFAULT_RESOLUTION_LABEL = "High (1500 px)"
DEFAULT_ASPECT = "16:9"
PROMPT_UNDO_CAP = 10
ROW_HEIGHT = 72


def _compute_px(long_edge, aspect):
    try:
        wp, hp = aspect.split(":")
        w, h = float(wp), float(hp)
    except Exception:
        w, h = 16.0, 9.0
    if w >= h:
        return (int(long_edge), int(round(long_edge * h / w)))
    return (int(round(long_edge * w / h)), int(long_edge))


_INVALID_FILENAME_CHARS = '<>:"/\\|?*'


def _safe_filename(s):
    out = []
    for c in (s or ""):
        if c in _INVALID_FILENAME_CHARS or ord(c) < 32:
            out.append("_")
        else:
            out.append(c)
    cleaned = "".join(out).strip("_ \t\r\n")
    return (cleaned or "untitled").replace(" ", "_")


def _items_text(dropdown, idx):
    """Defensive accessor for Eto.Forms.DropDown items.

    Some Rhino 7 Eto versions store strings directly when added via
    Items.Add(string); others wrap them in a ListItem with .Text.
    Also guards against -1 / out-of-range indices (Round 2 P2-edge-14).
    """
    if idx is None or idx < 0:
        return ""
    try:
        if idx >= dropdown.Items.Count:
            return ""
    except Exception:
        pass
    item = dropdown.Items[idx]
    return getattr(item, "Text", item) if item is not None else ""


def _hex_to_color(hex_str):
    """Eto.Drawing.Color from #RRGGBB or #AARRGGBB hex string.

    Lifted to EnneadTab.RHINO.RHINO_UI.hex_to_eto_color (2026-04-30) so
    the parse logic lives in COLOR.py (framework-agnostic) and the Eto
    construction lives next to other Eto helpers. This local wrapper
    is kept as a thin alias to avoid a sweeping rename across ~40
    callsites in this file. New code should call
    RHINO_UI.hex_to_eto_color directly.
    """
    return RHINO_UI.hex_to_eto_color(hex_str)


class GalleryRowPanel(Eto.Forms.Panel):
    """Custom Eto Panel rendering one GalleryRow. Owns its own buttons + click
    handlers; main form attaches via per-instance lambdas.

    2026-04-21 — Factory pattern (per McNeel forum thread on Eto subclass
    init args, https://discourse.mcneel.com/t/eto-forms-class-inheritance-
    and-initialization-argument-issue/167981). IronPython 2.7's CLR-derived
    constructor binder runs the .NET base `Eto.Forms.Panel(content=None)`
    BEFORE the Python __init__, so any extra args fail with "takes at most
    2 arguments (N given)". Workaround is mandatory: __init__ takes ZERO
    args (matching the Panel(content=None) overload exactly), and a
    classmethod factory `create(...)` instantiates then calls `_initialize`.
    Confirmed by `ai_render_trace.log` 14:48 — every row failed with the
    arity error until we adopted this pattern; gallery panel rendered empty
    despite history count == 7.
    """

    @classmethod
    def create(cls, row, on_view_original, on_view_result, on_save, on_context):
        inst = cls()  # zero-arg init goes through Panel(content=None) cleanly
        inst._initialize(row, on_view_original, on_view_result, on_save, on_context)
        return inst

    def _initialize(self, row, on_view_original, on_view_result, on_save, on_context):
        self._row = row
        self._on_view_original = on_view_original
        self._on_view_result = on_view_result
        self._on_save = on_save
        self._on_context = on_context

        self.BackgroundColor = _hex_to_color("#FF333333")
        self.Padding = Eto.Drawing.Padding(4)
        # 2026-04-21 — thumb size driven by G.THUMB_W/H so the dialog's
        # "Large" toggle (set_thumb_size + rebuild) makes both data + view
        # scale together. Row height = thumb height + small chrome padding.
        tw, th = G.THUMB_W, G.THUMB_H
        self.Size = Eto.Drawing.Size(0, max(ROW_HEIGHT, th + 12))

        layout = Eto.Forms.DynamicLayout()
        layout.Spacing = Eto.Drawing.Size(6, 0)
        layout.BeginHorizontal()

        # Original thumb
        iv_orig = Eto.Forms.ImageView()
        iv_orig.Size = Eto.Drawing.Size(tw, th)
        if row.OriginalThumb is not None:
            iv_orig.Image = row.OriginalThumb
        iv_orig.MouseDown += self._handle_orig_click
        layout.Add(iv_orig)

        # Result thumb
        iv_res = Eto.Forms.ImageView()
        iv_res.Size = Eto.Drawing.Size(tw, th)
        if row.ResultThumb is not None:
            iv_res.Image = row.ResultThumb
        iv_res.MouseDown += self._handle_res_click
        layout.Add(iv_res)

        # Info column. Three stacked labels:
        #   - StyleName (bold, top)
        #   - full prompt (wraps to multiple lines, fills middle)
        #   - Subtitle (small grey, pinned to bottom by spacer)
        # The spacer (empty Add with yscale=True) pushes the subtitle to the
        # bottom of the row so it visually aligns with the status column's
        # bottom-aligned status text.
        info = Eto.Forms.DynamicLayout()
        info.Padding = Eto.Drawing.Padding(0)
        info.Spacing = Eto.Drawing.Size(0, 2)
        lbl_style = Eto.Forms.Label(Text=row.StyleName)
        lbl_style.Font = Eto.Drawing.Font(Eto.Drawing.SystemFont.Bold, 11)
        info.Add(lbl_style)
        lbl_prompt = Eto.Forms.Label(Text=(row.full_prompt or row.PromptPreview))
        lbl_prompt.TextColor = _hex_to_color("#CBCBCB")
        try:
            lbl_prompt.Wrap = Eto.Forms.WrapMode.Word
        except Exception:
            pass  # older Eto builds may not expose Wrap
        info.Add(lbl_prompt, yscale=True)
        lbl_sub = Eto.Forms.Label(Text=row.Subtitle)
        lbl_sub.TextColor = _hex_to_color("#9A9A9A")
        info.Add(lbl_sub)
        layout.Add(info, xscale=True)

        # Status + progress column. Top spacer pushes content to the bottom
        # so the status text aligns with the Subtitle line in the info column.
        status_col = Eto.Forms.DynamicLayout()
        status_col.Spacing = Eto.Drawing.Size(0, 2)
        status_col.Add(None, yscale=True)  # bottom-align spacer
        lbl_st = Eto.Forms.Label(Text=row.StatusText)
        lbl_st.TextColor = _hex_to_color(row.StatusColor)
        lbl_st.Font = Eto.Drawing.Font(Eto.Drawing.SystemFont.Bold, 11)
        status_col.Add(lbl_st)
        if row.ProgressVisibility:
            pb = Eto.Forms.ProgressBar()
            pb.Indeterminate = bool(row.ProgressIndeterminate)
            pb.Value = int(row.ProgressPct or 0)
            pb.MaxValue = 100
            pb.Height = 6
            status_col.Add(pb)
        layout.Add(status_col)

        # Inline save button (only when SaveVisibility True). Wrapped in its
        # own bottom-aligned column so it sits on the same baseline as the
        # status text and Subtitle, not floating top.
        if row.SaveVisibility:
            save_col = Eto.Forms.DynamicLayout()
            save_col.Add(None, yscale=True)  # bottom-align spacer
            bt = Eto.Forms.Button(Text="💾")
            bt.Size = Eto.Drawing.Size(28, 28)
            bt.Click += self._handle_save_click
            save_col.Add(bt)
            layout.Add(save_col)

        layout.EndHorizontal()
        self.Content = layout

        # Context-menu via right-click anywhere on the panel.
        self.MouseDown += self._handle_panel_mouse

    def _handle_orig_click(self, sender, e):
        if e.Buttons == Eto.Forms.MouseButtons.Primary:
            self._on_view_original(self._row)

    def _handle_res_click(self, sender, e):
        if e.Buttons == Eto.Forms.MouseButtons.Primary:
            self._on_view_result(self._row)

    def _handle_save_click(self, sender, e):
        self._on_save(self._row)

    def _handle_panel_mouse(self, sender, e):
        if e.Buttons == Eto.Forms.MouseButtons.Alternate:
            self._on_context(self._row, sender)


class AiRenderForm(Eto.Forms.Form):

    def __init__(self):
        # 2026-04-28 — load saved preferences (window size, checkboxes,
        # dropdown selections) before constructing widgets so they can be
        # applied during _build_ui rather than re-applied afterward.
        self._prefs = _load_prefs()
        win_w = int(self._prefs.get("window_w", 1180))
        win_h = int(self._prefs.get("window_h", 940))

        self.Title = "EnneaDuck: View Render"
        self.Padding = Eto.Drawing.Padding(8)
        self.Size = Eto.Drawing.Size(win_w, win_h)
        self.MinimumSize = Eto.Drawing.Size(900, 560)

        self._form_closed = False
        self._jobs = []
        self._jobs_lock = System.Object()
        self._all_rows = []  # cached cloud rows
        # 2026-04-28 — distinguishes "history hasn't loaded yet" from
        # "history loaded but empty" so the gallery can show skeleton
        # placeholder rows during the initial fetch instead of "0 items".
        self._history_loaded = False
        self._filter_seconds = 7 * 86400
        self._filter_query = ""
        self._auto_save_enabled = bool(self._prefs.get("auto_save", True))
        self._last_tick_state = None  # explicit init (Round 3 P2-9)
        self._presets = []
        self._categories = []
        self._filtered_presets = []
        self._initial_prompt_for_reset = ""
        self._prompt_undo = []
        self._style_ref_path = None
        self._capture_path = None
        self._capture_view_name = ""
        self._last_save_folder = None
        self._my_prompts = []

        # Auto-capture state (2026-04-28). DisplayPipeline.PostDrawObjects
        # fires per redraw of any viewport — only when something changes,
        # so this is genuinely event-driven (not a 1Hz poll).
        self._auto_capture_enabled = bool(self._prefs.get("auto_capture", False))
        self._last_cam_signature = None
        self._auto_cap_timer = None
        self._draw_handler = None  # keep ref so .NET doesn't GC the delegate
        self._capturing = False    # in-flight guard so debounce-fire while a
                                    # capture is still saving/loading doesn't
                                    # stack a second one behind it (2026-04-28)

        self._build_ui()

        # Workers
        self._image_worker = AI_RENDER.QueueWorker(
            kind_filter=AI_RENDER.KIND_IMAGE,
            jobs_list=self._jobs,
            lock_obj=self._jobs_lock,
            invoke_ui=self._invoke_ui,
            job_update_callback=self._on_job_update,
            is_form_closed_fn=lambda: self._form_closed,
            auto_save_enabled_fn=lambda: self._auto_save_enabled,
            on_completion=self._on_any_job_complete)
        self._video_worker = AI_RENDER.QueueWorker(
            kind_filter=AI_RENDER.KIND_VIDEO,
            jobs_list=self._jobs,
            lock_obj=self._jobs_lock,
            invoke_ui=self._invoke_ui,
            job_update_callback=self._on_job_update,
            is_form_closed_fn=lambda: self._form_closed,
            auto_save_enabled_fn=lambda: self._auto_save_enabled,
            on_completion=self._on_any_job_complete)
        self._image_worker.start()
        self._video_worker.start()

        # Tick timer for live elapsed updates on active rows.
        self._tick_timer = Eto.Forms.UITimer()
        self._tick_timer.Interval = 1.0
        self._tick_timer.Elapsed += self._on_tick
        self._tick_timer.Start()

        self.Closed += self._on_closed
        try:
            self.SizeChanged += self._on_size_changed
        except Exception:
            pass

        # 2026-04-28 — Subscribe to DisplayPipeline so auto-capture is
        # event-driven. PostDrawObjects fires per viewport redraw, which
        # only happens when the camera/scene changes — when the dialog is
        # idle and Rhino isn't repainting, the handler costs nothing.
        try:
            self._draw_handler = self._on_post_draw
            Rhino.Display.DisplayPipeline.PostDrawObjects += self._draw_handler
        except Exception:
            self._draw_handler = None

        # Restore checkbox state from prefs now that widgets exist.
        # (cb_auto_capture is a styled Button, not a CheckBox — its visual
        # state is set by _apply_auto_capture_visual() during _build_ui.)
        try:
            self.cb_auto_save.Checked = self._auto_save_enabled
            self.cb_interior.Checked = bool(self._prefs.get("interior", False))
            self.cb_large_thumbs.Checked = bool(self._prefs.get("large_thumbs", True))
            res_idx = self._prefs.get("resolution_idx")
            if res_idx is not None and 0 <= int(res_idx) < self.cb_resolution.Items.Count:
                self.cb_resolution.SelectedIndex = int(res_idx)
            asp_idx = self._prefs.get("aspect_idx")
            if asp_idx is not None and 0 <= int(asp_idx) < self.cb_aspect.Items.Count:
                self.cb_aspect.SelectedIndex = int(asp_idx)
        except Exception:
            pass

        # Cleanup old capture_* folders (>7 days). Round 2 P1.
        try:
            AI_RENDER.cleanup_old_captures(FOLDER.DUMP_FOLDER, max_age_days=7)
        except Exception:
            pass

        # Render skeleton rows BEFORE kicking off the async cloud fetch
        # so the gallery doesn't read as "0 items" during the 0.5-3s
        # network round-trip. _apply_gallery_rows replaces them when
        # real data arrives.
        try:
            self._render_skeleton_rows()
        except Exception:
            pass

        # Async loads
        self._load_presets_async()
        self._open_browser_if_needed()
        self._refresh_gallery_async()
        self._refresh_quota_async()
        self._refresh_my_prompts_async()
        self._capture_view()

        RHINO_UI.apply_dark_style(self)

    # ------------------------------------------------------------------
    # UI construction
    # ------------------------------------------------------------------

    def _build_ui(self):
        root = Eto.Forms.DynamicLayout()
        root.Padding = Eto.Drawing.Padding(8)
        root.Spacing = Eto.Drawing.Size(6, 6)

        # --- Header row ---
        hdr = Eto.Forms.DynamicLayout()
        hdr.BeginHorizontal()
        hdr.Add(self._build_logo())
        hdr.Add(self._build_title_block(), xscale=True)
        bt_web = Eto.Forms.LinkButton(Text="Open ennead-ai.com →")
        bt_web.Click += lambda s, e: webbrowser.open(STUDIO_URL)
        hdr.Add(bt_web)
        hdr.EndHorizontal()
        root.Add(hdr)

        # --- Controls (capture + prompt panels side by side) ---
        ctrl = Eto.Forms.DynamicLayout()
        ctrl.BeginHorizontal()
        ctrl.Add(self._build_capture_panel(), yscale=True)
        ctrl.Add(self._build_prompt_panel(), xscale=True, yscale=True)
        ctrl.EndHorizontal()
        root.Add(ctrl)

        # --- Primary CTA bar: status + Queue Render. 2026-04-28 — promoted
        # out of the prompt panel so it dominates over the chip toolbar. ---
        root.Add(self._build_cta_bar())

        # --- Filter bar + gallery ---
        root.Add(self._build_filter_bar())
        root.Add(self._build_gallery_panel(), yscale=True)

        # --- Footer ---
        root.Add(self._build_footer())

        self.Content = root

    def _build_logo(self):
        iv = Eto.Forms.ImageView()
        logo_path = IMAGE.get_image_path_by_name("logo_vertical_light.png")
        if logo_path and os.path.exists(logo_path):
            try:
                iv.Image = Eto.Drawing.Bitmap(logo_path).WithSize(40, 40)
            except Exception:
                pass
        iv.Size = Eto.Drawing.Size(40, 40)
        return iv

    def _build_title_block(self):
        col = Eto.Forms.DynamicLayout()
        title = Eto.Forms.Label(Text="EnneaDuck: View Render")
        title.Font = Eto.Drawing.Font(Eto.Drawing.SystemFont.Bold, 14)
        title.TextColor = _hex_to_color("#FFFFE59C")
        col.Add(title)
        sub = Eto.Forms.Label(
            Text="Render Rhino views through Ennead's curated style library.")
        sub.TextColor = _hex_to_color("#CBCBCB")
        col.Add(sub)
        return col

    def _build_capture_panel(self):
        # 2026-04-28 redesign:
        #   - Bigger capture preview (264x168 -> 280x220) so composition is
        #     readable at a glance ("images all small" feedback).
        #   - preview_label moved BELOW the preview to act as a caption
        #     instead of a header, freeing vertical space.
        #   - Style Reference buttons collapse from 4 vertical to 1 horizontal
        #     row of chips next to a smaller (100x76) thumb.
        col = Eto.Forms.DynamicLayout()
        col.Spacing = Eto.Drawing.Size(0, 4)
        col.Width = 320

        # STEP 1 eyebrow
        step1_lbl = Eto.Forms.Label(Text="STEP 1 / CAPTURE")
        step1_lbl.TextColor = _hex_to_color("#9A9A9A")
        step1_lbl.Font = Eto.Drawing.Font(Eto.Drawing.SystemFont.Bold, 9)
        col.Add(step1_lbl)

        self.capture_preview = Eto.Forms.ImageView()
        self.capture_preview.Size = Eto.Drawing.Size(300, 220)
        col.Add(self.capture_preview)
        self.preview_label = Eto.Forms.Label(Text="Click Update Capture to begin")
        self.preview_label.TextColor = _hex_to_color("#CBCBCB")
        col.Add(self.preview_label)
        # 2026-04-28 — paired buttons. Update Capture is the primary
        # explicit action; the auto-toggle to its right is a related MODE
        # control (modifies the button's behavior). Styling them as two
        # buttons of similar weight reads as a logical pair, not as
        # disconnected siblings the way the old CheckBox did.
        cap_row = Eto.Forms.DynamicLayout()
        cap_row.Spacing = Eto.Drawing.Size(6, 0)
        cap_row.BeginHorizontal()
        bt_cap = Eto.Forms.Button(Text="Update Capture")
        bt_cap.Click += self._on_capture
        cap_row.Add(bt_cap, xscale=True)

        # Auto-capture mode toggle styled as a button (Eto's CheckBox is
        # too low-contrast to communicate "this is a live mode"). Text +
        # accent color flip on toggle so the state is visible at a glance.
        # Internal API surface stays as `cb_auto_capture` so existing
        # handlers + prefs code don't need to change.
        self.cb_auto_capture = Eto.Forms.Button(Text="Auto: OFF")
        self.cb_auto_capture.ToolTip = (
            "Auto-recapture the viewport ~0.3s after the camera stops "
            "moving. Useful while iterating on framing.")
        # Synthesize a `Checked` property so existing code that reads/sets
        # cb_auto_capture.Checked keeps working against the Button.
        self._auto_capture_btn_state = bool(self._auto_capture_enabled)
        self.cb_auto_capture.Click += self._on_auto_capture_btn_click
        try:
            self.cb_auto_capture.Size = Eto.Drawing.Size(110, -1)
        except Exception:
            pass
        cap_row.Add(self.cb_auto_capture)
        cap_row.EndHorizontal()
        col.Add(cap_row)
        # Apply initial visual state (color/text reflects loaded pref).
        self._apply_auto_capture_visual()

        # Resolution: inline "Size [res] [aspect]"
        col.Add(Eto.Forms.Label(Text="Capture Resolution",
                                TextColor=_hex_to_color("#CBCBCB")))
        res_row = Eto.Forms.DynamicLayout()
        res_row.BeginHorizontal()
        self.cb_resolution = Eto.Forms.DropDown()
        for label, _ in RESOLUTION_OPTIONS:
            self.cb_resolution.Items.Add(label)
        self.cb_resolution.SelectedIndex = [l for l, _ in RESOLUTION_OPTIONS].index(DEFAULT_RESOLUTION_LABEL)
        self.cb_resolution.SelectedIndexChanged += self._on_resolution_changed
        res_row.Add(self.cb_resolution, xscale=True)
        self.cb_aspect = Eto.Forms.DropDown()
        for a in ASPECT_OPTIONS:
            self.cb_aspect.Items.Add(a)
        self.cb_aspect.SelectedIndex = ASPECT_OPTIONS.index(DEFAULT_ASPECT)
        self.cb_aspect.SelectedIndexChanged += self._on_resolution_changed
        res_row.Add(self.cb_aspect, xscale=True)
        res_row.EndHorizontal()
        col.Add(res_row)
        self.resolution_hint = Eto.Forms.Label(Text="")
        self.resolution_hint.TextColor = _hex_to_color("#9A9A9A")
        col.Add(self.resolution_hint)
        self._update_resolution_hint()

        # Style reference: chip-row of buttons + smaller inline thumb.
        col.Add(Eto.Forms.Label(Text="Style Reference (optional)",
                                TextColor=_hex_to_color("#CBCBCB")))
        ref_row = Eto.Forms.DynamicLayout()
        ref_row.BeginHorizontal()
        ref_btns = Eto.Forms.DynamicLayout()
        ref_btns.Spacing = Eto.Drawing.Size(0, 3)
        bt_browse = Eto.Forms.Button(Text="Browse...")
        bt_browse.Click += self._on_browse_style
        ref_btns.Add(bt_browse)
        bt_paste = Eto.Forms.Button(Text="Paste Clipboard")
        bt_paste.Click += self._on_paste_style
        ref_btns.Add(bt_paste)
        bt_lib = Eto.Forms.Button(Text="Load from Library...")
        bt_lib.Click += self._on_library_style
        ref_btns.Add(bt_lib)
        self.bt_clear_style = Eto.Forms.Button(Text="X Clear")
        self.bt_clear_style.Click += self._on_clear_style
        self.bt_clear_style.Visible = False
        ref_btns.Add(self.bt_clear_style)
        ref_row.Add(ref_btns, xscale=True)
        self.style_preview = Eto.Forms.ImageView()
        self.style_preview.Size = Eto.Drawing.Size(100, 76)
        ref_row.Add(self.style_preview)
        ref_row.EndHorizontal()
        col.Add(ref_row)
        return col

    def _build_prompt_panel(self):
        # 2026-04-28 redesign:
        #   - Prompt action buttons (Spell/Lengthen/Shorten/Reset/Undo) flipped
        #     from a vertical column on the right of the textbox into a
        #     horizontal chip toolbar ABOVE the textbox, alongside Interior.
        #   - TextArea height 120 -> 100 ("prompt uses too much space" feedback);
        #     scrollbar still handles long prompts.
        #   - Status label + Queue Render button removed from this panel; they
        #     now live in the dedicated CTA bar built by _build_cta_bar().
        col = Eto.Forms.DynamicLayout()
        col.Spacing = Eto.Drawing.Size(0, 4)

        # STEP 2 eyebrow
        step2_lbl = Eto.Forms.Label(Text="STEP 2 / STYLE + PROMPT")
        step2_lbl.TextColor = _hex_to_color("#9A9A9A")
        step2_lbl.Font = Eto.Drawing.Font(Eto.Drawing.SystemFont.Bold, 9)
        col.Add(step2_lbl)

        col.Add(Eto.Forms.Label(Text="Rendering Style",
                                TextColor=_hex_to_color("#CBCBCB")))
        cat_row = Eto.Forms.DynamicLayout()
        cat_row.Spacing = Eto.Drawing.Size(6, 0)
        cat_row.BeginHorizontal()
        # 2026-04-21 — switched DropDown → ComboBox + AutoComplete so users
        # can type-to-filter the curated list (matches the WPF Revit dialog
        # IsEditable=True + IsTextSearchEnabled=True). AutoComplete attempted
        # on every selector; some Eto builds don't expose it on ComboBox so
        # we set it defensively via try/except.
        def _make_searchable_combo(width=None):
            cb = Eto.Forms.ComboBox()
            if width is not None:
                cb.Width = width
            try:
                cb.AutoComplete = True
            except Exception:
                pass
            return cb
        self.cb_category = _make_searchable_combo(width=150)
        self.cb_category.SelectedIndexChanged += self._on_category_changed
        cat_row.Add(self.cb_category)
        self.cb_style = _make_searchable_combo()
        self.cb_style.SelectedIndexChanged += self._on_style_changed
        cat_row.Add(self.cb_style, xscale=True)
        cat_row.EndHorizontal()
        col.Add(cat_row)

        # My Prompts row
        myp_row = Eto.Forms.DynamicLayout()
        myp_row.Spacing = Eto.Drawing.Size(6, 0)
        myp_row.BeginHorizontal()
        myp_row.Add(Eto.Forms.Label(Text="My Prompts:",
                                    TextColor=_hex_to_color("#CBCBCB")))
        self.cb_my_prompts = _make_searchable_combo()
        self.cb_my_prompts.SelectedIndexChanged += self._on_my_prompt_changed
        myp_row.Add(self.cb_my_prompts, xscale=True)
        # 2026-04-28 — modal browser. Eto's ComboBox.ToolTip is silently
        # ignored on this Rhino build, so the per-item preview tooltip
        # never appeared. The Browse button opens a proper picker with
        # a name list on the left and a live full-prompt preview pane
        # on the right.
        bt_browse_p = Eto.Forms.Button(Text="Browse...")
        bt_browse_p.ToolTip = "Open a picker with full-prompt previews"
        bt_browse_p.Click += self._on_browse_my_prompts
        myp_row.Add(bt_browse_p)
        bt_save_p = Eto.Forms.Button(Text="Save current...")
        bt_save_p.Click += self._on_save_prompt
        myp_row.Add(bt_save_p)
        myp_row.EndHorizontal()
        col.Add(myp_row)

        # Prompt header: label + horizontal action toolbar + Interior toggle.
        ptop = Eto.Forms.DynamicLayout()
        ptop.Spacing = Eto.Drawing.Size(4, 0)
        ptop.BeginHorizontal()
        ptop.Add(Eto.Forms.Label(Text="Prompt",
                                 TextColor=_hex_to_color("#CBCBCB")))
        self.bt_spell = Eto.Forms.Button(Text="Spell")
        self.bt_spell.Click += self._on_spell
        ptop.Add(self.bt_spell)
        self.bt_lengthen = Eto.Forms.Button(Text="Lengthen")
        self.bt_lengthen.Click += self._on_lengthen
        ptop.Add(self.bt_lengthen)
        self.bt_shorten = Eto.Forms.Button(Text="Shorten")
        self.bt_shorten.Click += self._on_shorten
        ptop.Add(self.bt_shorten)
        self.bt_reset_prompt = Eto.Forms.Button(Text="Reset")
        self.bt_reset_prompt.Click += self._on_reset_prompt
        ptop.Add(self.bt_reset_prompt)
        self.bt_undo_prompt = Eto.Forms.Button(Text="Undo")
        self.bt_undo_prompt.Click += self._on_undo_prompt
        self.bt_undo_prompt.Enabled = False
        ptop.Add(self.bt_undo_prompt)
        ptop.Add(None, xscale=True)  # spacer pushes Interior to the right
        self.cb_interior = Eto.Forms.CheckBox(Text="Interior scene")
        self.cb_interior.CheckedChanged += self._on_interior_changed
        ptop.Add(self.cb_interior)
        ptop.EndHorizontal()
        col.Add(ptop)

        self.tbox_prompt = Eto.Forms.TextArea()
        self.tbox_prompt.Size = Eto.Drawing.Size(0, 100)
        self.tbox_prompt.AcceptsReturn = True
        col.Add(self.tbox_prompt, yscale=True)

        return col

    def _build_cta_bar(self):
        """Dedicated full-width band: status text on the left, Queue Render
        button on the right, accent-tinted background + larger button so the
        primary action stands out against every other button in the dialog.
        2026-04-28 — extracted from the old prompt-panel bottom row in
        response to feedback that Queue Render was hard to find among the
        Spell/Lengthen/Shorten/Reset/Undo button cluster."""
        panel = Eto.Forms.Panel()
        panel.BackgroundColor = _hex_to_color("#FF2E2E2E")
        panel.Padding = Eto.Drawing.Padding(14, 10)

        bar = Eto.Forms.DynamicLayout()
        bar.Spacing = Eto.Drawing.Size(12, 0)
        bar.BeginHorizontal()

        status_col = Eto.Forms.DynamicLayout()
        cta_eyebrow = Eto.Forms.Label(Text="READY TO RENDER")
        cta_eyebrow.TextColor = _hex_to_color("#9A9A9A")
        cta_eyebrow.Font = Eto.Drawing.Font(Eto.Drawing.SystemFont.Bold, 9)
        status_col.Add(cta_eyebrow)
        self.status_label = Eto.Forms.Label(
            Text="Ready. Capture a view then queue a render.")
        self.status_label.TextColor = _hex_to_color("#DAE8FD")
        self.status_label.Font = Eto.Drawing.Font(Eto.Drawing.SystemFont.Default, 11)
        status_col.Add(self.status_label)
        bar.Add(status_col, xscale=True)

        self.bt_render = Eto.Forms.Button(Text="Queue Render  >")
        self.bt_render.Size = Eto.Drawing.Size(220, 40)
        # Eto Button has limited theming support across builds; defensively
        # apply accent + bold font when the API is available.
        try:
            self.bt_render.Font = Eto.Drawing.Font(Eto.Drawing.SystemFont.Bold, 12)
        except Exception:
            pass
        try:
            self.bt_render.BackgroundColor = _hex_to_color("#FFF39C12")
            self.bt_render.TextColor = _hex_to_color("#FFFFFFFF")
        except Exception:
            pass
        self.bt_render.Click += self._on_render
        bar.Add(self.bt_render)

        bar.EndHorizontal()
        panel.Content = bar
        return panel

    def _build_filter_bar(self):
        row = Eto.Forms.DynamicLayout()
        row.BeginHorizontal()
        self.gallery_header = Eto.Forms.Label(Text="History")
        self.gallery_header.Font = Eto.Drawing.Font(Eto.Drawing.SystemFont.Bold, 12)
        row.Add(self.gallery_header)
        self.gallery_count = Eto.Forms.Label(Text="loading...")
        self.gallery_count.TextColor = _hex_to_color("#CBCBCB")
        row.Add(self.gallery_count, xscale=True)
        # 2026-04-21 — Large-thumb toggle. Calls G.set_thumb_size() then
        # rebuilds the gallery so existing rows reload at the new size.
        self.cb_large_thumbs = Eto.Forms.CheckBox(Text="Large")
        # Default ON (2026-04-22) — matches the new G.THUMB_W/H default in
        # ai_render_gallery_module.py. Users can uncheck for compact rows.
        self.cb_large_thumbs.Checked = True
        self.cb_large_thumbs.ToolTip = "Show larger preview thumbnails (240x160)"
        self.cb_large_thumbs.CheckedChanged += self._on_large_thumbs_changed
        row.Add(self.cb_large_thumbs)
        self.cb_date_filter = Eto.Forms.DropDown()
        for label, _ in G.DATE_FILTERS:
            self.cb_date_filter.Items.Add(label)
        self.cb_date_filter.SelectedIndex = [l for l, _ in G.DATE_FILTERS].index(G.DEFAULT_DATE_FILTER)
        self.cb_date_filter.SelectedIndexChanged += self._on_date_filter_changed
        row.Add(self.cb_date_filter)
        self.tbox_search = Eto.Forms.TextBox()
        self.tbox_search.PlaceholderText = "search prompt or view"
        self.tbox_search.Size = Eto.Drawing.Size(160, 22)
        self.tbox_search.TextChanged += self._on_search_changed
        row.Add(self.tbox_search)
        bt_refresh = Eto.Forms.Button(Text="⟳ Refresh")
        bt_refresh.Click += self._on_refresh_gallery
        row.Add(bt_refresh)
        self.bt_active_jobs = Eto.Forms.Button(Text="Active jobs (0)")
        self.bt_active_jobs.Click += self._on_scroll_to_active
        row.Add(self.bt_active_jobs)
        self.bt_resume = Eto.Forms.Button(Text="Resume (auth paused)")
        self.bt_resume.Click += self._on_resume
        self.bt_resume.Visible = False
        row.Add(self.bt_resume)
        row.EndHorizontal()
        return row

    def _build_gallery_panel(self):
        # Scrollable wrapping a vertical StackLayout of GalleryRowPanel widgets.
        # (Per Review #1 — Eto.GridView's per-row variable layout is awkward.)
        self._rows_layout = Eto.Forms.StackLayout()
        self._rows_layout.Orientation = Eto.Forms.Orientation.Vertical
        self._rows_layout.HorizontalContentAlignment = Eto.Forms.HorizontalAlignment.Stretch
        self._rows_layout.Spacing = 1
        self._rows_layout.Padding = Eto.Drawing.Padding(2)

        self._scroll = Eto.Forms.Scrollable()
        self._scroll.Content = self._rows_layout
        self._scroll.Border = Eto.Forms.BorderType.Line
        return self._scroll

    def _build_footer(self):
        row = Eto.Forms.DynamicLayout()
        # 2026-04-21 — gap between adjacent controls so labels don't abut
        # ("Auto-save to Gallery0B cached" / "Open Output FolderQuota:" was
        # unreadable in user screenshot).
        row.Spacing = Eto.Drawing.Size(10, 0)
        row.Padding = Eto.Drawing.Padding(2, 4, 2, 4)
        row.BeginHorizontal()
        self.cb_auto_save = Eto.Forms.CheckBox(Text="Auto-save to Gallery")
        self.cb_auto_save.Checked = True
        self.cb_auto_save.CheckedChanged += self._on_auto_save_changed
        self.cb_auto_save.ToolTip = (
            "Saves every new render to your cloud Gallery (visible from web "
            "Studio, Revit, Rhino, mobile). Applies to newly-queued renders "
            "only - in-flight jobs keep their setting. Turn OFF to keep this "
            "render local-only (won't appear on other devices).")
        row.Add(self.cb_auto_save)
        # Cache label is clickable — opens manage-cache modal (Round 3 P1-parity
        # with Revit fix #16; Rhino missed this in Round 2).
        self.cache_size_label = Eto.Forms.LinkButton(Text="—")
        self.cache_size_label.TextColor = _hex_to_color("#9A9A9A")
        self.cache_size_label.ToolTip = "Click to manage local gallery cache (clearing is safe — cloud copy is canonical)"
        self.cache_size_label.Click += self._on_manage_cache
        row.Add(self.cache_size_label, xscale=True)
        bt_open_folder = Eto.Forms.Button(Text="Open Output Folder")
        bt_open_folder.Click += self._on_open_folder
        row.Add(bt_open_folder)
        self.quota_label = Eto.Forms.Label(Text="Quota: —")
        self.quota_label.TextColor = _hex_to_color("#9A9A9A")
        row.Add(self.quota_label)
        row.EndHorizontal()
        return row

    # ------------------------------------------------------------------
    # Lifecycle
    # ------------------------------------------------------------------

    def _on_closed(self, sender, e):
        self._form_closed = True
        try:
            self._tick_timer.Stop()
        except Exception:
            pass
        try:
            if self._auto_cap_timer is not None:
                self._auto_cap_timer.Stop()
        except Exception:
            pass
        # Unsubscribe DisplayPipeline event so we don't leak a handler that
        # keeps firing after the form is gone (would call _capture_view
        # against a disposed Eto control and likely crash Rhino).
        try:
            if self._draw_handler is not None:
                Rhino.Display.DisplayPipeline.PostDrawObjects -= self._draw_handler
        except Exception:
            pass
        try:
            self._image_worker.stop()
            self._video_worker.stop()
        except Exception:
            pass
        # Identity check — only clear sticky if it still points to us
        # (prevents close+reopen race from clobbering a freshly-created form).
        if sc.sticky.has_key("EA_AI_RENDER_FORM") and sc.sticky["EA_AI_RENDER_FORM"] is self:
            sc.sticky.Remove("EA_AI_RENDER_FORM")

    # ------------------------------------------------------------------
    # Preferences (2026-04-28) — write-through helpers used by every
    # checkbox / dropdown handler so the next session restores state.
    # ------------------------------------------------------------------

    def _save_pref(self, key, value):
        try:
            self._prefs[key] = value
            _save_prefs(self._prefs)
        except Exception:
            pass

    def _on_size_changed(self, sender, e):
        # Persist last user-resized window so it reopens at their preferred
        # dimensions; gallery height was the chief complaint at 780px.
        if self._form_closed:
            return
        try:
            sz = self.Size
            self._save_pref("window_w", int(sz.Width))
            self._save_pref("window_h", int(sz.Height))
        except Exception:
            pass

    # ------------------------------------------------------------------
    # Auto-capture on camera change (2026-04-28)
    # ------------------------------------------------------------------

    def _on_auto_capture_btn_click(self, sender, e):
        # Toggle state, persist, repaint.
        self._auto_capture_enabled = not bool(self._auto_capture_enabled)
        self._auto_capture_btn_state = self._auto_capture_enabled
        self._save_pref("auto_capture", self._auto_capture_enabled)
        # Reset the camera baseline so toggling ON doesn't immediately fire
        # against a now-stale signature from before the user enabled it.
        self._last_cam_signature = self._cam_signature_for_active_view()
        self._apply_auto_capture_visual()

    def _apply_auto_capture_visual(self):
        """Paint the auto-capture button to make ON/OFF unmistakable.
        Text changes between 'Auto: ON' (with bullet) and 'Auto: OFF';
        background flips to accent orange when ON. Color setters are
        wrapped because some Eto builds don't honor them on Button."""
        on = bool(self._auto_capture_enabled)
        try:
            self.cb_auto_capture.Text = "● Auto: ON" if on else "Auto: OFF"
        except Exception:
            pass
        try:
            if on:
                self.cb_auto_capture.BackgroundColor = _hex_to_color("#FFF39C12")
                self.cb_auto_capture.TextColor = _hex_to_color("#FFFFFFFF")
            else:
                # Default-ish dark button look.
                self.cb_auto_capture.BackgroundColor = _hex_to_color("#FF3A3A3A")
                self.cb_auto_capture.TextColor = _hex_to_color("#FFCBCBCB")
        except Exception:
            pass

    def _cam_signature_for_active_view(self):
        try:
            view = sc.doc.Views.ActiveView
            if view is None:
                return None
            return self._cam_signature(view.ActiveViewport)
        except Exception:
            return None

    def _cam_signature(self, vp):
        # Round to 2 decimals — sub-millimeter jitter shouldn't trigger
        # captures, and floating-point noise would otherwise look like
        # constant motion to the diff check.
        try:
            loc = vp.CameraLocation
            tgt = vp.CameraTarget
            return "{:.2f},{:.2f},{:.2f}|{:.2f},{:.2f},{:.2f}".format(
                loc.X, loc.Y, loc.Z, tgt.X, tgt.Y, tgt.Z)
        except Exception:
            return None

    def _on_post_draw(self, sender, e):
        """Fires per viewport redraw. Cheap when nothing changes (Rhino only
        emits these during scene/view updates). Diffs camera signature, then
        debounces via a 1.2s one-shot Eto timer so a continuous spin produces
        ONE capture after the user lets go, not 60 per second."""
        if self._form_closed or not self._auto_capture_enabled:
            return
        try:
            view = sc.doc.Views.ActiveView
            if view is None:
                return
            # Filter to active viewport — we don't want every floating
            # detail view in the doc to retrigger.
            if e.Viewport.Id != view.ActiveViewport.Id:
                return
            sig = self._cam_signature(e.Viewport)
            if sig is None or sig == self._last_cam_signature:
                return
            self._last_cam_signature = sig
            # Marshal timer manipulation onto the UI thread; PostDrawObjects
            # runs on Rhino's display thread.
            self._invoke_ui(self._restart_auto_capture_timer)
        except Exception:
            pass

    def _restart_auto_capture_timer(self):
        if self._form_closed:
            return
        if self._auto_cap_timer is None:
            self._auto_cap_timer = Eto.Forms.UITimer()
            # 2026-04-28 — debounce 1.2s -> 0.3s after user reported the
            # auto-update felt laggy. Short enough that it fires almost
            # immediately when the user lets go of the camera, long enough
            # that a brief mid-orbit pause doesn't burn a capture.
            self._auto_cap_timer.Interval = 0.3
            self._auto_cap_timer.Elapsed += self._on_auto_capture_fire
        try:
            self._auto_cap_timer.Stop()
            self._auto_cap_timer.Start()
        except Exception:
            pass

    def _on_auto_capture_fire(self, sender, e):
        try:
            self._auto_cap_timer.Stop()
        except Exception:
            pass
        if self._form_closed or not self._auto_capture_enabled:
            return
        # In-flight guard: capture at high res (e.g. 2048 px) takes hundreds
        # of ms for ViewCapture + JPEG save + preview reload. If the timer
        # fires again while we're still mid-save, skip — the next camera
        # change will retrigger anyway and we won't fall behind.
        if self._capturing:
            return
        try:
            self._capture_view()
        except Exception:
            pass

    def _invoke_ui(self, fn):
        # Two race windows to guard:
        # 1. Form may close between this check and AsyncInvoke being scheduled.
        # 2. Form may close between scheduling and the dispatcher actually
        #    running our lambda — by which point Eto controls are disposed
        #    and `setattr(self.bt_X, 'Text', ...)` raises ObjectDisposedException
        #    inside the WndProc, which Rhino propagates as a hard crash.
        # Re-check inside the dispatched lambda AND swallow any exception so
        # post-close callbacks can never reach the native message loop.
        # (2026-04-21 audit P0-3.)
        if self._form_closed:
            return
        def _safe():
            if self._form_closed:
                return
            try:
                fn()
            except Exception:
                pass
        try:
            Eto.Forms.Application.Instance.AsyncInvoke(System.Action(_safe))
        except Exception:
            pass

    def _on_tick(self, sender, e):
        """Diff against last tick — only rebuild when (status, progress, elapsed)
        actually changed. Mirrors the Revit fix from Round 1 to stop the
        1Hz full-rebuild perf hit on Rhino (Round 2 P0-perf-3)."""
        if self._form_closed:
            return
        Monitor.Enter(self._jobs_lock)
        try:
            current_state = tuple(
                (j.job_id, j.status, j.progress_pct, int(j.elapsed_sec()))
                for j in self._jobs
                if j.status == AI_RENDER.STATUS_ACTIVE)
        finally:
            Monitor.Exit(self._jobs_lock)
        if current_state != getattr(self, "_last_tick_state", None):
            self._last_tick_state = current_state
            self._rebuild_rows()

    # ------------------------------------------------------------------
    # Capture
    # ------------------------------------------------------------------

    def _on_capture(self, sender, e):
        self._capture_view()

    @ERROR_HANDLE.try_catch_error()
    def _capture_view(self):
        if self._capturing:
            return
        self._capturing = True
        try:
            self._capture_view_impl()
        finally:
            self._capturing = False

    def _capture_view_impl(self):
        view = sc.doc.Views.ActiveView
        if view is None:
            self.status_label.Text = "No active Rhino view to capture."
            return
        long_edge = self._current_long_edge()
        aspect = self._current_aspect()
        w, h = _compute_px(long_edge, aspect)

        # Capture at the requested resolution but NEVER mutate view.Size
        # (Bug-finder [P0-5-2] — old code stretched the actual viewport).
        capture = Rhino.Display.ViewCapture()
        capture.Width = w
        capture.Height = h
        capture.ScaleScreenItems = False
        capture.DrawAxes = False
        capture.DrawGrid = False
        capture.DrawGridAxes = False
        capture.TransparentBackground = False

        # Full ms — fixes folder collision on rapid double-click (Audit P1-runtime-2).
        session_ts = time.strftime("%Y%m%d-%H%M%S-") + str(int(time.time() * 1000))
        folder = os.path.join(FOLDER.DUMP_FOLDER, "EnneadTab_Ai_Rendering",
                              "capture_" + session_ts)
        if not os.path.exists(folder):
            os.makedirs(folder)
        target = os.path.join(folder, "Original.jpeg")

        try:
            bitmap = capture.CaptureToBitmap(view)
            try:
                bitmap.Save(target, System.Drawing.Imaging.ImageFormat.Jpeg)
            finally:
                bitmap.Dispose()
        except Exception as ex:
            self.status_label.Text = "Capture failed: {}".format(str(ex)[:150])
            return

        self._capture_path = target
        self._capture_view_name = view.ActiveViewport.Name

        bmp = G.bitmap_from_path(target, 300, 220)
        if bmp:
            self.capture_preview.Image = bmp
        self.preview_label.Text = "Captured: {}".format(self._capture_view_name)
        self.status_label.Text = "Ready. Click Queue Render to send."

    # ------------------------------------------------------------------
    # Resolution / aspect
    # ------------------------------------------------------------------

    def _on_resolution_changed(self, sender, e):
        self._update_resolution_hint()
        try:
            self._save_pref("resolution_idx", int(self.cb_resolution.SelectedIndex))
            self._save_pref("aspect_idx", int(self.cb_aspect.SelectedIndex))
        except Exception:
            pass

    def _update_resolution_hint(self):
        label = _items_text(self.cb_resolution, self.cb_resolution.SelectedIndex)
        asp = _items_text(self.cb_aspect, self.cb_aspect.SelectedIndex)
        long_edge = dict(RESOLUTION_OPTIONS)[label]
        w, h = _compute_px(long_edge, asp)
        self.resolution_hint.Text = "{} × {} ({} · {})".format(
            w, h, label.split(" ")[0], asp)

    def _current_long_edge(self):
        label = _items_text(self.cb_resolution, self.cb_resolution.SelectedIndex)
        return dict(RESOLUTION_OPTIONS)[label]

    def _current_aspect(self):
        return _items_text(self.cb_aspect, self.cb_aspect.SelectedIndex)

    # ------------------------------------------------------------------
    # Style preset dropdowns
    # ------------------------------------------------------------------

    def _load_presets_async(self):
        def worker(state):
            try:
                token = AUTH.get_token()
                presets = AI_RENDER.get_render_presets(token=token) or []
            except Exception:
                presets = []
            self._invoke_ui(lambda: self._apply_presets(presets))
        System.Threading.ThreadPool.QueueUserWorkItem(
            System.Threading.WaitCallback(worker))

    def _apply_presets(self, presets):
        self._presets = presets or []
        if not self._presets:
            self.cb_category.Items.Clear()
            self.cb_category.Items.Add("(Presets unavailable — check connection)")
            self.cb_category.SelectedIndex = 0
            self.cb_style.Items.Clear()
            return
        cats = []
        seen = set()
        for p in self._presets:
            c = p.get("category") or "Other"
            if c not in seen:
                seen.add(c)
                cats.append(c)
        cats.sort()
        self._categories = cats
        self.cb_category.Items.Clear()
        self.cb_category.Items.Add("All")
        for c in cats:
            self.cb_category.Items.Add(c)
        # Restore last category from prefs (2026-04-28). Falls back to "All"
        # if the saved category no longer exists in the curated list.
        saved_cat = self._prefs.get("category_text") if self._prefs else None
        cat_idx = 0
        if saved_cat:
            for i in range(self.cb_category.Items.Count):
                if _items_text(self.cb_category, i) == saved_cat:
                    cat_idx = i
                    break
        self.cb_category.SelectedIndex = cat_idx
        self._refresh_style_list()

    def _refresh_style_list(self):
        self.cb_style.Items.Clear()
        idx = self.cb_category.SelectedIndex
        if idx <= 0:
            self._filtered_presets = list(self._presets)
        else:
            cat = _items_text(self.cb_category, idx)
            self._filtered_presets = [p for p in self._presets if p.get("category") == cat]
        for p in self._filtered_presets:
            self.cb_style.Items.Add(p.get("name") or "?")
        # Hover tooltip listing every preset in the current category
        # with its first-line preview. Same rationale as cb_my_prompts:
        # users don't have to click each one to remember what it does.
        try:
            self.cb_style.ToolTip = self._build_prompt_list_tooltip(
                self._filtered_presets,
                "Rendering styles in this category")
        except Exception:
            pass
        if self._filtered_presets:
            # Restore last style from prefs (2026-04-28). Falls back to first
            # entry if the saved name isn't in the current category's list.
            saved_style = self._prefs.get("style_text") if self._prefs else None
            style_idx = 0
            if saved_style:
                for i in range(self.cb_style.Items.Count):
                    if _items_text(self.cb_style, i) == saved_style:
                        style_idx = i
                        break
            self.cb_style.SelectedIndex = style_idx
            sel = self._filtered_presets[style_idx]
            first_prompt = sel.get("prompt", "")
            if not (self.tbox_prompt.Text or "").strip():
                self.tbox_prompt.Text = first_prompt
                self._initial_prompt_for_reset = first_prompt

    def _on_interior_changed(self, sender, e):
        try:
            self._save_pref("interior", bool(self.cb_interior.Checked))
        except Exception:
            pass

    def _on_category_changed(self, sender, e):
        self._refresh_style_list()
        try:
            self._save_pref("category_text",
                            _items_text(self.cb_category, self.cb_category.SelectedIndex))
        except Exception:
            pass

    def _on_style_changed(self, sender, e):
        idx = self.cb_style.SelectedIndex
        if 0 <= idx < len(self._filtered_presets):
            new_prompt = self._filtered_presets[idx].get("prompt", "")
            self._push_prompt_undo()
            self.tbox_prompt.Text = new_prompt
            self._initial_prompt_for_reset = new_prompt
        try:
            self._save_pref("style_text",
                            _items_text(self.cb_style, self.cb_style.SelectedIndex))
        except Exception:
            pass

    # ------------------------------------------------------------------
    # Prompt action buttons
    # ------------------------------------------------------------------

    def _push_prompt_undo(self):
        cur = self.tbox_prompt.Text
        if not cur:
            return
        self._prompt_undo.append(cur)
        if len(self._prompt_undo) > PROMPT_UNDO_CAP:
            self._prompt_undo = self._prompt_undo[-PROMPT_UNDO_CAP:]
        self.bt_undo_prompt.Enabled = True

    def _on_undo_prompt(self, sender, e):
        if not self._prompt_undo:
            self.bt_undo_prompt.Enabled = False
            return
        prev = self._prompt_undo.pop()
        self.tbox_prompt.Text = prev
        if not self._prompt_undo:
            self.bt_undo_prompt.Enabled = False

    def _on_reset_prompt(self, sender, e):
        self._push_prompt_undo()
        self.tbox_prompt.Text = self._initial_prompt_for_reset or ""

    def _run_prompt_api(self, btn, api_fn, action_name):
        prompt = (self.tbox_prompt.Text or "").strip()
        if not prompt:
            self.status_label.Text = "Nothing to {}.".format(action_name.lower())
            return
        btn.Enabled = False
        old_text = btn.Text
        btn.Text = "…"
        self._push_prompt_undo()
        self.status_label.Text = "{}...".format(action_name)

        def _safe_unicode(v):
            # 2026-04-28 — IronPython 2.7's json.loads can return Python
            # `str` (bytes) for ASCII-only JSON strings; setting that as
            # Eto TextArea.Text triggers bytes->unicode coercion via
            # sys.getdefaultencoding() (= "unknown" on Windows non-en-US),
            # which dies on UTF-8 multibyte sequences (e.g. byte 0xE7 in
            # the middle of an em-dash or curly quote the AI added). Same
            # class for str(ex) when the .NET exception Message has
            # non-ASCII chars. Force-decode here so the boundary is safe.
            if v is None:
                return u""
            if isinstance(v, bytes):
                try:
                    return v.decode("utf-8")
                except Exception:
                    try:
                        return v.decode("utf-8", "replace")
                    except Exception:
                        return v.decode("latin-1", "replace")
            try:
                return unicode(v)
            except Exception:
                try:
                    return v.encode("utf-8", "replace").decode("utf-8", "replace")
                except Exception:
                    return u""

        def worker(state):
            token = AUTH.get_token()
            if not token:
                self._invoke_ui(lambda: setattr(self.status_label, 'Text',
                                                "Sign in required."))
                self._invoke_ui(lambda: self._restore_btn(btn, old_text))
                return
            try:
                new_text = _safe_unicode(api_fn(token, prompt))
                self._invoke_ui(lambda: setattr(self.tbox_prompt, 'Text', new_text))
                self._invoke_ui(lambda: setattr(self.status_label, 'Text',
                                                "{} applied.".format(action_name)))
            except Exception as ex:
                err_text = _safe_unicode(ex)[:200]
                self._invoke_ui(lambda: setattr(self.status_label, 'Text',
                                                u"{} failed: {}".format(action_name, err_text)))
            finally:
                self._invoke_ui(lambda: self._restore_btn(btn, old_text))
        System.Threading.ThreadPool.QueueUserWorkItem(
            System.Threading.WaitCallback(worker))

    def _restore_btn(self, btn, old_text):
        btn.Enabled = True
        btn.Text = old_text

    def _on_spell(self, sender, e):
        self._run_prompt_api(self.bt_spell,
                             lambda tok, p: AI_CHAT.spell_check_with_token(tok, p),
                             "Spell check")

    def _on_lengthen(self, sender, e):
        is_int = bool(self.cb_interior.Checked)
        self._run_prompt_api(self.bt_lengthen,
                             lambda tok, p: AI_CHAT.improve_prompt_with_token(
                                 tok, p, mode="image", action="improve", is_interior=is_int),
                             "Lengthen")

    def _on_shorten(self, sender, e):
        self._run_prompt_api(self.bt_shorten,
                             lambda tok, p: AI_CHAT.improve_prompt_with_token(
                                 tok, p, mode="image", action="summarize"),
                             "Shorten")

    # ------------------------------------------------------------------
    # Style reference
    # ------------------------------------------------------------------

    def _on_browse_style(self, sender, e):
        dlg = Eto.Forms.OpenFileDialog()
        dlg.Filters.Add(Eto.Forms.FileFilter("Images", ".png", ".jpg", ".jpeg", ".webp"))
        if dlg.ShowDialog(self) == Eto.Forms.DialogResult.Ok:
            self._set_style_ref(dlg.FileName)

    def _on_paste_style(self, sender, e):
        try:
            clipboard = Eto.Forms.Clipboard()
            if not clipboard.ContainsImage:
                self.status_label.Text = "No image in clipboard."
                return
            tmp_name = "clip_{}.png".format(int(time.time() * 1000))
            temp_path = os.path.join(FOLDER.DUMP_FOLDER, tmp_name)
            if not os.path.exists(FOLDER.DUMP_FOLDER):
                os.makedirs(FOLDER.DUMP_FOLDER)
            eto_img = clipboard.Image
            # Eto API rename — Rhino 7 uses ToSystemDrawing, newer uses ToSD.
            ext = Rhino.UI.EtoExtensions
            converter = getattr(ext, "ToSD", None) or getattr(ext, "ToSystemDrawing", None)
            if converter is None:
                self.status_label.Text = "Clipboard paste not supported on this Rhino version."
                return
            sys_bmp = converter(eto_img)
            try:
                sys_bmp.Save(temp_path, System.Drawing.Imaging.ImageFormat.Png)
            finally:
                sys_bmp.Dispose()
            self._set_style_ref(temp_path)
        except Exception as ex:
            self.status_label.Text = "Paste failed: {}".format(str(ex)[:150])

    def _on_library_style(self, sender, e):
        self.status_label.Text = "Loading style library..."
        def worker(state):
            # 2026-04-21 — .NET worker exception = process termination. Wrap
            # EVERYTHING in try/except. Audit Lens B, P0. Mirrored in Revit.
            try:
                token = AUTH.get_token()
                if not token:
                    self._invoke_ui(lambda: setattr(self.status_label, 'Text',
                                                    "Sign in required."))
                    return
                items = AI_RENDER.get_demo_style_images(token)
                self._invoke_ui(lambda: self._show_library_picker(items))
            except Exception as ex:
                _trace("worker.library_style SWALLOWED {}".format(ex))
                self._invoke_ui(lambda: setattr(self.status_label, 'Text',
                                                "Style library failed: {}".format(str(ex)[:120])))
        System.Threading.ThreadPool.QueueUserWorkItem(
            System.Threading.WaitCallback(worker))

    def _show_library_picker(self, items):
        """Thumbnail grid (4 columns) of curated Ennead style refs.

        Eto DynamicLayout filled with ImageView buttons. Thumbnails fill
        from cache on a background thread so the modal opens instantly.
        """
        if not items:
            self.status_label.Text = "Style library is empty or unavailable."
            return
        dlg = Eto.Forms.Dialog()
        dlg.Title = "Ennead Style Reference Library ({})".format(len(items))
        dlg.Size = Eto.Drawing.Size(720, 540)

        scroll = Eto.Forms.Scrollable()
        grid = Eto.Forms.DynamicLayout()
        grid.Spacing = Eto.Drawing.Size(6, 6)
        grid.Padding = Eto.Drawing.Padding(8)

        cols = 4
        tiles = []  # list of (item, image_view)
        for i in range(0, len(items), cols):
            row_items = items[i:i+cols]
            grid.BeginHorizontal()
            for item in row_items:
                tile = Eto.Forms.DynamicLayout()
                iv = Eto.Forms.ImageView()
                iv.Size = Eto.Drawing.Size(160, 100)
                tile.Add(iv)
                lbl = Eto.Forms.Label(Text=item["filename"][:24])
                lbl.TextColor = _hex_to_color("#CBCBCB")
                tile.Add(lbl)
                # Click handler — left-button only (Round 3 P2-2 — no filter
                # meant right-click also fired download). Closes modal on
                # success OR failure so user isn't stuck staring at the picker
                # if the network drops mid-download.
                def on_click(s, a, it=item):
                    if a.Buttons != Eto.Forms.MouseButtons.Primary:
                        return
                    self.status_label.Text = "Selected {}".format(it["filename"])
                    def dl_worker(state, it=it):
                        try:
                            path = AI_RENDER.get_or_cache_demo_style_image(
                                it["url"], it["filename"])
                            self._invoke_ui(lambda: self._set_style_ref(path))
                        except Exception as ex:
                            self._invoke_ui(lambda: setattr(self.status_label, 'Text',
                                                            "Download failed: {}".format(str(ex)[:150])))
                        finally:
                            self._invoke_ui(lambda: dlg.Close())
                    System.Threading.ThreadPool.QueueUserWorkItem(
                        System.Threading.WaitCallback(dl_worker))
                iv.MouseDown += on_click
                tiles.append((item, iv))
                grid.Add(tile)
            grid.EndHorizontal()

        scroll.Content = grid
        dlg.Content = scroll

        # Background-fill thumbnails from cache (downloads on miss).
        def fill_worker(state):
            for item, iv in tiles:
                try:
                    path = AI_RENDER.get_or_cache_demo_style_image(
                        item["url"], item["filename"])
                    bmp = G.bitmap_from_path(path, 160, 100)
                    if bmp is not None:
                        self._invoke_ui(lambda im=iv, b=bmp: setattr(im, "Image", b))
                except Exception:
                    continue
        System.Threading.ThreadPool.QueueUserWorkItem(
            System.Threading.WaitCallback(fill_worker))

        dlg.ShowModal(self)

    def _on_clear_style(self, sender, e):
        self._style_ref_path = None
        self.style_preview.Image = None
        self.bt_clear_style.Visible = False
        self.status_label.Text = "Style reference cleared."

    def _set_style_ref(self, path):
        self._style_ref_path = path
        bmp = G.bitmap_from_path(path, 120, 92)
        if bmp:
            self.style_preview.Image = bmp
        self.bt_clear_style.Visible = True
        self.status_label.Text = "Style reference: {}".format(os.path.basename(path))

    # ------------------------------------------------------------------
    # My Prompts
    # ------------------------------------------------------------------

    def _set_status(self, msg):
        """Set status_label text from any thread context (when wrapped
        in _invoke_ui) or directly from the UI thread. Phase B1 helper
        - mirrors the dozens of existing direct status_label.Text=...
        sites without introducing a stringly-typed setattr pattern.
        """
        try:
            self.status_label.Text = msg
        except Exception:
            pass

    def _refresh_my_prompts_async(self):
        token = AUTH.get_token()
        if not token:
            self._set_status(
                "My prompts unavailable - sign in or check connection.")
            return
        def worker(state):
            # 2026-04-21 — .NET worker exception = host process termination.
            # Audit Lens B P0. Mirrored in Revit.
            try:
                prompts = AI_RENDER.list_prompts_with_token(token)
                self._invoke_ui(lambda: self._apply_my_prompts(prompts))
            except Exception as ex:
                _trace("worker.my_prompts SWALLOWED {}".format(ex))
                # Phase B1 2026-04-30: surface coherent error instead of silent no-op
                self._invoke_ui(lambda: self._set_status(
                    "My prompts unavailable - check connection."))
        System.Threading.ThreadPool.QueueUserWorkItem(
            System.Threading.WaitCallback(worker))

    def _apply_my_prompts(self, prompts):
        self._my_prompts = prompts or []
        self.cb_my_prompts.Items.Clear()
        if not self._my_prompts:
            self.cb_my_prompts.Items.Add("(none — click Save current...)")
            self.cb_my_prompts.SelectedIndex = 0
            self.cb_my_prompts.Enabled = False
            try:
                self.cb_my_prompts.ToolTip = (
                    "No saved prompts yet. Edit the prompt textbox, then "
                    "click 'Save current' to add one.")
            except Exception:
                pass
            return
        self.cb_my_prompts.Enabled = True
        self.cb_my_prompts.Items.Add("— select a saved prompt —")
        for p in self._my_prompts:
            label = p.get("name") or "(unnamed)"
            cat = p.get("category")
            if cat:
                label = "{} · {}".format(label, cat)
            self.cb_my_prompts.Items.Add(label)
        self.cb_my_prompts.SelectedIndex = 0
        # 2026-04-28 — Eto's ComboBox doesn't support per-item hover
        # tooltips, but we can stuff a multi-line preview list into the
        # control's overall ToolTip. Hovering the dropdown trigger now
        # surfaces every saved prompt's name + first-line preview so
        # users don't have to click each one to remember what it says.
        try:
            self.cb_my_prompts.ToolTip = self._build_prompt_list_tooltip(
                self._my_prompts, "Saved prompts")
        except Exception:
            pass

    def _build_prompt_list_tooltip(self, items, header):
        """Format a list of {name, prompt, category?} dicts into a
        multi-line tooltip string. Each line: 'NAME — first ~120 chars'."""
        lines = ["{} ({}):".format(header, len(items)), ""]
        max_per_line = 120
        max_items = 30  # avoid a tooltip that's taller than the screen
        for p in items[:max_items]:
            name = (p.get("name") or "(unnamed)").strip()
            text = (p.get("prompt") or "").strip().replace("\n", " ")
            if len(text) > max_per_line:
                text = text[:max_per_line].rstrip() + "..."
            cat = p.get("category")
            if cat:
                lines.append(u"• {} [{}]".format(name, cat))
            else:
                lines.append(u"• {}".format(name))
            if text:
                lines.append(u"   {}".format(text))
        if len(items) > max_items:
            lines.append("")
            lines.append("... and {} more".format(len(items) - max_items))
        return u"\n".join(lines)

    def _on_browse_my_prompts(self, sender, e):
        """Open the modal prompt browser for saved prompts."""
        if not self._my_prompts:
            self.status_label.Text = (
                "No saved prompts yet — edit the prompt then click Save current.")
            return
        def _on_pick(idx):
            if 0 <= idx < len(self._my_prompts):
                chosen = self._my_prompts[idx]
                text = chosen.get("prompt") or ""
                if text:
                    self._push_prompt_undo()
                    self.tbox_prompt.Text = text
                    self.status_label.Text = u"Loaded prompt: {}".format(
                        chosen.get("name") or "")
        self._show_prompt_browser_modal(
            self._my_prompts, "Browse Saved Prompts", _on_pick)

    def _show_prompt_browser_modal(self, items, title, on_select):
        """Modal picker with a name list (left) and live full-prompt
        preview pane (right). 2026-04-28 — built because Eto ComboBox
        tooltips don't render on this Rhino build, so the multi-line
        tooltip preview attempt was invisible."""
        try:
            dlg = Eto.Forms.Dialog()
            dlg.Title = title
            dlg.Padding = Eto.Drawing.Padding(10)
            dlg.Resizable = True
            try:
                dlg.Size = Eto.Drawing.Size(900, 560)
                dlg.MinimumSize = Eto.Drawing.Size(640, 400)
            except Exception:
                pass

            state = {"idx": 0 if items else -1}

            row = Eto.Forms.DynamicLayout()
            row.Spacing = Eto.Drawing.Size(10, 0)
            row.BeginHorizontal()

            # Left column: list of names + categories
            listbox = Eto.Forms.ListBox()
            try:
                listbox.Width = 280
            except Exception:
                pass
            for p in items:
                item = Eto.Forms.ListItem()
                name = p.get("name") or "(unnamed)"
                cat = p.get("category")
                item.Text = u"{}  [{}]".format(name, cat) if cat else name
                listbox.Items.Add(item)

            # Right column: name header + scrollable full prompt preview
            right = Eto.Forms.DynamicLayout()
            right.Spacing = Eto.Drawing.Size(0, 6)
            lbl_name = Eto.Forms.Label(Text="")
            try:
                lbl_name.Font = Eto.Drawing.Font(
                    Eto.Drawing.SystemFont.Bold, 13)
                lbl_name.TextColor = _hex_to_color("#FFE59C")
            except Exception:
                pass
            right.Add(lbl_name)

            preview = Eto.Forms.TextArea()
            try:
                preview.ReadOnly = True
                preview.Wrap = True
                preview.Font = Eto.Drawing.Font(
                    Eto.Drawing.SystemFont.Default, 11)
            except Exception:
                pass
            right.Add(preview, yscale=True)

            def _refresh_preview(idx):
                if 0 <= idx < len(items):
                    p = items[idx]
                    lbl_name.Text = p.get("name") or "(unnamed)"
                    preview.Text = p.get("prompt") or ""
                else:
                    lbl_name.Text = ""
                    preview.Text = ""

            def _on_sel_changed(s, ev):
                state["idx"] = listbox.SelectedIndex
                _refresh_preview(state["idx"])
            listbox.SelectedIndexChanged += _on_sel_changed

            row.Add(listbox)
            row.Add(right, xscale=True)
            row.EndHorizontal()
            dlg.Content = row

            # Buttons via Dialog's positive/negative slots so Enter/Esc work.
            bt_ok = Eto.Forms.Button(Text="Load Prompt")
            def _on_ok(s, ev):
                if state["idx"] >= 0:
                    try:
                        on_select(state["idx"])
                    except Exception as ex:
                        _trace("browser on_select failed: " + str(ex))
                dlg.Close()
            bt_ok.Click += _on_ok
            dlg.DefaultButton = bt_ok
            dlg.PositiveButtons.Add(bt_ok)

            bt_cancel = Eto.Forms.Button(Text="Cancel")
            bt_cancel.Click += lambda s, ev: dlg.Close()
            dlg.AbortButton = bt_cancel
            dlg.NegativeButtons.Add(bt_cancel)

            # Pre-select first item.
            if items:
                listbox.SelectedIndex = 0
                _refresh_preview(0)

            dlg.ShowModal(self)
        except Exception as ex:
            _trace("browser dialog FAILED: " + str(ex))
            self.status_label.Text = u"Browser failed: {}".format(str(ex)[:120])

    def _on_my_prompt_changed(self, sender, e):
        idx = self.cb_my_prompts.SelectedIndex
        if idx <= 0 or idx > len(self._my_prompts):
            return
        chosen = self._my_prompts[idx - 1]
        text = chosen.get("prompt") or ""
        if text:
            self._push_prompt_undo()
            self.tbox_prompt.Text = text
            self.status_label.Text = "Loaded prompt: {}".format(chosen.get("name") or "")

    def _on_save_prompt(self, sender, e):
        prompt_text = (self.tbox_prompt.Text or "").strip()
        if not prompt_text:
            self.status_label.Text = "Nothing to save."
            return
        # Eto's input dialog
        name = self._prompt_for_text("Save prompt", "Name this prompt:", "")
        if not name:
            return
        token = AUTH.get_token()
        if not token:
            self.status_label.Text = "Sign in required."
            return
        idx = self.cb_style.SelectedIndex
        category = None
        if 0 <= idx < len(self._filtered_presets):
            category = self._filtered_presets[idx].get("category")
        def worker(state):
            try:
                AI_RENDER.save_prompt_with_token(token, name, prompt_text, category=category)
                self._invoke_ui(lambda: setattr(self.status_label, 'Text',
                                                "Saved prompt '{}'".format(name)))
                self._invoke_ui(self._refresh_my_prompts_async)
            except Exception as ex:
                self._invoke_ui(lambda: setattr(self.status_label, 'Text',
                                                "Save failed: {}".format(str(ex)[:200])))
        System.Threading.ThreadPool.QueueUserWorkItem(
            System.Threading.WaitCallback(worker))

    def _prompt_for_text(self, title, label_text, default=""):
        dlg = Eto.Forms.Dialog()
        dlg.Title = title
        dlg.Size = Eto.Drawing.Size(360, 140)
        layout = Eto.Forms.DynamicLayout()
        layout.Padding = Eto.Drawing.Padding(10)
        layout.Add(Eto.Forms.Label(Text=label_text))
        tb = Eto.Forms.TextBox()
        tb.Text = default
        layout.Add(tb)
        result = [None]
        ok = Eto.Forms.Button(Text="OK")
        cancel = Eto.Forms.Button(Text="Cancel")
        def on_ok(s, a):
            txt = (tb.Text or "").strip()
            result[0] = txt if txt else None
            dlg.Close()
        ok.Click += on_ok
        cancel.Click += lambda s, a: dlg.Close()
        layout.AddSeparateRow(None, ok, cancel)
        dlg.Content = layout
        dlg.ShowModal(self)
        return result[0]

    # ------------------------------------------------------------------
    # Queue Render
    # ------------------------------------------------------------------

    @ERROR_HANDLE.try_catch_error()
    def _on_render(self, sender, e):
        # 2026-04-21 — Queue Render is the active crash surface. Trace each
        # step to %APPDATA%/EnneadTab/ai_render_trace.log so the next crash
        # leaves a breadcrumb trail showing exactly where execution died,
        # even if the failure is a native AccessViolation that no Python
        # exception handler can intercept. Remove the trace once stable.
        _trace("Queue.START")
        if not self._capture_path or not os.path.exists(self._capture_path):
            self.status_label.Text = "Capture a view first."
            _trace("Queue.ABORT no_capture")
            return
        prompt = (self.tbox_prompt.Text or "").strip()
        if not prompt:
            self.status_label.Text = "Enter a prompt."
            _trace("Queue.ABORT no_prompt")
            return
        if not AI_RENDER.can_enqueue(self._jobs, self._jobs_lock):
            self.status_label.Text = "Queue full ({} active).".format(AI_RENDER.ACTIVE_CAP)
            _trace("Queue.ABORT queue_full")
            return
        _trace("Queue.preflight_ok prompt_len={} style_idx={}".format(
            len(prompt), self.cb_style.SelectedIndex))
        style_name = ""
        idx = self.cb_style.SelectedIndex
        if 0 <= idx < len(self._filtered_presets):
            style_name = self._filtered_presets[idx].get("name") or ""

        _trace("Queue.before_RenderJob_init")
        job = AI_RENDER.RenderJob(
            original_path=None,
            prompt=prompt,
            style_preset=style_name,
            style_ref_path=self._style_ref_path,
            aspect_ratio=self._current_aspect(),
            long_edge=self._current_long_edge(),
            view_name=self._capture_view_name,
            is_interior=bool(self.cb_interior.Checked),
            kind=AI_RENDER.KIND_IMAGE,
            host="rhino",
            auto_save_gallery=self._auto_save_enabled)
        _trace("Queue.RenderJob_created job_id={}".format(job.job_id[:8]))
        snapshot = os.path.join(job.job_folder,
                                "original" + os.path.splitext(self._capture_path)[1])
        try:
            shutil.copy2(self._capture_path, snapshot)
        except Exception as ex:
            self.status_label.Text = "Snapshot failed: {}".format(ex)
            _trace("Queue.snapshot_FAILED {}".format(ex))
            return
        job.original_path = snapshot
        _trace("Queue.snapshot_ok size={} bytes".format(
            os.path.getsize(snapshot) if os.path.exists(snapshot) else -1))

        Monitor.Enter(self._jobs_lock)
        try:
            self._jobs.append(job)
        finally:
            Monitor.Exit(self._jobs_lock)
        _trace("Queue.before_worker_wake jobs_count={}".format(len(self._jobs)))
        self._image_worker.wake()
        _trace("Queue.after_worker_wake")
        self.status_label.Text = "Queued (job #{}).".format(job.job_id[:6])
        # Do NOT call self._rebuild_rows() here. The worker fires _on_job_update
        # → _invoke_ui(self._rebuild_rows) within milliseconds; calling it
        # synchronously creates a re-entry race against both that AsyncInvoke
        # AND the 1 Hz tick rebuild, which mutates StackLayout.Items from
        # multiple paths in one message-pump cycle and crashes Rhino on Eto's
        # native backend. (2026-04-21 audit P0-2.)
        self._update_active_jobs_label()
        _trace("Queue.END")

    def _on_job_update(self, job):
        # Worker thread — marshal to UI and check for pause state.
        _trace("on_job_update.START job={} status={}".format(
            getattr(job, "job_id", "?")[:8], getattr(job, "status", "?")))
        Monitor.Enter(self._jobs_lock)
        try:
            paused = any(
                j.status == AI_RENDER.STATUS_PENDING and j.error_msg
                and "auth" in (j.error_msg or "").lower()
                for j in self._jobs)
        finally:
            Monitor.Exit(self._jobs_lock)
        self._invoke_ui(self._rebuild_rows)
        self._invoke_ui(self._update_active_jobs_label)
        self._invoke_ui(lambda: setattr(self.bt_resume, 'Visible', paused))
        _trace("on_job_update.END job={}".format(getattr(job, "job_id", "?")[:8]))

    def _on_any_job_complete(self, job):
        self._invoke_ui(self._refresh_quota_async)
        Monitor.Enter(self._jobs_lock)
        try:
            still_going = any(j.status in (AI_RENDER.STATUS_PENDING, AI_RENDER.STATUS_ACTIVE)
                              for j in self._jobs)
        finally:
            Monitor.Exit(self._jobs_lock)
        if not still_going:
            AI_RENDER.play_completion_sound()

    def _on_resume(self, sender, e):
        AUTH.clear_token()
        if not AUTH.is_auth_in_progress():
            AUTH.request_auth()
        if AUTH.get_token():
            self._image_worker.resume()
            self._video_worker.resume()
            self.bt_resume.Visible = False
            self.status_label.Text = "Queue resumed."
        else:
            self.status_label.Text = "Sign in via the browser, then click Resume again."

    # ------------------------------------------------------------------
    # Gallery rebuild + filters
    # ------------------------------------------------------------------

    def _rebuild_rows(self):
        # Snapshot under lock, build rows OUTSIDE lock (no I/O while workers
        # are blocked) — Round 2 P0-perf-3 port from Revit.
        _trace("rebuild.START")
        Monitor.Enter(self._jobs_lock)
        try:
            jobs_snapshot = list(self._jobs)
        finally:
            Monitor.Exit(self._jobs_lock)
        _trace("rebuild.snapshot jobs={}".format(len(jobs_snapshot)))
        job_rows = [G.row_from_job(j) for j in jobs_snapshot]
        # Dedup: cloud rows whose ID matches a local job's gallery_id are
        # already on screen via the local job row (P0-state-2 from Round 2 —
        # was comparing job_id to cloud_id, never matched).
        local_gallery_ids = set(j.gallery_id for j in jobs_snapshot if j.gallery_id)
        cloud_only = [r for r in self._all_rows if r.cloud_item
                      and r.id not in local_gallery_ids]
        merged = G.filter_rows(job_rows + cloud_only,
                               self._filter_seconds, self._filter_query)
        _trace("rebuild.merged total={} job_rows={} cloud_only={}".format(
            len(merged), len(job_rows), len(cloud_only)))
        # Wholesale rebuild of the StackLayout — clear + add.
        try:
            self._rows_layout.Items.Clear()
            _trace("rebuild.cleared")
        except Exception as ex:
            _trace("rebuild.CLEAR_FAILED {}".format(ex))
            raise
        built = 0
        for i, r in enumerate(merged):
            try:
                # 2026-04-21 — factory pattern. Direct GalleryRowPanel(...)
                # call (positional or kwargs) hits IronPython's CLR-derived
                # constructor binder bug — args dispatch to the .NET base
                # Eto.Forms.Panel(content) instead of the Python __init__,
                # raising "takes at most 2 arguments (N given)" for every
                # row. Confirmed via trace 14:48: gallery rendered empty
                # while history count read 7. McNeel forum's canonical
                # workaround is .create() factory + zero-arg __init__.
                panel = GalleryRowPanel.create(
                    r,
                    self._row_view_original,
                    self._row_view_result,
                    self._row_save,
                    self._row_context_menu)
                self._rows_layout.Items.Add(Eto.Forms.StackLayoutItem(panel,
                                                                      Eto.Forms.HorizontalAlignment.Stretch))
                built += 1
            except Exception as ex:
                # Don't re-raise — leaving the StackLayout cleared-but-unfilled
                # is what kills Rhino on the next paint. Skip the bad row,
                # log it, and let the rest of the rebuild succeed so the UI
                # ends in a consistent state.
                _trace("rebuild.ROW_FAILED idx={} id={} {}".format(
                    i, getattr(r, "id", "?"), ex))
        # Show built/total so silent row-construction failures are visible.
        if built == len(merged):
            self.gallery_count.Text = "· {} items".format(len(merged))
        else:
            self.gallery_count.Text = "· {}/{} items (some failed)".format(
                built, len(merged))
        _trace("rebuild.END built={} of {}".format(built, len(merged)))

    def _refresh_gallery_async(self):
        token = AUTH.get_token()
        if not token:
            # Phase B1 2026-04-30: surface coherent error instead of silent no-op
            self._set_status(
                "Gallery unavailable - sign in or check connection.")
            return
        def on_done(rows):
            if rows is None:
                # Fetch failed (network or auth). Don't clear existing
                # rows on failure - just surface a status.
                self._invoke_ui(lambda: self._set_status(
                    "Gallery refresh failed - check connection."))
                return
            self._invoke_ui(lambda: self._apply_gallery_rows(rows))
        G.fetch_gallery_index_async(token, on_done, limit=500)

    def _apply_gallery_rows(self, rows):
        self._all_rows = rows
        self._history_loaded = True
        self._rebuild_rows()
        self._update_cache_size()

    def _render_skeleton_rows(self, count=4):
        """Show dimmed loading rows so an empty gallery during initial
        cloud-fetch doesn't look like 'you have nothing'. Replaced by
        real rows the moment _apply_gallery_rows fires (~0.5-3s after
        dialog open depending on network).

        2026-04-28 v2 — earlier version used Eto.Forms.Panel for
        placeholders, which doesn't paint BackgroundColor on this
        Rhino 8 build (same bug that hid the viewer's bar backgrounds).
        Switched to Scrollable-wrapped Label rows which DO paint.
        """
        try:
            self._rows_layout.Items.Clear()
            for i in range(count):
                placeholder = Eto.Forms.Scrollable()
                placeholder.BackgroundColor = _hex_to_color("#FF2A2A2A")
                try:
                    placeholder.Border = Eto.Forms.BorderType.None
                    placeholder.ExpandContentWidth = True
                    placeholder.ExpandContentHeight = True
                except Exception:
                    pass
                placeholder.Padding = Eto.Drawing.Padding(16, 28)
                placeholder.Height = 80
                # Honesty fix 2026-04-30: previously said "(1/4)"..(4/4)"
                # which read as 25%-stages of progress. It's just 4
                # identical placeholder rows - all say the same thing.
                label = Eto.Forms.Label(Text="Loading recent renders...")
                try:
                    label.TextColor = _hex_to_color("#FF6A6A6A")
                    label.Font = Eto.Drawing.Font(
                        Eto.Drawing.SystemFont.Default, 11)
                except Exception:
                    pass
                placeholder.Content = label
                self._rows_layout.Items.Add(
                    Eto.Forms.StackLayoutItem(
                        placeholder,
                        Eto.Forms.HorizontalAlignment.Stretch))
            try:
                self._rows_layout.Invalidate()
            except Exception:
                pass
            _trace("skeleton rendered {} placeholder rows".format(count))
        except Exception as ex:
            _trace("skeleton render failed: {}".format(ex))

    def _on_date_filter_changed(self, sender, e):
        idx = self.cb_date_filter.SelectedIndex
        if 0 <= idx < len(G.DATE_FILTERS):
            _, secs = G.DATE_FILTERS[idx]
            self._filter_seconds = secs
            self._rebuild_rows()

    def _on_search_changed(self, sender, e):
        self._filter_query = (self.tbox_search.Text or "").strip()
        self._rebuild_rows()

    @ERROR_HANDLE.try_catch_error()
    def _on_large_thumbs_changed(self, sender, e):
        # 2026-04-21 — Eto CheckBox.CheckedChanged fires on the UI thread;
        # any uncaught exception here escapes into the WPF/Eto message pump
        # as an unhandled managed exception (CLR 0xE0434352) and crashes
        # Rhino. Wrap in @ERROR_HANDLE.try_catch_error() AND hand all real
        # work off via _invoke_ui so the checkbox event handler returns
        # quickly — the actual rebuild happens on the next pump cycle
        # without re-entering from the event handler stack frame.
        _trace("large_thumbs.changed checked={}".format(
            bool(self.cb_large_thumbs.Checked)))
        try:
            if bool(self.cb_large_thumbs.Checked):
                G.set_thumb_size(G.THUMB_W_LARGE, G.THUMB_H_LARGE)
            else:
                G.set_thumb_size(G.THUMB_W_SMALL, G.THUMB_H_SMALL)
            self._save_pref("large_thumbs", bool(self.cb_large_thumbs.Checked))
        except Exception as ex:
            _trace("large_thumbs.set_size FAILED {}".format(ex))
            return
        # Defer both the server refresh and the local rebuild so the
        # CheckedChanged event returns immediately without re-entering.
        self._invoke_ui(self._refresh_gallery_async)
        self._invoke_ui(self._rebuild_rows)

    def _on_refresh_gallery(self, sender, e):
        self.status_label.Text = "Refreshing gallery..."
        self._refresh_gallery_async()

    def _on_scroll_to_active(self, sender, e):
        try:
            if self._rows_layout.Items.Count > 0:
                self._scroll.ScrollPosition = Eto.Drawing.Point(0, 0)
        except Exception:
            pass

    def _update_active_jobs_label(self):
        n = AI_RENDER.count_inflight(self._jobs, self._jobs_lock)
        self.bt_active_jobs.Text = "Active jobs ({})".format(n)

    # ------------------------------------------------------------------
    # Row interactions
    # ------------------------------------------------------------------

    @ERROR_HANDLE.try_catch_error()
    def _row_view_original(self, row):
        # 2026-04-28 — open in the native Eto viewer (was os.startfile).
        # 2026-04-28 v3 — wrapped in try_catch_error AND deferred via
        # _invoke_ui so any failure during viewer construction can't
        # escape into the GalleryRowPanel MouseDown event pump (CLR
        # 0xE0434352 crash class). Same pattern as _on_large_thumbs_changed.
        self._invoke_ui(lambda: self._open_in_viewer(row, "original"))

    @ERROR_HANDLE.try_catch_error()
    def _row_view_result(self, row):
        self._invoke_ui(lambda: self._open_in_viewer(row, "result"))

    @ERROR_HANDLE.try_catch_error()
    def _open_in_viewer(self, row, prefer):
        """prefer = 'original' or 'result'. Shows the native viewer with
        all currently-loaded rows as siblings so left/right navigates
        through the visible gallery."""
        Rhino.RhinoApp.WriteLine(
            "[ai_render] _open_in_viewer prefer={} row.original={} row.result={} cloud={} viewer_loaded={}".format(
                prefer,
                bool(row.original_path), bool(row.result_path),
                bool(row.cloud_item),
                _SHOW_VIEWER is not None))
        if _SHOW_VIEWER is None:
            Rhino.RhinoApp.WriteLine(
                "[ai_render] viewer module not loaded - falling back to os.startfile")
            self._legacy_open(row, prefer)
            return
        show_viewer = _SHOW_VIEWER
        # Build parallel lists so the viewer can:
        # - Walk every row in the visible gallery (Next/Prev)
        # - Toggle Input <-> Result at the current row (Tab)
        # - Show the full prompt and rich metadata in the viewer chrome
        paths = []
        alternates = []
        titles = []
        prompts = []
        subtitles = []
        viewer_rows = []
        start_idx = 0
        clicked_path = (row.result_path if prefer == "result"
                        else row.original_path)
        Rhino.RhinoApp.WriteLine(
            "[ai_render] clicked row path={} exists={}".format(
                clicked_path,
                bool(clicked_path and os.path.exists(clicked_path))))
        # 2026-04-28 — gather EVERY visible row, not just rows with a
        # local file. Cloud-only rows now contribute their stored
        # thumbnail (~512px) as the displayed image so Prev/Next can
        # actually walk the whole history. Full-res download still
        # available via Save Image... button.
        for r in (self._all_rows or []):
            primary_kind = "result" if prefer == "result" else "input"
            alt_kind = "input" if prefer == "result" else "result"
            primary_local = (r.result_path if prefer == "result"
                             else r.original_path)
            alt_local = (r.original_path if prefer == "result"
                         else r.result_path)

            # Pick best available source for primary side.
            primary_path = None
            if primary_local and os.path.exists(primary_local):
                primary_path = primary_local
            elif getattr(r, "cloud_item", None):
                primary_path = self._materialize_thumb(r, primary_kind)
            if not primary_path:
                continue  # nothing to show for this row

            # Pick best available source for alternate side.
            alt_path = None
            if alt_local and os.path.exists(alt_local):
                alt_path = alt_local
            elif getattr(r, "cloud_item", None):
                alt_path = self._materialize_thumb(r, alt_kind)

            paths.append(primary_path)
            alternates.append(alt_path)
            titles.append(r.StyleName or "-")
            prompts.append(r.full_prompt or r.PromptPreview or "")
            subtitles.append(r.Subtitle or "")
            viewer_rows.append(r)
            if r is row:
                start_idx = len(paths) - 1
        Rhino.RhinoApp.WriteLine(
            "[ai_render] gathered {} paths ({} with alternates), start_idx={}".format(
                len(paths),
                sum(1 for a in alternates if a),
                start_idx))
        # 2026-04-28 fix: if the clicked row's local file is missing
        # but the gallery has OTHER local rows, still open the viewer
        # with whatever IS local — start_idx falls back to 0. And if
        # NOTHING is local but the clicked row has a cloud item,
        # fetch then open. Old code's "0 paths -> bail to status bar"
        # was leaving the user stuck whenever they clicked a cloud-only
        # history row that had original_path/result_path attribute set
        # to a stale or never-downloaded local path.
        if not paths:
            if row.cloud_item:
                Rhino.RhinoApp.WriteLine(
                    "[ai_render] no local paths, fetching cloud item")
                self._fetch_and_open_full(row)
                return
            if clicked_path:
                Rhino.RhinoApp.WriteLine(
                    "[ai_render] no exists() match - trying single-path mode")
                paths = [clicked_path]
                alternates = [None]
                titles = [row.StyleName or "-"]
                prompts = [row.full_prompt or row.PromptPreview or ""]
                subtitles = [row.Subtitle or ""]
                viewer_rows = [row]
                start_idx = 0
            else:
                Rhino.RhinoApp.WriteLine(
                    "[ai_render] no paths AND no cloud_item - cannot open")
                self.status_label.Text = "No image available."
                return

        # Save / Open callbacks let the viewer act on the gallery row
        # without re-implementing the file-save dialog flow.
        def _viewer_save(viewer_idx, show_alt):
            if not (0 <= viewer_idx < len(viewer_rows)):
                return
            r = viewer_rows[viewer_idx]
            self._invoke_ui(lambda: self._row_save(r))

        def _viewer_open_external(viewer_idx, show_alt):
            if not (0 <= viewer_idx < len(viewer_rows)):
                return
            r = viewer_rows[viewer_idx]
            p = r.original_path if show_alt else r.result_path
            if p and os.path.exists(p):
                try:
                    os.startfile(p)
                except Exception:
                    pass

        try:
            f = show_viewer(
                self, paths,
                start_index=start_idx,
                titles=titles,
                alternates=alternates,
                prompts=prompts,
                subtitles=subtitles,
                on_save_index=_viewer_save,
                on_open_external_index=_viewer_open_external)
            if f is None:
                Rhino.RhinoApp.WriteLine(
                    "[ai_render] show_viewer returned None - falling back")
                self._legacy_open(row, prefer)
            else:
                self.status_label.Text = "Viewing {}/{}".format(
                    start_idx + 1, len(paths))
        except Exception as ex:
            Rhino.RhinoApp.WriteLine(
                "[ai_render] show_viewer raised: {}".format(ex))
            self.status_label.Text = "Viewer failed: {}".format(str(ex)[:120])
            self._legacy_open(row, prefer)

    def _materialize_input_thumb(self, row):
        return self._materialize_thumb(row, "input")

    def _materialize_thumb(self, row, kind):
        """Write a cloud row's stored thumbnail (input OR result) to a
        temp PNG and return the path. Used as a viewer-path fallback so
        the History viewer's Prev/Next can walk every row even when the
        full local file isn't cached. Resolution is small (~512px max);
        users still need 'Save Image...' to get the full original.

        kind = 'input'  -> originalThumbnailData
        kind = 'result' -> thumbnailData"""
        try:
            cloud = getattr(row, "cloud_item", None) or {}
            meta = cloud.get("metadata") or {}
            if kind == "input":
                data_url = (cloud.get("originalThumbnailData") or
                            meta.get("originalThumbnailData"))
                suffix = "_input_thumb.png"
            else:
                data_url = (cloud.get("thumbnailData") or
                            cloud.get("thumbnailVideo") or
                            meta.get("thumbnailData"))
                suffix = "_result_thumb.png"
            if not data_url:
                return None
            base = os.environ.get("TEMP") or FOLDER.DUMP_FOLDER
            thumb_dir = os.path.join(base, "EnneadTab_Ai_Rendering",
                                     "viewer_thumbs")
            if not os.path.isdir(thumb_dir):
                try:
                    os.makedirs(thumb_dir)
                except Exception:
                    pass
            row_id = getattr(row, "id", None) or "row"
            out = os.path.join(thumb_dir, "{}{}".format(row_id, suffix))
            if not os.path.exists(out):
                try:
                    G.write_data_url_to_file(data_url, out)
                except Exception as ex:
                    Rhino.RhinoApp.WriteLine(
                        "[ai_render] _materialize_thumb({}) FAILED: {}".format(
                            kind, ex))
                    return None
            return out if os.path.exists(out) else None
        except Exception:
            return None

    def _legacy_open(self, row, prefer):
        path = row.result_path if prefer == "result" else row.original_path
        if path and os.path.exists(path):
            try:
                os.startfile(path)
            except Exception:
                pass
        elif row.cloud_item:
            self._fetch_and_open_full(row)

    def _fetch_and_open_full(self, row):
        self.status_label.Text = "Loading full-size image..."
        token = AUTH.get_token()
        if not token:
            self.status_label.Text = "Sign in required."
            return
        def on_done(_bmp, path):
            if path:
                self._invoke_ui(lambda: self._open_path(path, row))
            else:
                self._invoke_ui(lambda: setattr(self.status_label, 'Text',
                                                "Failed to load image."))
        G.fetch_full_item_async(token, row.id, on_done)

    def _open_path(self, path, row=None):
        # Single-image cloud fetch — use the native viewer with one entry.
        # 2026-04-28: when a row is supplied, pass its prompt + subtitle +
        # style name so the cloud-fetched view has the same chrome as the
        # local rows, not a bare filename. Save callback wired so the
        # toolbar Save button isn't disabled for cloud-fetched items.
        if _SHOW_VIEWER is not None:
            try:
                title = (row.StyleName if row else os.path.basename(path))
                prompts = [row.full_prompt or row.PromptPreview or ""] if row else None
                subtitles = [row.Subtitle or ""] if row else None

                # Save callback for the single-row cloud-fetched case.
                def _viewer_save(viewer_idx, show_alt):
                    if row is None:
                        return
                    self._invoke_ui(lambda: self._row_save(row))

                # Try to surface the input thumbnail as the alternate so
                # "View Input" shows SOMETHING for cloud-only rows. The
                # thumbnail is small but useful for quick before/after.
                alternates = None
                if row is not None and getattr(row, "cloud_item", None):
                    alt_thumb = self._materialize_input_thumb(row)
                    if alt_thumb:
                        alternates = [alt_thumb]

                f = _SHOW_VIEWER(self, [path], start_index=0,
                                 titles=[title],
                                 prompts=prompts,
                                 subtitles=subtitles,
                                 alternates=alternates,
                                 on_save_index=_viewer_save)
                if f is not None:
                    self.status_label.Text = "Opened {}".format(
                        os.path.basename(path))
                    return
            except Exception as ex:
                Rhino.RhinoApp.WriteLine(
                    "[ai_render] viewer open failed: {}".format(ex))
        try:
            os.startfile(path)
            self.status_label.Text = "Opened {}".format(os.path.basename(path))
        except Exception as ex:
            self.status_label.Text = "Open failed: {}".format(ex)

    def _row_save(self, row):
        src = row.result_path
        if not src or not os.path.exists(src):
            if row.cloud_item:
                self._fetch_and_save(row)
                return
            self.status_label.Text = "No local result to save."
            return
        self._save_path_as(src, row)

    def _save_path_as(self, src, row):
        dlg = Eto.Forms.SaveFileDialog()
        ext = os.path.splitext(src)[1]
        dlg.Filters.Add(Eto.Forms.FileFilter("Image (*{})".format(ext), "*{}".format(ext)))
        dlg.FileName = "{}_{}_{}{}".format(
            _safe_filename(row.view_name or "View"),
            _safe_filename(row.StyleName or "Style"),
            row.id[:6], ext)
        # Bug-finder P2-dead-7: previous code constructed a throwaway
        # SelectFolderDialog just to read .Directory — copy-paste artifact.
        if self._last_save_folder and os.path.isdir(self._last_save_folder):
            dlg.Directory = self._last_save_folder
        if dlg.ShowDialog(self) == Eto.Forms.DialogResult.Ok:
            try:
                shutil.copyfile(src, dlg.FileName)
                self._last_save_folder = os.path.dirname(dlg.FileName)
                self.status_label.Text = "Saved {}".format(os.path.basename(dlg.FileName))
            except Exception as ex:
                self.status_label.Text = "Save failed: {}".format(ex)

    def _fetch_and_save(self, row):
        self.status_label.Text = "Downloading for save..."
        token = AUTH.get_token()
        if not token:
            self.status_label.Text = "Sign in required."
            return
        def on_done(_bmp, path):
            if path:
                self._invoke_ui(lambda: self._save_path_as(path, row))
            else:
                self._invoke_ui(lambda: setattr(self.status_label, 'Text',
                                                "Failed to fetch image."))
        G.fetch_full_item_async(token, row.id, on_done)

    def _row_context_menu(self, row, anchor):
        cm = Eto.Forms.ContextMenu()
        def add(label, handler, enabled=True):
            mi = Eto.Forms.ButtonMenuItem(Text=label)
            mi.Enabled = enabled
            mi.Click += lambda s, a: handler()
            cm.Items.Add(mi)

        has_local_result = bool(row.result_path and os.path.exists(row.result_path or ""))
        has_local_original = bool(row.original_path and os.path.exists(row.original_path or ""))
        has_cloud = bool(row.cloud_item)
        is_active = bool(row.job_ref and row.job_ref.status in (AI_RENDER.STATUS_PENDING, AI_RENDER.STATUS_ACTIVE))
        gallery_id = (row.cloud_item or {}).get("id") if has_cloud else (
            row.job_ref.gallery_id if row.job_ref else None)

        add("Show full prompt", lambda: self._ctx_show_prompt(row))
        cm.Items.AddSeparator()
        add("Save result as...", lambda: self._row_save(row),
            enabled=has_local_result or has_cloud)
        add("Save bundle (.zip)...", lambda: self._ctx_save_bundle(row),
            enabled=has_local_result and has_local_original)
        cm.Items.AddSeparator()
        is_failed = bool(row.job_ref and row.job_ref.status == AI_RENDER.STATUS_FAILED)
        rerun_label = "Retry" if is_failed else "Re-run with same prompt"
        add(rerun_label, lambda: self._ctx_rerun(row),
            enabled=not is_active and (has_local_original or has_cloud))
        cm.Items.AddSeparator()
        add("Open in ennead-ai.com Studio", lambda: self._ctx_open_studio(row),
            enabled=bool(gallery_id))
        cm.Items.AddSeparator()
        add("Delete from Gallery (all devices)...",
            lambda: self._ctx_delete_gallery(row, gallery_id),
            enabled=bool(gallery_id))

        cm.Show(anchor)

    def _ctx_show_prompt(self, row):
        cloud_meta = (row.cloud_item or {}).get("metadata") or {}
        if row.job_ref:
            aspect = row.job_ref.aspect_ratio
            long_edge = row.job_ref.long_edge
            interior = "yes" if row.job_ref.is_interior else "no"
            style_ref = (os.path.basename(row.job_ref.style_ref_path)
                         if row.job_ref.style_ref_path else "—")
        else:
            aspect = cloud_meta.get("aspectRatio") or "?"
            long_edge = cloud_meta.get("longEdge") or "?"
            interior = "yes" if cloud_meta.get("isInterior") else "no"
            style_ref = cloud_meta.get("styleRefName") or "—"
        Eto.Forms.MessageBox.Show(
            self,
            ("Style: {}\nView: {}\nHost: {}\n"
             "Aspect: {}\nLong edge: {}px\nInterior: {}\nStyle ref: {}\n\n{}").format(
                row.StyleName or "—", row.view_name or "—", row.host or "—",
                aspect, long_edge, interior, style_ref,
                row.full_prompt or "(empty)"),
            "Prompt for {}".format(row.id[:8]))

    def _ctx_save_bundle(self, row):
        if not (row.original_path and row.result_path
                and os.path.exists(row.original_path) and os.path.exists(row.result_path)):
            self.status_label.Text = "Bundle requires both original + result locally."
            return
        dlg = Eto.Forms.SaveFileDialog()
        dlg.Filters.Add(Eto.Forms.FileFilter("ZIP archive", ".zip"))
        dlg.FileName = "{}_{}_{}.zip".format(
            _safe_filename(row.view_name or "View"),
            _safe_filename(row.StyleName or "Style"),
            row.id[:6])
        if dlg.ShowDialog(self) != Eto.Forms.DialogResult.Ok:
            return
        try:
            import zipfile
            with zipfile.ZipFile(dlg.FileName, "w", zipfile.ZIP_DEFLATED) as zf:
                zf.write(row.original_path, "original" + os.path.splitext(row.original_path)[1])
                zf.write(row.result_path, "result" + os.path.splitext(row.result_path)[1])
                meta = "\n".join([
                    "Prompt: " + (row.full_prompt or ""),
                    "Style: " + (row.StyleName or ""),
                    "View: " + (row.view_name or ""),
                    "Host: " + (row.host or ""),
                    "Created: " + time.strftime("%Y-%m-%d %H:%M:%S",
                                                 time.localtime(row.created_at or time.time())),
                    "ID: " + (row.id or ""),
                ])
                zf.writestr("prompt.txt", meta)
            self.status_label.Text = "Bundle saved: {}".format(os.path.basename(dlg.FileName))
        except Exception as ex:
            self.status_label.Text = "Bundle failed: {}".format(str(ex)[:200])

    def _ctx_rerun(self, row):
        if row.original_path and os.path.exists(row.original_path):
            self._enqueue_rerun(row, row.original_path)
            return
        if row.cloud_item:
            self.status_label.Text = "Downloading original for re-run..."
            token = AUTH.get_token()
            if not token:
                self.status_label.Text = "Sign in required."
                return
            def on_done(_bmp, path):
                if path:
                    self._invoke_ui(lambda: self._enqueue_rerun(row, path))
                else:
                    self._invoke_ui(lambda: setattr(self.status_label, 'Text',
                                                    "Failed to fetch original."))
            G.fetch_full_item_async(token, row.id, on_done)

    def _enqueue_rerun(self, row, original_path):
        if not AI_RENDER.can_enqueue(self._jobs, self._jobs_lock):
            self.status_label.Text = "Queue full."
            return
        # Pull every reproducibility field from the source row (Audit P0).
        meta = (row.cloud_item or {}).get("metadata") or {}
        if row.job_ref:
            aspect = row.job_ref.aspect_ratio
            long_edge = row.job_ref.long_edge
            is_interior = row.job_ref.is_interior
            style_ref = row.job_ref.style_ref_path
        else:
            aspect = meta.get("aspectRatio") or self._current_aspect()
            long_edge = meta.get("longEdge") or self._current_long_edge()
            is_interior = bool(meta.get("isInterior"))
            style_ref = None
        # Preserve video kind/duration/resolution (Round 3 P2-7).
        is_video = (row.kind == "video")
        if row.job_ref and is_video:
            video_dur = row.job_ref.video_duration
            video_res = row.job_ref.video_resolution
        else:
            video_dur = int(meta.get("duration") or 4) if is_video else 4
            video_res = meta.get("resolution") or "720p"
        job = AI_RENDER.RenderJob(
            original_path=original_path, prompt=row.full_prompt,
            style_preset=row.StyleName, style_ref_path=style_ref,
            aspect_ratio=aspect, long_edge=long_edge,
            view_name=row.view_name, is_interior=is_interior,
            kind=(AI_RENDER.KIND_VIDEO if is_video else AI_RENDER.KIND_IMAGE),
            host="rhino", video_duration=video_dur, video_resolution=video_res,
            auto_save_gallery=self._auto_save_enabled)
        Monitor.Enter(self._jobs_lock)
        try:
            self._jobs.append(job)
        finally:
            Monitor.Exit(self._jobs_lock)
        self._image_worker.wake()
        self.status_label.Text = "Re-queued (job #{}).".format(job.job_id[:6])
        self._rebuild_rows()
        self._update_active_jobs_label()

    def _ctx_open_studio(self, row):
        gallery_id = (row.cloud_item or {}).get("id") if row.cloud_item else (
            row.job_ref.gallery_id if row.job_ref else None)
        if not gallery_id:
            return
        try:
            webbrowser.open("{}/gallery/{}".format(STUDIO_URL, gallery_id))
        except Exception:
            pass

    def _ctx_delete_gallery(self, row, gallery_id):
        if not gallery_id:
            return
        # Confirm
        dlg = Eto.Forms.MessageBox.Show(
            self,
            "Delete this item from your Gallery?\n\n"
            "Removes it from the cloud — every signed-in device stops showing it.",
            "Delete from Gallery",
            Eto.Forms.MessageBoxButtons.YesNo)
        if dlg != Eto.Forms.DialogResult.Yes:
            return
        token = AUTH.get_token()
        if not token:
            self.status_label.Text = "Sign in required."
            return
        def worker(state):
            try:
                AI_RENDER.delete_gallery_item_with_token(token, gallery_id)
                self._invoke_ui(lambda: setattr(self.status_label, 'Text', "Deleted from Gallery."))
                self._invoke_ui(self._refresh_gallery_async)
            except Exception as ex:
                self._invoke_ui(lambda: setattr(self.status_label, 'Text',
                                                "Delete failed: {}".format(str(ex)[:200])))
        System.Threading.ThreadPool.QueueUserWorkItem(
            System.Threading.WaitCallback(worker))

    # ------------------------------------------------------------------
    # Footer
    # ------------------------------------------------------------------

    def _on_auto_save_changed(self, sender, e):
        self._auto_save_enabled = bool(self.cb_auto_save.Checked)
        self._save_pref("auto_save", self._auto_save_enabled)
        # Visual confirmation in status bar so user knows the toggle stuck
        # (Round 3 P2 — Rhino had no NDA-mode visual cue).
        if self._auto_save_enabled:
            self.status_label.Text = "Auto-save ON — new renders saved to cloud Gallery."
        else:
            self.status_label.Text = "Auto-save OFF — new renders stay local only (NDA mode)."

    def _on_manage_cache(self, sender, e):
        """Open the manage-local-cache modal — clear the gallery cache.
        Cloud is canonical so wipe is non-destructive.
        """
        n = AI_RENDER.cache_size_bytes()
        msg = ("Local gallery cache: {}\n\n"
               "Cloud Gallery is canonical — clearing the local cache only "
               "frees disk space. Items re-download on next view.\n\n"
               "Clear cache now?").format(AI_RENDER.fmt_bytes(n))
        res = Eto.Forms.MessageBox.Show(
            self, msg, "Manage local cache",
            Eto.Forms.MessageBoxButtons.YesNo)
        if res == Eto.Forms.DialogResult.Yes:
            try:
                AI_RENDER.clear_cache()
                self.status_label.Text = "Local cache cleared."
                self._update_cache_size()
            except Exception as ex:
                self.status_label.Text = "Clear failed: {}".format(str(ex)[:200])

    def _on_open_folder(self, sender, e):
        folder = os.path.join(FOLDER.DUMP_FOLDER, "EnneadTab_Ai_Rendering")
        if not os.path.exists(folder):
            try:
                os.makedirs(folder)
            except Exception:
                pass
        try:
            os.startfile(folder)
        except Exception:
            pass

    def _update_cache_size(self):
        def worker(state):
            try:
                n = G.cache_size_bytes()
                self._invoke_ui(lambda: setattr(self.cache_size_label, 'Text',
                                                "{} cached".format(G.fmt_bytes(n))))
            except Exception:
                pass
        System.Threading.ThreadPool.QueueUserWorkItem(
            System.Threading.WaitCallback(worker))

    def _refresh_quota_async(self):
        token = AUTH.get_token()
        if not token:
            self.quota_label.Text = "Quota: -"
            # Phase B1 2026-04-30: surface coherent error instead of silent dash
            self._set_status(
                "Quota unavailable - sign in or check connection.")
            return
        def worker(state):
            # 2026-04-21 — .NET worker exception = host termination.
            # Audit Lens B P0. Mirrored in Revit. The int(...) calls below
            # raise ValueError on non-int strings if the API returns them.
            txt = "Quota: -"
            had_error = False
            try:
                q = AI_RENDER.get_quota_with_token(token)
                if q:
                    txt = "Quota: {:,}/{:,}".format(
                        int(q.get("requestsRemaining") or 0),
                        int(q.get("requestsLimit") or 0))
            except Exception as ex:
                _trace("worker.quota SWALLOWED {}".format(ex))
                had_error = True
            self._invoke_ui(lambda: setattr(self.quota_label, 'Text', txt))
            if had_error:
                # Phase B1 2026-04-30: surface coherent error instead of silent dash
                self._invoke_ui(lambda: self._set_status(
                    "Quota check failed - check connection."))
        System.Threading.ThreadPool.QueueUserWorkItem(
            System.Threading.WaitCallback(worker))

    def _open_browser_if_needed(self):
        if AUTH.get_token():
            return
        if not AUTH.is_auth_in_progress():
            AUTH.request_auth()


@LOG.log(__file__, __title__)
@ERROR_HANDLE.try_catch_error()
def view2render():
    if sc.sticky.has_key("EA_AI_RENDER_FORM"):
        existing = sc.sticky["EA_AI_RENDER_FORM"]
        try:
            existing.BringToFront()
            return
        except Exception:
            sc.sticky.Remove("EA_AI_RENDER_FORM")
    form = AiRenderForm()
    form.Owner = Rhino.UI.RhinoEtoApp.MainWindow
    form.Show()
    sc.sticky["EA_AI_RENDER_FORM"] = form


if __name__ == "__main__":
    view2render()
