# -*- coding: utf-8 -*-
__title__ = "AiRenderingFromView"
__doc__ = """AI-powered view rendering for Rhino.

Capture the active viewport, queue prompts, and see your full cloud Gallery
across every device (Revit, Rhino, mobile web, desktop web — same items).

Powered by ennead-ai.com — all features call the live web API. No local
fallbacks: when the web product improves, this dialog improves automatically.
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
    """Eto.Drawing.Color from #RRGGBB or #AARRGGBB hex string."""
    if not hex_str:
        return Eto.Drawing.Colors.White
    s = hex_str.lstrip("#")
    if len(s) == 6:
        r, g, b, a = int(s[0:2], 16), int(s[2:4], 16), int(s[4:6], 16), 255
    elif len(s) == 8:
        a, r, g, b = int(s[0:2], 16), int(s[2:4], 16), int(s[4:6], 16), int(s[6:8], 16)
    else:
        return Eto.Drawing.Colors.White
    return Eto.Drawing.Color.FromArgb(a, r, g, b)


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

        # Info column
        info = Eto.Forms.DynamicLayout()
        info.Padding = Eto.Drawing.Padding(0)
        info.Spacing = Eto.Drawing.Size(0, 0)
        lbl_style = Eto.Forms.Label(Text=row.StyleName)
        lbl_style.Font = Eto.Drawing.Font(Eto.Drawing.SystemFont.Bold, 11)
        info.Add(lbl_style)
        lbl_prompt = Eto.Forms.Label(Text=row.PromptPreview)
        lbl_prompt.TextColor = _hex_to_color("#CBCBCB")
        info.Add(lbl_prompt)
        lbl_sub = Eto.Forms.Label(Text=row.Subtitle)
        lbl_sub.TextColor = _hex_to_color("#9A9A9A")
        info.Add(lbl_sub)
        layout.Add(info, xscale=True)

        # Status + progress
        status_col = Eto.Forms.DynamicLayout()
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

        # Inline save button (only when SaveVisibility True)
        if row.SaveVisibility:
            bt = Eto.Forms.Button(Text="💾")
            bt.Size = Eto.Drawing.Size(28, 28)
            bt.Click += self._handle_save_click
            layout.Add(bt)

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
        self.Title = "EnneaDuck: AI View Render"
        self.Padding = Eto.Drawing.Padding(8)
        self.Size = Eto.Drawing.Size(1100, 780)
        self.MinimumSize = Eto.Drawing.Size(900, 560)

        self._form_closed = False
        self._jobs = []
        self._jobs_lock = System.Object()
        self._all_rows = []  # cached cloud rows
        self._filter_seconds = 7 * 86400
        self._filter_query = ""
        self._auto_save_enabled = True
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

        # Cleanup old capture_* folders (>7 days). Round 2 P1.
        try:
            AI_RENDER.cleanup_old_captures(FOLDER.DUMP_FOLDER, max_age_days=7)
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
        title = Eto.Forms.Label(Text="EnneaDuck: AI View Render")
        title.Font = Eto.Drawing.Font(Eto.Drawing.SystemFont.Bold, 14)
        title.TextColor = _hex_to_color("#FFFFE59C")
        col.Add(title)
        sub = Eto.Forms.Label(
            Text="Powered by ennead-ai.com — Ennead's in-house rendering AI.")
        sub.TextColor = _hex_to_color("#CBCBCB")
        col.Add(sub)
        return col

    def _build_capture_panel(self):
        col = Eto.Forms.DynamicLayout()
        col.Spacing = Eto.Drawing.Size(0, 4)
        col.Width = 280
        self.preview_label = Eto.Forms.Label(Text="Click Update Capture to begin")
        self.preview_label.TextColor = _hex_to_color("#CBCBCB")
        col.Add(self.preview_label)
        self.capture_preview = Eto.Forms.ImageView()
        self.capture_preview.Size = Eto.Drawing.Size(264, 168)
        col.Add(self.capture_preview)
        bt_cap = Eto.Forms.Button(Text="Update Capture")
        bt_cap.Click += self._on_capture
        col.Add(bt_cap)

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

        col.Add(Eto.Forms.Label(Text="Style Reference (optional)",
                                TextColor=_hex_to_color("#CBCBCB")))
        bt_browse = Eto.Forms.Button(Text="Browse...")
        bt_browse.Click += self._on_browse_style
        col.Add(bt_browse)
        bt_paste = Eto.Forms.Button(Text="Paste Clipboard")
        bt_paste.Click += self._on_paste_style
        col.Add(bt_paste)
        bt_lib = Eto.Forms.Button(Text="Load from Library...")
        bt_lib.Click += self._on_library_style
        col.Add(bt_lib)
        self.bt_clear_style = Eto.Forms.Button(Text="Clear")
        self.bt_clear_style.Click += self._on_clear_style
        self.bt_clear_style.Visible = False
        col.Add(self.bt_clear_style)
        self.style_preview = Eto.Forms.ImageView()
        self.style_preview.Size = Eto.Drawing.Size(120, 92)
        col.Add(self.style_preview)
        return col

    def _build_prompt_panel(self):
        col = Eto.Forms.DynamicLayout()
        col.Spacing = Eto.Drawing.Size(0, 4)

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
        bt_save_p = Eto.Forms.Button(Text="Save current...")
        bt_save_p.Click += self._on_save_prompt
        myp_row.Add(bt_save_p)
        myp_row.EndHorizontal()
        col.Add(myp_row)

        # Prompt + interior toggle row
        ptop = Eto.Forms.DynamicLayout()
        ptop.BeginHorizontal()
        ptop.Add(Eto.Forms.Label(Text="Prompt",
                                 TextColor=_hex_to_color("#CBCBCB")), xscale=True)
        self.cb_interior = Eto.Forms.CheckBox(Text="Interior scene")
        ptop.Add(self.cb_interior)
        ptop.EndHorizontal()
        col.Add(ptop)

        prow = Eto.Forms.DynamicLayout()
        prow.BeginHorizontal()
        self.tbox_prompt = Eto.Forms.TextArea()
        self.tbox_prompt.Size = Eto.Drawing.Size(0, 120)
        self.tbox_prompt.AcceptsReturn = True
        prow.Add(self.tbox_prompt, xscale=True, yscale=True)

        btn_col = Eto.Forms.DynamicLayout()
        self.bt_spell = Eto.Forms.Button(Text="Spell Check")
        self.bt_spell.Click += self._on_spell
        btn_col.Add(self.bt_spell)
        self.bt_lengthen = Eto.Forms.Button(Text="Lengthen")
        self.bt_lengthen.Click += self._on_lengthen
        btn_col.Add(self.bt_lengthen)
        self.bt_shorten = Eto.Forms.Button(Text="Shorten")
        self.bt_shorten.Click += self._on_shorten
        btn_col.Add(self.bt_shorten)
        self.bt_reset_prompt = Eto.Forms.Button(Text="Reset")
        self.bt_reset_prompt.Click += self._on_reset_prompt
        btn_col.Add(self.bt_reset_prompt)
        self.bt_undo_prompt = Eto.Forms.Button(Text="↶ Undo")
        self.bt_undo_prompt.Click += self._on_undo_prompt
        self.bt_undo_prompt.Enabled = False
        btn_col.Add(self.bt_undo_prompt)
        # Eto DynamicLayout stretches the last child to fill remaining vertical
        # space; without this filler row, Undo balloons next to the 120-px
        # TextArea. (2026-04-21 — visible in user screenshot.)
        btn_col.Add(None, yscale=True)
        prow.Add(btn_col)
        prow.EndHorizontal()
        col.Add(prow, yscale=True)

        # Status + render button
        bottom = Eto.Forms.DynamicLayout()
        bottom.BeginHorizontal()
        self.status_label = Eto.Forms.Label(Text="Ready. Capture a view then queue a render.")
        self.status_label.TextColor = _hex_to_color("#CBCBCB")
        bottom.Add(self.status_label, xscale=True)
        self.bt_render = Eto.Forms.Button(Text="Queue Render  →")
        self.bt_render.Click += self._on_render
        bottom.Add(self.bt_render)
        bottom.EndHorizontal()
        col.Add(bottom)
        return col

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
        self.cb_large_thumbs.Checked = False
        self.cb_large_thumbs.ToolTip = "Show larger preview thumbnails (240×160)"
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
            "only — in-flight jobs keep their setting. Turn OFF for NDA work.")
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
            self._image_worker.stop()
            self._video_worker.stop()
        except Exception:
            pass
        # Identity check — only clear sticky if it still points to us
        # (prevents close+reopen race from clobbering a freshly-created form).
        if sc.sticky.has_key("EA_AI_RENDER_FORM") and sc.sticky["EA_AI_RENDER_FORM"] is self:
            sc.sticky.Remove("EA_AI_RENDER_FORM")

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

        bmp = G.bitmap_from_path(target, 264, 168)
        if bmp:
            self.capture_preview.Image = bmp
        self.preview_label.Text = "Captured: {}".format(self._capture_view_name)
        self.status_label.Text = "Ready. Click Queue Render to send."

    # ------------------------------------------------------------------
    # Resolution / aspect
    # ------------------------------------------------------------------

    def _on_resolution_changed(self, sender, e):
        self._update_resolution_hint()

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
        self.cb_category.SelectedIndex = 0
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
        if self._filtered_presets:
            self.cb_style.SelectedIndex = 0
            first_prompt = self._filtered_presets[0].get("prompt", "")
            if not (self.tbox_prompt.Text or "").strip():
                self.tbox_prompt.Text = first_prompt
                self._initial_prompt_for_reset = first_prompt

    def _on_category_changed(self, sender, e):
        self._refresh_style_list()

    def _on_style_changed(self, sender, e):
        idx = self.cb_style.SelectedIndex
        if 0 <= idx < len(self._filtered_presets):
            new_prompt = self._filtered_presets[idx].get("prompt", "")
            self._push_prompt_undo()
            self.tbox_prompt.Text = new_prompt
            self._initial_prompt_for_reset = new_prompt

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

        def worker(state):
            token = AUTH.get_token()
            if not token:
                self._invoke_ui(lambda: setattr(self.status_label, 'Text',
                                                "Sign in required."))
                self._invoke_ui(lambda: self._restore_btn(btn, old_text))
                return
            try:
                new_text = api_fn(token, prompt)
                self._invoke_ui(lambda: setattr(self.tbox_prompt, 'Text', new_text))
                self._invoke_ui(lambda: setattr(self.status_label, 'Text',
                                                "{} applied.".format(action_name)))
            except Exception as ex:
                self._invoke_ui(lambda: setattr(self.status_label, 'Text',
                                                "{} failed: {}".format(action_name, str(ex)[:200])))
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

    def _refresh_my_prompts_async(self):
        token = AUTH.get_token()
        if not token:
            return
        def worker(state):
            # 2026-04-21 — .NET worker exception = host process termination.
            # Audit Lens B P0. Mirrored in Revit.
            try:
                prompts = AI_RENDER.list_prompts_with_token(token)
                self._invoke_ui(lambda: self._apply_my_prompts(prompts))
            except Exception as ex:
                _trace("worker.my_prompts SWALLOWED {}".format(ex))
        System.Threading.ThreadPool.QueueUserWorkItem(
            System.Threading.WaitCallback(worker))

    def _apply_my_prompts(self, prompts):
        self._my_prompts = prompts or []
        self.cb_my_prompts.Items.Clear()
        if not self._my_prompts:
            self.cb_my_prompts.Items.Add("(none — click Save current...)")
            self.cb_my_prompts.SelectedIndex = 0
            self.cb_my_prompts.Enabled = False
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
            return
        def on_done(rows):
            if rows is None:
                return
            self._invoke_ui(lambda: self._apply_gallery_rows(rows))
        G.fetch_gallery_index_async(token, on_done, limit=500)

    def _apply_gallery_rows(self, rows):
        self._all_rows = rows
        self._rebuild_rows()
        self._update_cache_size()

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
                G.set_thumb_size(84, 60)
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

    def _row_view_original(self, row):
        if row.original_path and os.path.exists(row.original_path):
            try:
                os.startfile(row.original_path)
            except Exception:
                pass
        elif row.cloud_item:
            self._fetch_and_open_full(row)

    def _row_view_result(self, row):
        if row.result_path and os.path.exists(row.result_path):
            try:
                os.startfile(row.result_path)
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
                self._invoke_ui(lambda: self._open_path(path))
            else:
                self._invoke_ui(lambda: setattr(self.status_label, 'Text',
                                                "Failed to load image."))
        G.fetch_full_item_async(token, row.id, on_done)

    def _open_path(self, path):
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
            self.quota_label.Text = "Quota: —"
            return
        def worker(state):
            # 2026-04-21 — .NET worker exception = host termination.
            # Audit Lens B P0. Mirrored in Revit. The int(...) calls below
            # raise ValueError on non-int strings if the API returns them.
            try:
                q = AI_RENDER.get_quota_with_token(token)
                if q:
                    txt = "Quota: {:,}/{:,}".format(
                        int(q.get("requestsRemaining") or 0),
                        int(q.get("requestsLimit") or 0))
                else:
                    txt = "Quota: —"
            except Exception as ex:
                _trace("worker.quota SWALLOWED {}".format(ex))
                txt = "Quota: —"
            self._invoke_ui(lambda: setattr(self.quota_label, 'Text', txt))
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
