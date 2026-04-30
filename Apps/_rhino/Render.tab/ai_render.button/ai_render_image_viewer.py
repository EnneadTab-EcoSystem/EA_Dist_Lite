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
import time as _t_viewer_load

import Rhino  # pyright: ignore
import Eto    # pyright: ignore
import System  # pyright: ignore

from EnneadTab.RHINO import RHINO_UI


# v4 self-identifying load trace - every fresh import announces its
# build version + load time. Lets the user verify a stale cache isn't
# masking the latest patch. If you bump this build tag whenever the
# viewer module changes, the Rhino command line shows exactly which
# version is running. Format: BUILD_TAG must include the iteration
# version so a cached old viewer can be spotted at a glance.
_VIEWER_BUILD_TAG = "v4.1-file-logging"


# v4.1 (2026-04-30) - file logging.
# RhinoApp.WriteLine writes to the in-app command line which scrolls,
# gets buffer-truncated, and forces the user to copy-paste to share
# with collaborators. _trace() now ALSO appends to a disk log so the
# full timeline survives across Rhino restarts and is recoverable
# after a crash. File path matches view2render_left.py's _trace:
# %APPDATA%/EnneadTab/ai_render_trace.log - same file, both modules'
# events interleave in time order.
_TRACE_LOG_PATH = None


def _trace_file_path():
    global _TRACE_LOG_PATH
    if _TRACE_LOG_PATH is not None:
        return _TRACE_LOG_PATH
    try:
        base = os.environ.get("APPDATA") or os.path.expanduser("~")
        d = os.path.join(base, "EnneadTab")
        if not os.path.isdir(d):
            try:
                os.makedirs(d)
            except Exception:
                pass
        _TRACE_LOG_PATH = os.path.join(d, "ai_render_trace.log")
    except Exception:
        _TRACE_LOG_PATH = None
    return _TRACE_LOG_PATH


def _trace(msg):
    """Dual-write trace: in-app command line (live debugging) AND
    disk log (post-hoc analysis, crash recovery, share-with-Claude).
    Both paths swallow exceptions so a logging failure never breaks
    the viewer.
    """
    line = "[ai_render_viewer] " + str(msg)
    try:
        Rhino.RhinoApp.WriteLine(line)
    except Exception:
        pass
    try:
        path = _trace_file_path()
        if path is None:
            return
        from datetime import datetime
        # Compute HH:MM:SS.mmm manually (avoids strftime microsecond
        # token to keep the IronPython compat hook happy).
        _now = datetime.now()
        ts = "{}.{:03d}".format(_now.strftime("%H:%M:%S"),
                                _now.microsecond // 1000)
        fp = open(path, "a")
        try:
            fp.write("{}  {}\n".format(ts, line))
            fp.flush()
            try:
                os.fsync(fp.fileno())
            except Exception:
                pass
        finally:
            fp.close()
    except Exception:
        pass


# Build banner - first thing in the log on every fresh import so a
# stale cache shows up as a missing/old banner.
try:
    Rhino.RhinoApp.WriteLine(
        "[ai_render_viewer] module loaded {} build={}".format(
            _t_viewer_load.strftime("%H:%M:%S"), _VIEWER_BUILD_TAG))
except Exception:
    pass
_trace("===== module load build={} =====".format(_VIEWER_BUILD_TAG))


def _hex_to_color(hex_str):
    """Thin alias - lifted to RHINO_UI.hex_to_eto_color 2026-04-30.
    Kept locally to avoid renaming ~30 callsites in this file. New
    code should call RHINO_UI.hex_to_eto_color directly.
    """
    return RHINO_UI.hex_to_eto_color(hex_str)


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
        # 2026-04-30 death-loop fix (picoe/Eto #477):
        # - v1 (3678cb888) re-entry flag is belt-and-suspenders; the
        #   size-equality guard in _apply_image_to_view was the actual
        #   loop-breaker. WPF SizeChanged fires async on the dispatcher
        #   queue, so the flag may release before the next event.
        #   INSUFFICIENT - loop returned with bigger trace dimensions.
        # - v2/v3 iterations on Scrollable+ExpandContent flags - see
        #   stacked history in build_form() near state.scroll / outer
        #   and in _make_resize_handler.
        # - v4 (this commit) adopts the rafntor/Eto.Containers
        #   DragZoomImageView pattern: Drawable IS the image-area
        #   root (no inner Scrollable wrapper), an Eto.Drawing.Matrix
        #   transform owns scale+translate, and Drawable.SizeChanged
        #   rebuilds the transform without ever mutating Size. The
        #   #477 trigger (Scrollable.ExpandContent + Drawable.Size
        #   mutation from SizeChanged) is structurally absent.
        self._applying_size = False
        # v4: image transform - identity until a bitmap is loaded.
        # Holds zoom (scale) + pan (translate) for both fit and 1:1
        # modes. Built/rebuilt by _init_transform from the current
        # Drawable.Size and bitmap.Size.
        self._transform = None
        self._prev_drawable_size = None

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


def _init_transform(state):
    """v4 Pattern 1 (DragZoomImageView, rafntor/Eto.Containers):
    Build the Matrix that maps bitmap-space -> drawable-space.

    fit_mode: scale = min(dw/bw, dh/bh, 1.0); translate to center.
    1:1 mode: scale = 1.0; translate to (0, 0). Bitmap clips at the
    edges if it exceeds the drawable. (Pan-via-mouse-drag is a
    follow-up; v4 ships without it to keep the migration scoped.)

    Critically: this function NEVER mutates state.drawable.Size.
    The Drawable inherits its size from its parent layout cell
    (yscale=True). Mutating Size from a SizeChanged handler is
    exactly what triggered picoe/Eto #477 in v1-v3.
    """
    bmp = state.loaded_bmp
    if bmp is None:
        _trace("_init_transform: bmp None (no transform built)")
        state._transform = None
        return
    try:
        bw, bh = int(bmp.Size.Width), int(bmp.Size.Height)
    except Exception as ex:
        _trace("_init_transform: bmp.Size read FAILED: " + str(ex))
        state._transform = None
        return
    if bw <= 0 or bh <= 0:
        _trace("_init_transform: degenerate bmp size {}x{}".format(bw, bh))
        state._transform = None
        return
    try:
        sz = state.drawable.Size
        dw, dh = int(sz.Width), int(sz.Height)
    except Exception as ex:
        _trace("_init_transform: drawable.Size read FAILED: " + str(ex))
        dw, dh = 0, 0
    if dw <= 0 or dh <= 0:
        # Drawable hasn't been laid out yet. Defer transform build
        # until first SizeChanged fires (Drawable.SizeChanged handler
        # will call this function again).
        _trace("_init_transform: drawable not laid out yet ({}x{}), defer".format(dw, dh))
        state._transform = None
        return
    try:
        m = Eto.Drawing.Matrix.Create()
        if state.fit_mode:
            scale = min(float(dw) / bw, float(dh) / bh, 1.0)
            new_w = bw * scale
            new_h = bh * scale
            tx = (dw - new_w) / 2.0
            ty = (dh - new_h) / 2.0
            m.Translate(float(tx), float(ty))
            m.Scale(float(scale), float(scale))
            _trace("_init_transform fit: bmp={}x{} drawable={}x{} scale={:.4f} translate=({:.1f},{:.1f}) drawn={:.0f}x{:.0f}".format(
                bw, bh, dw, dh, scale, tx, ty, new_w, new_h))
        else:
            # 1:1 mode: identity matrix - bitmap drawn at native pixel
            # size starting at (0, 0). User sees the top-left chunk if
            # bitmap > drawable. (Pan deferred to v5.)
            _trace("_init_transform 1:1: bmp={}x{} drawable={}x{} (identity matrix)".format(
                bw, bh, dw, dh))
        state._transform = m
    except Exception as ex:
        _trace("_init_transform FAILED: " + str(ex))
        state._transform = None


# v4: kept as a thin compatibility shim for any caller that still
# uses the old name. New code should call _init_transform directly.
def _apply_image_to_view(state, bmp):
    state.loaded_bmp = bmp
    _init_transform(state)
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
    # ----- Image-area architecture decision history -----
    # v1-v3 wrapped state.drawable in state.scroll (Scrollable with
    #   ExpandContent flags) for native scrollbar pan in 1:1 mode.
    #   That architecture trapped us in picoe/Eto #477 (the WPF
    #   ScrollableHandler.UpdateSizes feedback loop). Three iterations
    #   of guards (re-entry flag, size-equality, drop-then-restore
    #   ExpandContent) failed to converge cleanly - either the loop
    #   came back, the bitmap stopped fitting, the background stopped
    #   painting, or oversized scrollbars appeared.
    # v4 (this commit) adopts rafntor/Eto.Containers.DragZoomImageView:
    #   the Drawable IS the image-area root, sitting directly in the
    #   layout with yscale=True to inherit allocated size. NO inner
    #   Scrollable wrapper. NO ExpandContent flag. An Eto.Drawing.
    #   Matrix transform owns scale+translate; SizeChanged on the
    #   Drawable rebuilds the transform without ever mutating Size.
    #   The #477 trigger pattern (Scrollable.ExpandContent + manual
    #   content-size mutation) is structurally absent.
    #
    # Trade-off vs v1-v3: 1:1 mode no longer has scrollbar-pan; the
    # bitmap shows top-left clipped if it exceeds the Drawable. Pan-
    # via-mouse-drag is a follow-up (v5). Most users live in fit-mode
    # so this is acceptable for first ship of v4.
    state.drawable = Eto.Forms.Drawable()
    try:
        state.drawable.BackgroundColor = _hex_to_color("#FF1A1A1A")
    except Exception:
        pass
    state.drawable.Paint += _make_paint_handler(state)
    # v4: SizeChanged on Drawable itself (not Scrollable) rebuilds
    # the transform when the layout cell allocates a new size.
    try:
        state.drawable.SizeChanged += _make_drawable_size_handler(state)
    except Exception as ex:
        _trace("Drawable.SizeChanged subscribe failed: " + str(ex))
    state.image_view = state.drawable  # keep field name for back-compat
    # v4: state.scroll kept as a None placeholder so other code paths
    # that reference it (KeyDown subscribe loop, _on_resized fallback
    # reads in older traces, etc.) don't AttributeError. Set to None
    # so any accidental .Size / .Content access raises clearly rather
    # than silently misbehaving.
    state.scroll = None
    root.Add(state.drawable, yscale=True)

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
        # ----- outer.ExpandContent decision history -----
        # v1 (3678cb888): kept ExpandContent = True; the loop was
        #   amplified here because the outer's content (the whole
        #   dialog body) reflows on every inner-Scrollable layout
        #   pass, feeding back into the WPF UpdateSizes mechanism.
        # v2 (0c678b26b): dropped ExpandContent here. The 11088x9010
        #   trace dimensions were the OUTER scrollable accumulating
        #   layout drift on a wrapper whose content depended on its
        #   own size - classic #477 signature at ~7x dialog size.
        #   The loop died, BUT:
        #     (a) form chrome (burgundy) bled through where outer
        #         used to paint - per the carry-forward memory's
        #         empirical finding, ExpandContent IS the only
        #         paint-reliable primitive on this Rhino 8 build
        #     (b) inner button rows wider than viewport triggered
        #         an oversized horizontal scrollbar at natural width
        # v3 (this commit): ExpandContent restored on outer too.
        #   We accept the layout-level loop risk and rely on the
        #   centralized resize-handler guard to break the cycle.
        #   See _on_resized for the actual loop-breaking logic.
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
    # ----- form/scroll-level SizeChanged subscription history -----
    # v1-v3: subscribed _make_resize_handler to BOTH f.SizeChanged
    #   AND state.scroll.SizeChanged, with an in-handler call to
    #   _apply_image_to_view that mutated state.drawable.Size. This
    #   was the upper rung of the picoe/Eto #477 chain - dual-source
    #   re-entry from form-resize OR scroll-relayout.
    # v4 (this commit): both subscriptions DROPPED. The Drawable
    #   itself is what needs to know about resizes (to rebuild the
    #   transform), and Drawable.SizeChanged is wired separately at
    #   the Drawable construction site. Form/scroll resize events
    #   are no longer relevant to the image area.
    # KeyDown subscribed on multiple controls so arrow keys still fire
    # when focus is on the outer wrapper / Drawable / TextArea instead
    # of the Form itself. Eto.Forms doesn't bubble KeyDown reliably
    # across the focus tree on every Rhino build.
    key_handler = _make_key_handler(state)
    for target in (f, outer, state.image_view):
        try:
            target.KeyDown += key_handler
        except Exception as ex:
            _trace("KeyDown subscribe failed on {} (non-fatal): {}".format(
                type(target).__name__, ex))

    return f


# Closure factories. Separate named functions instead of inline lambdas
# so stack traces point at meaningful sites.

def _make_paint_handler(state):
    """Per-frame paint for the image Drawable.

    ----- paint-handler decision history (DO NOT delete) -----
    v1-v3: read e.ClipRectangle (with Drawable.Size + Scrollable.Size
      fallbacks) every paint to compute an inscribed RectangleF and
      DrawImage into it. The trace line "[ai_render_viewer] paint fit
      dw=N dh=N new=NxN at (X,Y)" was emitted from this path. The
      ClipRectangle approach was correct but it interacted badly with
      the WPF #477 layout loop - paint ran in lockstep with each
      drifting size pass, hammering the trace and the Graphics.Clear.
    v4 (this commit): paint reads state._transform (built ONCE in
      _init_transform from current Drawable.Size + bitmap.Size, also
      rebuilt on Drawable.SizeChanged). MultiplyTransform applies the
      matrix and the bitmap is drawn at origin. Per
      rafntor/Eto.Containers.DragZoomImageView - this is the
      structurally loop-free pattern. No ClipRectangle reads, no
      Scrollable.Size fallbacks, no per-paint scale math.
    """
    # v4.1 2026-04-30: rate-limited paint counter so we can confirm
    # Paint IS firing without flooding the log. State on the closure.
    paint_state = {"count": 0, "drew": 0, "no_bmp": 0, "no_xform": 0}

    def _on_paint(sender, e):
        paint_state["count"] += 1
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
            paint_state["no_bmp"] += 1
            # First few only - then silent so log doesn't fill
            if paint_state["no_bmp"] <= 3:
                _trace("paint: no bitmap loaded yet (call #{})".format(
                    paint_state["count"]))
            return
        m = state._transform
        if m is None:
            paint_state["no_xform"] += 1
            # Transform not built yet - either bitmap not loaded or
            # Drawable hasn't received its first size allocation.
            # _init_transform will fire from SizeChanged when it does.
            if paint_state["no_xform"] <= 3:
                _trace("paint: no transform yet (call #{})".format(
                    paint_state["count"]))
            return
        try:
            g.SaveTransform()
        except Exception:
            pass
        drew_ok = False
        try:
            g.MultiplyTransform(m)
            g.DrawImage(bmp, 0.0, 0.0)
            drew_ok = True
            paint_state["drew"] += 1
        except Exception as ex:
            _trace("DrawImage v4 FAILED: " + str(ex))
        try:
            g.RestoreTransform()
        except Exception:
            pass
        # First successful draw + every 50th draw - so we can see
        # Paint is firing without spam.
        if drew_ok and (paint_state["drew"] == 1 or paint_state["drew"] % 50 == 0):
            _trace("paint: draw #{} (total Paint calls={}, bmp_misses={}, xform_misses={})".format(
                paint_state["drew"], paint_state["count"],
                paint_state["no_bmp"], paint_state["no_xform"]))
    return _on_paint


def _make_drawable_size_handler(state):
    """v4 (rafntor pattern): listens to Drawable.SizeChanged and
    rebuilds the transform. Critically, this handler does NOT mutate
    Drawable.Size or any layout property - that mutation was the
    picoe/Eto #477 trigger across v1-v3. The Drawable inherits its
    size from its parent layout cell; we react to the new size, we
    don't drive it.
    """
    # Rate-limited counter to detect any residual loop without
    # flooding the log. If this fires more than ~5 times per real
    # resize, something is wrong.
    size_state = {"count": 0, "last_size": None}

    def _on_drawable_size(sender, e):
        try:
            import scriptcontext as sc
            if sc.sticky.get('EA_DISABLE_FIT_MODE'):
                return
        except Exception:
            pass
        size_state["count"] += 1
        try:
            cur = state.drawable.Size
            sig = (int(cur.Width), int(cur.Height))
        except Exception:
            sig = None
        # First few + any time the size signature changes - log it.
        # If the same size keeps firing, that's a residual loop signal.
        if size_state["count"] <= 5 or sig != size_state["last_size"]:
            _trace("drawable.SizeChanged #{} -> {}".format(
                size_state["count"], sig))
        size_state["last_size"] = sig
        if state.loaded_bmp is None:
            return
        _init_transform(state)
        try:
            state.drawable.Invalidate()
        except Exception:
            pass
    return _on_drawable_size


def _make_shown_handler(state):
    def _on_shown(sender, e):
        if not state.first_render_done:
            state.first_render_done = True
            try:
                # v4: state.scroll is None - log Drawable.Size instead.
                _trace("Shown - rendering at drawable size {}".format(
                    state.drawable.Size))
            except Exception:
                pass
        _render_current(state)
    return _on_shown


# v4 NOTE: _make_resize_handler is NO LONGER WIRED to any event.
# The form/scroll-level SizeChanged subscriptions were removed when
# v4 adopted the rafntor pattern. This function is retained verbatim
# (NOT deleted) so the v1/v2/v3 stacked decision history below stays
# in source - per memory feedback_increment_investigation_record.md
# the detour lessons are load-bearing for future maintenance. If a
# future iteration needs to revive form-level resize handling, this
# is the documented starting point.

def _make_resize_handler(state):
    def _on_resized(sender, e):
        # ----- resize-handler decision history (DO NOT delete) -----
        #
        # v1 (3678cb888) - INSUFFICIENT
        #   Approach: re-entry flag (state._applying_size) wrapped
        #   around state.drawable.Size assignment in
        #   _apply_image_to_view, plus size-equality guard
        #   (if state.drawable.Size != new_size:) before assigning,
        #   plus sticky kill-switch.
        #   Trace fired with dw/dh ~7989-8001, monotonic +1-3px growth.
        #   Symptom returned with bigger numbers (~11088).
        #   Why it failed: WPF SizeChanged fires async on the
        #   dispatcher queue. The flag releases (in finally) BEFORE
        #   the next queued event fires. Even with the equality
        #   guard preventing Drawable.Size from changing, Invalidate()
        #   still fired, Paint kept reading a drifting ClipRectangle
        #   from the WPF ScrollableHandler.UpdateSizes loop (picoe/Eto
        #   #477) which was alive at the layout level.
        #
        # v2 (0c678b26b) - LOOP DIED, BROKE THREE OTHER THINGS
        #   Approach: removed _apply_image_to_view call from resize
        #   handler entirely; dropped ExpandContentWidth/Height = True
        #   on BOTH state.scroll AND outer; resize handler only
        #   called Invalidate.
        #   Death loop died (no more substrate for #477).
        #   But: image didn't fill viewer (Drawable wasn't growing
        #   with viewport), background paint broke on outer (form
        #   chrome bled through - per carry-forward memory only
        #   Scrollable+ExpandContent paints reliably on Rhino 8),
        #   and inner button rows triggered an oversized horizontal
        #   scrollbar at natural width.
        #
        # v3 (this commit) - centralized guard
        #   ExpandContent restored on both Scrollables to fix the
        #   three v2 regressions. Re-entry flag + size-equality guard
        #   restored, this time as the ONLY loop-breaker. Resize
        #   handler still calls _apply_image_to_view + Invalidate so
        #   Drawable grows with viewport - but the guards inside
        #   _apply_image_to_view make subsequent re-entries no-ops
        #   once the size has settled, so #477's monotonic drift
        #   converges instead of diverging.
        #   Sticky kill-switch retained as in-field bypass.
        try:
            import scriptcontext as sc
            if sc.sticky.get('EA_DISABLE_FIT_MODE'):
                return
        except Exception:
            pass
        # Re-entry guard - skip if we're inside our own Drawable.Size
        # assignment (handles synchronous SizeChanged refire paths).
        if getattr(state, "_applying_size", False):
            return
        if state.first_render_done and state.fit_mode and state.loaded_bmp is not None:
            _apply_image_to_view(state, state.loaded_bmp)
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
