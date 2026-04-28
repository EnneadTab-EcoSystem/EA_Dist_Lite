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
    """Drawable + custom Paint approach: Eto.Forms.ImageView renders
    the bitmap at NATIVE pixel size regardless of its .Size, so the
    1:1 / Fit toggle was clipping rather than scaling. We use an
    Eto.Forms.Drawable and draw the bitmap into it at the right rect
    for each mode. Fit mode = bitmap scaled to drawable client size,
    centered. 1:1 mode = drawable expanded to bitmap native size and
    bitmap drawn at 0,0; Scrollable handles pan."""
    state.loaded_bmp = bmp
    bw = bh = 0
    try:
        bw, bh = bmp.Size.Width, bmp.Size.Height
    except Exception:
        pass
    if bw <= 0 or bh <= 0:
        return
    try:
        if state.fit_mode:
            # Match Drawable to scrollable client size so it fills,
            # doesn't trigger scroll. Paint computes the inscribed rect.
            sz = state.scroll.Size
            if sz.Width > 0 and sz.Height > 0:
                state.drawable.Size = Eto.Drawing.Size(
                    int(sz.Width), int(sz.Height))
        else:
            # 1:1 — Drawable is bitmap-sized so the Scrollable enables
            # scrollbars and the user can pan to see the full pixel grid.
            state.drawable.Size = Eto.Drawing.Size(int(bw), int(bh))
    except Exception as ex:
        _trace("set Drawable.Size FAILED: " + str(ex))
    try:
        state.drawable.Invalidate()
    except Exception as ex:
        _trace("Invalidate FAILED: " + str(ex))


# Leaf widget types whose BackgroundColor we should NOT touch (they
# manage their own theming and overriding washes out contrast).
_LEAF_TYPES = (
    'Button', 'Label', 'TextBox', 'TextArea', 'ImageView',
    'CheckBox', 'RadioButton', 'ComboBox', 'DropDown', 'ListBox',
    'Slider', 'NumericStepper', 'Spinner', 'ProgressBar',
)

def _force_opaque_tree(control, color):
    """Inverted approach (2026-04-28 v2): paint BackgroundColor on
    EVERY control in the tree except known leaf widgets. Earlier
    container-type allow-list missed Eto's wrapped class names like
    'Eto.Wpf.Forms.Controls.PanelHandler' on Rhino 8, so the
    DynamicLayouts stayed transparent and the parent dialog bled
    through. Now we paint by default and only skip explicit leaves."""
    if control is None:
        return
    cls_name = ""
    try:
        cls_name = type(control).__name__
    except Exception:
        pass
    is_leaf = any(t in cls_name for t in _LEAF_TYPES)
    if not is_leaf:
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
    # 2026-04-28 v8 — Scrollable from v7 fixed paint but introduced a
    # horizontal scrollbar because DynamicLayout's natural width
    # exceeded the scrollable's client area. TableLayout paints its
    # BackgroundColor reliably AND doesn't introduce scrollbars; it
    # also auto-stretches its single cell to fill, which is exactly
    # what we want for a "background-painting wrapper".
    bar_panel = Eto.Forms.TableLayout()
    try:
        bar_panel.BackgroundColor = _hex_to_color("#FF2A2A2A")
        bar_panel.Padding = Eto.Drawing.Padding(0)
        bar_panel.Spacing = Eto.Drawing.Size(0, 0)
    except Exception:
        pass
    bar_panel.Rows.Add(Eto.Forms.TableRow(
        Eto.Forms.TableCell(bar, True)))
    # Wrap in BeginVertical so each Add() becomes a full-width row
    # instead of a horizontal slot. Without this, DynamicLayout's
    # implicit horizontal mode left bar_panel and ctrl_panel at their
    # natural width with burgundy form chrome visible at the edges.
    root.BeginVertical()
    root.Add(bar_panel)

    # ---------------- Image area ----------------
    # Drawable + custom Paint so 1:1 vs Fit actually scales the bitmap.
    # ImageView renders at native pixel size regardless of its Size,
    # which made the toggle a no-op (just clipped/showed full bitmap).
    state.drawable = Eto.Forms.Drawable()
    try:
        state.drawable.BackgroundColor = _hex_to_color("#FF1A1A1A")
    except Exception:
        pass
    state.drawable.Paint += _make_paint_handler(state)
    state.image_view = state.drawable  # keep field name for back-compat
    state.scroll = Eto.Forms.Scrollable()
    state.scroll.Content = state.drawable
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
    state.prompt_panel = Eto.Forms.TableLayout()
    try:
        state.prompt_panel.BackgroundColor = _hex_to_color("#FF222222")
        state.prompt_panel.Padding = Eto.Drawing.Padding(8, 6)
        state.prompt_panel.Spacing = Eto.Drawing.Size(0, 0)
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
    # TableLayout doesn't have .Content; add p_layout as a single
    # full-width row (scaleWidth=True).
    state.prompt_panel.Rows.Add(Eto.Forms.TableRow(
        Eto.Forms.TableCell(p_layout, True)))
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
    ctrl_panel = Eto.Forms.TableLayout()
    try:
        ctrl_panel.BackgroundColor = _hex_to_color("#FF2A2A2A")
        ctrl_panel.Padding = Eto.Drawing.Padding(0)
        ctrl_panel.Spacing = Eto.Drawing.Size(0, 0)
    except Exception:
        pass
    ctrl_panel.Rows.Add(Eto.Forms.TableRow(
        Eto.Forms.TableCell(ctrl, True)))
    root.Add(ctrl_panel)
    root.EndVertical()

    # 2026-04-28 v10 — Empirical evidence after 4 iterations:
    # - Eto.Forms.Panel: BackgroundColor silently NO-OP on Rhino 8 build
    # - Eto.Forms.TableLayout: BackgroundColor ALSO silent NO-OP
    # - Eto.Forms.Scrollable: paints reliably (image area proof)
    # - Eto.Forms.Drawable: paints reliably (custom Paint event)
    # Only the last two work. Using Scrollable as outer wrapper because
    # it can hold a layout child via .Content. Trade-off: the inner bar
    # color distinctions are lost (everything reads uniform dark grey)
    # because we can't reliably paint differentiated bars. Accepting
    # that trade-off in exchange for getting opacity right.
    outer = Eto.Forms.Scrollable()
    try:
        outer.BackgroundColor = _hex_to_color("#FF1A1A1A")
        outer.Border = Eto.Forms.BorderType.None
        outer.ExpandContentWidth = True
        outer.ExpandContentHeight = True
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
    resize_handler = _make_resize_handler(state)
    try:
        f.SizeChanged += resize_handler
    except Exception:
        pass
    # Also subscribe on the Scrollable directly — Form.SizeChanged
    # doesn't always propagate to inner content sizing on Rhino 8 Eto.
    try:
        state.scroll.SizeChanged += resize_handler
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

def _make_paint_handler(state):
    """Per-frame paint for the image Drawable. Reads state.loaded_bmp
    and state.fit_mode; draws scaled-to-fit (centered) or 1:1 native.
    Uses the SCROLLABLE's size for fit calc so resizes are honored
    even when Drawable.Size was set to a stale value at load time."""
    def _on_paint(sender, e):
        try:
            g = e.Graphics
        except Exception:
            return
        try:
            g.Clear(_hex_to_color("#FF1A1A1A"))
        except Exception:
            pass
        bmp = state.loaded_bmp
        if bmp is None:
            return
        bw = bh = 0
        try:
            bw, bh = bmp.Size.Width, bmp.Size.Height
        except Exception:
            return
        if bw <= 0 or bh <= 0:
            return
        # Use ClipRectangle FIRST — it's the actual paint surface size
        # and is always valid inside a Paint event. Drawable.Size and
        # Scrollable.Size both returned stale/wrong values in earlier
        # iterations, breaking centering.
        dw = dh = 0
        try:
            cr = e.ClipRectangle
            dw, dh = int(cr.Width), int(cr.Height)
        except Exception:
            pass
        if dw <= 0 or dh <= 0:
            try:
                sz = state.drawable.Size
                dw, dh = int(sz.Width), int(sz.Height)
            except Exception:
                pass
        if dw <= 0 or dh <= 0:
            try:
                sz = state.scroll.Size
                dw, dh = int(sz.Width), int(sz.Height)
            except Exception:
                dw, dh = bw, bh

        if state.fit_mode and dw > 0 and dh > 0:
            ratio = min(float(dw) / bw, float(dh) / bh, 1.0)
            new_w = max(1, int(bw * ratio))
            new_h = max(1, int(bh * ratio))
            x = max(0, (dw - new_w) // 2)
            y = max(0, (dh - new_h) // 2)
            _trace("paint fit dw={} dh={} new={}x{} at ({},{})".format(
                dw, dh, new_w, new_h, x, y))
            try:
                g.DrawImage(bmp,
                            Eto.Drawing.RectangleF(
                                float(x), float(y),
                                float(new_w), float(new_h)))
            except Exception as ex:
                _trace("DrawImage fit FAILED: " + str(ex))
        else:
            _trace("paint 1:1 bw={} bh={}".format(bw, bh))
            try:
                g.DrawImage(bmp, 0.0, 0.0, float(bw), float(bh))
            except Exception as ex:
                _trace("DrawImage 1:1 FAILED: " + str(ex))
    return _on_paint


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
            # Belt-and-suspenders: also force the Drawable to repaint
            # so paint reads the freshly-changed Scrollable size.
            try:
                state.drawable.Invalidate()
            except Exception:
                pass
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
