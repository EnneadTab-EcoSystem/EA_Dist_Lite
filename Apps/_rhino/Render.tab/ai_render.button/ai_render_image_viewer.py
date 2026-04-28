# -*- coding: utf-8 -*-
"""Native Eto image viewer for the Rhino AI Render dialog.

Replaces the previous os.startfile() handoff that delegated to whatever
the OS had registered for .jpg/.png. The native viewer is bound to the
gallery row list so prev/next walks the visible/filtered set.

IronPython 2.7 — no f-strings, type hints, pathlib.

Usage from view2render_left.py:
    from ai_render_image_viewer import show_viewer
    show_viewer(
        parent_form,
        paths_list,                  # primary image to show first
        start_index=2,
        titles=row_titles,           # short label per item (top bar)
        alternates=alternate_paths,  # parallel list, Tab swaps to this
        prompts=full_prompts,        # parallel list, shown in prompt panel
        subtitles=meta_strings,      # parallel list, e.g. "16:9 - 1500px"
        on_save_index=callback,      # optional Save handler (idx -> None)
        on_open_external_index=cb,   # optional Open-in-OS handler
    )

Design notes (2026-04-28 v5):
- NOT a Python subclass of Eto.Forms.Form. Plain Form() construction +
  closure-based handlers on a separate _ViewerState avoids the
  IronPython CLR-binder arity mismatch that crashed v1-v3.
- sys.modules invalidation in view2render_left.py guarantees every
  dialog open reads the latest source even when ResetEngine fails to
  flush the in-process module cache.
- Keyboard shortcuts: Left/Right navigate, Tab swaps Input/Result,
  F or Space toggles fit/1:1, P toggles prompt panel, S saves, O opens
  in OS app, Esc closes.
"""

import os

import Rhino  # pyright: ignore
import Eto    # pyright: ignore
import System  # pyright: ignore


def _trace(msg):
    try:
        Rhino.RhinoApp.WriteLine("[ai_render_viewer] " + str(msg))
    except Exception:
        pass


def _hex_to_color(hex_str):
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


class _ViewerState(object):
    """Pure-Python state object — no .NET inheritance."""

    def __init__(self, paths, start_index, titles=None, alternates=None,
                 prompts=None, subtitles=None,
                 on_save_index=None, on_open_external_index=None):
        self.paths = list(paths or [])
        self.alternates = list(alternates or [])
        while len(self.alternates) < len(self.paths):
            self.alternates.append(None)
        self.titles = list(titles or [])
        self.prompts = list(prompts or [])
        self.subtitles = list(subtitles or [])
        if self.paths:
            self.idx = max(0, min(int(start_index), len(self.paths) - 1))
        else:
            self.idx = 0

        # Modes — persist across navigation so the user sees the same
        # side / fit setting / prompt visibility after Next/Prev.
        self.fit_mode = True
        self.show_alternate = False  # False = primary (paths), True = alternates
        self.prompt_visible = True

        self.loaded_bmp = None
        self.first_render_done = False

        self.on_save_index = on_save_index
        self.on_open_external_index = on_open_external_index

        # Eto controls — assigned by build.
        self.form = None
        self.lbl_title = None
        self.lbl_side = None
        self.lbl_meta = None
        self.lbl_counter = None
        self.bt_prev = None
        self.bt_next = None
        self.bt_fit = None
        self.bt_swap = None
        self.bt_prompt = None
        self.bt_save = None
        self.bt_open = None
        self.image_view = None
        self.scroll = None
        self.prompt_panel = None
        self.tbox_prompt = None

    def current_path(self):
        if not self.paths:
            return None
        if self.show_alternate:
            alt = self.alternates[self.idx] if self.idx < len(self.alternates) else None
            if alt:
                return alt
        return self.paths[self.idx]

    def has_alternate_at(self, idx):
        if 0 <= idx < len(self.alternates):
            return self.alternates[idx] is not None
        return False

    def current_title(self):
        if 0 <= self.idx < len(self.titles):
            return self.titles[self.idx] or ""
        return ""

    def current_prompt(self):
        if 0 <= self.idx < len(self.prompts):
            return self.prompts[self.idx] or ""
        return ""

    def current_subtitle(self):
        if 0 <= self.idx < len(self.subtitles):
            return self.subtitles[self.idx] or ""
        return ""


def _load_bitmap(path):
    if not path or not os.path.exists(path):
        _trace("load_bitmap: missing path " + str(path))
        return None
    try:
        return Eto.Drawing.Bitmap(path)
    except Exception as ex:
        _trace("Eto.Drawing.Bitmap(path) FAILED: {} - {}".format(path, ex))
        try:
            stream = System.IO.File.OpenRead(path)
            try:
                return Eto.Drawing.Bitmap(stream)
            finally:
                stream.Close()
        except Exception as ex2:
            _trace("Stream load FAILED: " + str(ex2))
            return None


def _render_current(state):
    n = len(state.paths)
    path = state.current_path()
    title = state.current_title() or (
        os.path.basename(path) if path else "(no image)")
    side_label = "Result" if not state.show_alternate else "Input"
    if state.show_alternate and not state.has_alternate_at(state.idx):
        side_label = "Result (no input cached)"

    try:
        state.lbl_title.Text = title
        state.lbl_counter.Text = "{} / {}".format(state.idx + 1, n) if n else "-"
        state.lbl_side.Text = side_label
        state.lbl_meta.Text = state.current_subtitle()
        state.bt_prev.Enabled = state.idx > 0
        state.bt_next.Enabled = state.idx < n - 1
        state.bt_fit.Text = "1:1" if state.fit_mode else "Fit"
        state.bt_swap.Text = "View Input" if not state.show_alternate else "View Result"
        # Save/Open enabled only when the current path is a real local file.
        local_ok = bool(path and os.path.exists(path))
        if state.bt_save is not None:
            state.bt_save.Enabled = local_ok and state.on_save_index is not None
        if state.bt_open is not None:
            state.bt_open.Enabled = local_ok
        # Prompt panel
        if state.tbox_prompt is not None:
            state.tbox_prompt.Text = state.current_prompt()
        if state.prompt_panel is not None:
            state.prompt_panel.Visible = state.prompt_visible
            state.bt_prompt.Text = "Hide Prompt" if state.prompt_visible else "Show Prompt"
    except Exception as ex:
        _trace("label update FAILED: " + str(ex))

    bmp = _load_bitmap(path)
    if bmp is None:
        try:
            state.image_view.Image = None
        except Exception:
            pass
        return
    state.loaded_bmp = bmp
    _apply_image_to_view(state, bmp)


def _apply_image_to_view(state, bmp):
    try:
        state.image_view.Image = bmp
    except Exception as ex:
        _trace("set Image FAILED: " + str(ex))
        return
    bw = bh = 0
    try:
        bw, bh = bmp.Size.Width, bmp.Size.Height
    except Exception:
        pass
    if bw <= 0 or bh <= 0:
        return
    if not state.fit_mode:
        try:
            state.image_view.Size = Eto.Drawing.Size(int(bw), int(bh))
        except Exception:
            pass
        return
    avail_w = avail_h = 0
    try:
        sz = state.scroll.Size
        avail_w = max(0, int(sz.Width) - 16)
        avail_h = max(0, int(sz.Height) - 16)
    except Exception:
        pass
    if avail_w <= 0 or avail_h <= 0:
        try:
            state.image_view.Size = Eto.Drawing.Size(int(bw), int(bh))
        except Exception:
            pass
        return
    ratio = min(float(avail_w) / bw, float(avail_h) / bh, 1.0)
    new_w = max(1, int(bw * ratio))
    new_h = max(1, int(bh * ratio))
    try:
        state.image_view.Size = Eto.Drawing.Size(new_w, new_h)
    except Exception as ex:
        _trace("set Size FAILED: " + str(ex))


_CONTAINER_TYPES = (
    'Panel', 'Scrollable', 'GroupBox',
    'DynamicLayout', 'StackLayout', 'TableLayout', 'PixelLayout',
    'TabControl', 'TabPage', 'Splitter',
)

def _force_opaque_tree(control, color):
    """Recursively set BackgroundColor on every CONTAINER in the
    Eto control tree (Panel/Scrollable/DynamicLayout/etc.) — not on
    leaf widgets like Button/Label/TextArea/ImageView, which need
    their own background to keep contrast and theming.
    Some containers (DynamicLayout especially) don't paint their
    BackgroundColor by default, so the parent Form's surface bleeds
    through gaps between explicit-paint children. Called once after
    the form is built."""
    if control is None:
        return
    cls_name = ""
    try:
        cls_name = type(control).__name__
    except Exception:
        pass
    is_container = any(t in cls_name for t in _CONTAINER_TYPES)
    if is_container:
        try:
            if hasattr(control, 'BackgroundColor'):
                control.BackgroundColor = color
        except Exception:
            pass
    # Walk Content (Panel, ScrollView, etc.)
    try:
        child = getattr(control, 'Content', None)
        if child is not None and child is not control:
            _force_opaque_tree(child, color)
    except Exception:
        pass
    # Walk Items (DynamicLayout, StackLayout, etc.)
    try:
        items = getattr(control, 'Items', None)
        if items is not None:
            for it in items:
                # DynamicLayoutItem / StackLayoutItem expose .Control
                inner = getattr(it, 'Control', it)
                _force_opaque_tree(inner, color)
    except Exception:
        pass
    # Walk Rows (TableLayout)
    try:
        rows = getattr(control, 'Rows', None)
        if rows is not None:
            for row in rows:
                cells = getattr(row, 'Cells', None)
                if cells:
                    for cell in cells:
                        inner = getattr(cell, 'Control', cell)
                        _force_opaque_tree(inner, color)
    except Exception:
        pass


def _build_form(state):
    f = Eto.Forms.Form()
    state.form = f
    try:
        f.Title = "EnneaDuck - Render Viewer"
    except Exception:
        pass
    try:
        f.Size = Eto.Drawing.Size(1280, 880)
        f.MinimumSize = Eto.Drawing.Size(720, 520)
        f.Padding = Eto.Drawing.Padding(0)
    except Exception:
        pass
    # Force fully opaque chrome. On Rhino 8 / Windows 11 the default Form
    # background can pick up the system acrylic/blur effect, which made
    # the dark dialog look washed-out and "semi-transparent" through to
    # the Rhino doc behind it. Setting a hard FF-alpha background here
    # AND wrapping Content in an opaque Panel below kills both leak paths.
    try:
        f.BackgroundColor = _hex_to_color("#FF1A1A1A")
    except Exception:
        pass
    try:
        f.Opacity = 1.0
    except Exception:
        pass

    root = Eto.Forms.DynamicLayout()
    try:
        root.Padding = Eto.Drawing.Padding(0)
        root.Spacing = Eto.Drawing.Size(0, 0)
    except Exception:
        pass

    # ---------------- Top bar ----------------
    bar = Eto.Forms.DynamicLayout()
    try:
        bar.Padding = Eto.Drawing.Padding(14, 8)
        bar.Spacing = Eto.Drawing.Size(10, 2)
    except Exception:
        pass
    bar.BeginVertical()

    # Top row: title + side badge + counter
    bar.BeginHorizontal()
    state.lbl_title = Eto.Forms.Label(Text="")
    try:
        state.lbl_title.Font = Eto.Drawing.Font(
            Eto.Drawing.SystemFont.Bold, 13)
        state.lbl_title.TextColor = _hex_to_color("#DAE8FD")
    except Exception:
        pass
    bar.Add(state.lbl_title, xscale=True)

    state.lbl_side = Eto.Forms.Label(Text="")
    try:
        state.lbl_side.Font = Eto.Drawing.Font(
            Eto.Drawing.SystemFont.Bold, 10)
        state.lbl_side.TextColor = _hex_to_color("#FFE59C")
    except Exception:
        pass
    bar.Add(state.lbl_side)

    state.lbl_counter = Eto.Forms.Label(Text="")
    try:
        state.lbl_counter.TextColor = _hex_to_color("#9A9A9A")
    except Exception:
        pass
    bar.Add(state.lbl_counter)
    bar.EndHorizontal()

    # Subtitle row: metadata (style / view / resolution / duration)
    bar.BeginHorizontal()
    state.lbl_meta = Eto.Forms.Label(Text="")
    try:
        state.lbl_meta.TextColor = _hex_to_color("#9A9A9A")
        state.lbl_meta.Font = Eto.Drawing.Font(
            Eto.Drawing.SystemFont.Default, 9)
    except Exception:
        pass
    bar.Add(state.lbl_meta, xscale=True)
    bar.EndHorizontal()

    bar.EndVertical()
    bar_panel = Eto.Forms.Panel()
    try:
        bar_panel.BackgroundColor = _hex_to_color("#FF2A2A2A")
    except Exception:
        pass
    bar_panel.Content = bar
    root.Add(bar_panel)

    # ---------------- Image area ----------------
    state.image_view = Eto.Forms.ImageView()
    state.scroll = Eto.Forms.Scrollable()
    state.scroll.Content = state.image_view
    try:
        state.scroll.BackgroundColor = _hex_to_color("#FF1A1A1A")
        state.scroll.ExpandContentWidth = True
        state.scroll.ExpandContentHeight = True
    except Exception:
        pass
    root.Add(state.scroll, yscale=True)

    # ---------------- Prompt panel ----------------
    state.tbox_prompt = Eto.Forms.TextArea()
    try:
        state.tbox_prompt.ReadOnly = True
        state.tbox_prompt.Wrap = True
        state.tbox_prompt.BackgroundColor = _hex_to_color("#FF222222")
        state.tbox_prompt.TextColor = _hex_to_color("#CBCBCB")
        state.tbox_prompt.Font = Eto.Drawing.Font(
            Eto.Drawing.SystemFont.Default, 10)
    except Exception:
        pass
    state.prompt_panel = Eto.Forms.Panel()
    try:
        state.prompt_panel.BackgroundColor = _hex_to_color("#FF222222")
        state.prompt_panel.Padding = Eto.Drawing.Padding(8, 6)
    except Exception:
        pass
    p_layout = Eto.Forms.DynamicLayout()
    p_layout.BeginHorizontal()
    p_label = Eto.Forms.Label(Text="PROMPT")
    try:
        p_label.Font = Eto.Drawing.Font(Eto.Drawing.SystemFont.Bold, 9)
        p_label.TextColor = _hex_to_color("#9A9A9A")
        p_label.Width = 60
    except Exception:
        pass
    p_layout.Add(p_label)
    p_layout.Add(state.tbox_prompt, xscale=True)
    p_layout.EndHorizontal()
    state.prompt_panel.Content = p_layout
    try:
        state.prompt_panel.Height = 110
    except Exception:
        pass
    root.Add(state.prompt_panel)

    # ---------------- Bottom controls ----------------
    # 2026-04-28 v6 layout: Prev/Next at the FAR extremes of the bar,
    # large enough that they're the obvious navigation affordance. The
    # secondary toggles (swap / fit / prompt) cluster in the middle
    # with spacers. "Open in OS" removed — non-tech users were confused
    # by the term; Save covers the export use case, and the O keyboard
    # shortcut still works for power users.
    ctrl = Eto.Forms.DynamicLayout()
    try:
        ctrl.Padding = Eto.Drawing.Padding(14, 8)
        ctrl.Spacing = Eto.Drawing.Size(6, 0)
    except Exception:
        pass
    ctrl.BeginHorizontal()

    # FAR LEFT: prominent Previous button.
    state.bt_prev = Eto.Forms.Button(Text="<  Previous")
    state.bt_prev.ToolTip = "Previous image in history (Left arrow)"
    try:
        state.bt_prev.Size = Eto.Drawing.Size(120, 36)
        state.bt_prev.Font = Eto.Drawing.Font(
            Eto.Drawing.SystemFont.Bold, 11)
    except Exception:
        pass
    state.bt_prev.Click += _make_prev_handler(state)
    ctrl.Add(state.bt_prev)

    ctrl.Add(None, xscale=True)  # spacer

    # MIDDLE CLUSTER: secondary toggles.
    state.bt_swap = Eto.Forms.Button(Text="View Input")
    state.bt_swap.ToolTip = "Swap between input capture and AI result (Tab)"
    state.bt_swap.Click += _make_swap_handler(state)
    ctrl.Add(state.bt_swap)

    state.bt_fit = Eto.Forms.Button(Text="1:1")
    state.bt_fit.ToolTip = "Toggle fit-to-window vs actual size (F or Space)"
    state.bt_fit.Click += _make_fit_handler(state)
    ctrl.Add(state.bt_fit)

    state.bt_prompt = Eto.Forms.Button(Text="Hide Prompt")
    state.bt_prompt.ToolTip = "Show or hide the prompt text panel (P)"
    state.bt_prompt.Click += _make_prompt_handler(state)
    ctrl.Add(state.bt_prompt)

    state.bt_save = Eto.Forms.Button(Text="Save Image...")
    state.bt_save.ToolTip = "Save a copy of the current image to disk (S)"
    state.bt_save.Click += _make_save_handler(state)
    ctrl.Add(state.bt_save)

    # bt_open kept for the O keyboard shortcut handler but not on the
    # toolbar (the label "Open in OS" confused non-technical users).
    state.bt_open = Eto.Forms.Button(Text="")
    state.bt_open.Visible = False
    state.bt_open.Click += _make_open_handler(state)

    ctrl.Add(None, xscale=True)  # spacer

    # FAR RIGHT: prominent Next button.
    state.bt_next = Eto.Forms.Button(Text="Next  >")
    state.bt_next.ToolTip = "Next image in history (Right arrow)"
    try:
        state.bt_next.Size = Eto.Drawing.Size(120, 36)
        state.bt_next.Font = Eto.Drawing.Font(
            Eto.Drawing.SystemFont.Bold, 11)
    except Exception:
        pass
    state.bt_next.Click += _make_next_handler(state)
    ctrl.Add(state.bt_next)

    ctrl.EndHorizontal()

    # Single thin hint line under the controls so the keyboard shortcuts
    # are discoverable without crowding the buttons.
    ctrl.BeginHorizontal()
    hint = Eto.Forms.Label(
        Text="Left / Right arrows navigate history   |   "
             "Tab swaps input / result   |   "
             "F or Space toggles fit   |   P toggles prompt   |   "
             "S saves   |   Esc closes")
    try:
        hint.TextColor = _hex_to_color("#7A7A7A")
        hint.Font = Eto.Drawing.Font(Eto.Drawing.SystemFont.Default, 9)
        hint.TextAlignment = Eto.Forms.TextAlignment.Center
    except Exception:
        pass
    ctrl.Add(hint, xscale=True)
    ctrl.EndHorizontal()
    ctrl_panel = Eto.Forms.Panel()
    try:
        ctrl_panel.BackgroundColor = _hex_to_color("#FF2A2A2A")
    except Exception:
        pass
    ctrl_panel.Content = ctrl
    root.Add(ctrl_panel)

    # Wrap layout in a hard-painted opaque Panel. Eto Form.BackgroundColor
    # on Rhino 8 doesn't reliably paint the client area — gaps in the
    # DynamicLayout let the parent AiRenderForm's burgundy tint bleed
    # through, which is what made the viewer look "red semi-transparent".
    outer = Eto.Forms.Panel()
    try:
        outer.BackgroundColor = _hex_to_color("#FF1A1A1A")
        outer.Padding = Eto.Drawing.Padding(0)
    except Exception:
        pass
    outer.Content = root
    f.Content = outer
    # 2026-04-28 — even with the outer Panel set, DynamicLayout
    # containers don't paint their BackgroundColor, so the parent
    # AiRenderForm's burgundy was leaking through the gaps between
    # explicit panels. Recursively force BackgroundColor on every
    # container in the tree as a brute-force opacity guarantee. Mirrors
    # what RHINO_UI.apply_dark_style does for the main dialog.
    _force_opaque_tree(outer, _hex_to_color("#FF1A1A1A"))

    try:
        f.Shown += _make_shown_handler(state)
    except Exception as ex:
        _trace("Shown subscribe failed (non-fatal): " + str(ex))
    try:
        f.SizeChanged += _make_resize_handler(state)
    except Exception:
        pass
    # KeyDown subscribed on multiple controls so arrow keys still fire
    # when focus is on the Scrollable / ImageView / TextArea instead of
    # the Form itself. Eto.Forms doesn't bubble KeyDown reliably across
    # the focus tree on every Rhino build.
    key_handler = _make_key_handler(state)
    for target in (f, outer, state.scroll, state.image_view):
        try:
            target.KeyDown += key_handler
        except Exception as ex:
            _trace("KeyDown subscribe failed on {} (non-fatal): {}".format(
                type(target).__name__, ex))

    return f


# Closure factories. Separate named functions instead of inline lambdas
# so stack traces point at meaningful sites.

def _make_shown_handler(state):
    def _on_shown(sender, e):
        if not state.first_render_done:
            state.first_render_done = True
            try:
                _trace("Shown - rendering at scrollable size {}".format(
                    state.scroll.Size))
            except Exception:
                pass
        _render_current(state)
    return _on_shown


def _make_resize_handler(state):
    def _on_resized(sender, e):
        if state.first_render_done and state.fit_mode and state.loaded_bmp is not None:
            _apply_image_to_view(state, state.loaded_bmp)
    return _on_resized


def _make_prev_handler(state):
    def _on_prev(sender, e):
        if state.idx > 0:
            state.idx -= 1
            _render_current(state)
    return _on_prev


def _make_next_handler(state):
    def _on_next(sender, e):
        if state.idx < len(state.paths) - 1:
            state.idx += 1
            _render_current(state)
    return _on_next


def _make_fit_handler(state):
    def _on_toggle_fit(sender, e):
        state.fit_mode = not state.fit_mode
        if state.loaded_bmp is not None:
            _apply_image_to_view(state, state.loaded_bmp)
        try:
            state.bt_fit.Text = "1:1" if state.fit_mode else "Fit"
        except Exception:
            pass
    return _on_toggle_fit


def _make_swap_handler(state):
    def _on_swap(sender, e):
        # Toggle between primary and alternate; rerender same idx.
        state.show_alternate = not state.show_alternate
        _trace("swap -> {}".format("Input" if state.show_alternate else "Result"))
        _render_current(state)
    return _on_swap


def _make_prompt_handler(state):
    def _on_prompt(sender, e):
        state.prompt_visible = not state.prompt_visible
        try:
            state.prompt_panel.Visible = state.prompt_visible
            state.bt_prompt.Text = "Hide Prompt" if state.prompt_visible else "Show Prompt"
        except Exception:
            pass
    return _on_prompt


def _make_save_handler(state):
    def _on_save(sender, e):
        if state.on_save_index is None:
            return
        try:
            state.on_save_index(state.idx, state.show_alternate)
        except Exception as ex:
            _trace("save handler raised: " + str(ex))
    return _on_save


def _make_open_handler(state):
    def _on_open(sender, e):
        path = state.current_path()
        if not path or not os.path.exists(path):
            return
        if state.on_open_external_index is not None:
            try:
                state.on_open_external_index(state.idx, state.show_alternate)
                return
            except Exception:
                pass
        # Fallback: os.startfile so users always have an escape hatch.
        try:
            os.startfile(path)
        except Exception as ex:
            _trace("os.startfile failed: " + str(ex))
    return _on_open


def _make_key_handler(state):
    def _on_key(sender, e):
        try:
            k = e.Key
        except Exception:
            return
        if k == Eto.Forms.Keys.Left:
            _make_prev_handler(state)(sender, e)
            e.Handled = True
        elif k == Eto.Forms.Keys.Right:
            _make_next_handler(state)(sender, e)
            e.Handled = True
        elif k == Eto.Forms.Keys.Tab:
            _make_swap_handler(state)(sender, e)
            e.Handled = True
        elif k == Eto.Forms.Keys.Escape:
            try:
                state.form.Close()
            except Exception:
                pass
            e.Handled = True
        elif k == Eto.Forms.Keys.F or k == Eto.Forms.Keys.Space:
            _make_fit_handler(state)(sender, e)
            e.Handled = True
        elif k == Eto.Forms.Keys.P:
            _make_prompt_handler(state)(sender, e)
            e.Handled = True
        elif k == Eto.Forms.Keys.S:
            _make_save_handler(state)(sender, e)
            e.Handled = True
        elif k == Eto.Forms.Keys.O:
            _make_open_handler(state)(sender, e)
            e.Handled = True
        elif k == Eto.Forms.Keys.Home:
            if state.paths:
                state.idx = 0
                _render_current(state)
            e.Handled = True
        elif k == Eto.Forms.Keys.End:
            if state.paths:
                state.idx = len(state.paths) - 1
                _render_current(state)
            e.Handled = True
    return _on_key


# Module-level handle so a second show_viewer call doesn't pile up
# multiple windows; reuses the existing one if still open.
_VIEWER = [None]


def show_viewer(parent, paths, start_index=0, titles=None,
                alternates=None, prompts=None, subtitles=None,
                on_save_index=None, on_open_external_index=None):
    """Open (or refocus) the native image viewer.

    Returns the form instance, or None on failure.
    """
    if not paths:
        _trace("show_viewer: empty paths list")
        return None
    _trace("show_viewer paths={} alts={} start={}".format(
        len(paths),
        sum(1 for a in (alternates or []) if a) if alternates else 0,
        start_index))
    existing = _VIEWER[0]
    if existing is not None:
        try:
            existing.Close()
        except Exception as ex:
            _trace("close existing viewer FAILED: " + str(ex))
        _VIEWER[0] = None

    state = _ViewerState(
        paths, start_index, titles=titles, alternates=alternates,
        prompts=prompts, subtitles=subtitles,
        on_save_index=on_save_index,
        on_open_external_index=on_open_external_index)
    f = None
    try:
        f = _build_form(state)
    except Exception as ex:
        _trace("Form construction FAILED: " + str(ex))
        return None
    if f is None:
        return None
    _VIEWER[0] = f
    try:
        f.Show()
    except Exception as ex:
        _trace("Show() FAILED: " + str(ex))
        _VIEWER[0] = None
        return None
    try:
        f.Focus()
    except Exception as ex:
        _trace("Focus() failed (non-fatal): " + str(ex))
    _trace("show_viewer: viewer is up")
    return f
