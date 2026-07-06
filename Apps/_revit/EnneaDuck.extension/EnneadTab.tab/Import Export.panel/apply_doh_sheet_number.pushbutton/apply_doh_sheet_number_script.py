#!/usr/bin/python
# -*- coding: utf-8 -*-



__doc__ = ("Toggle live sheet numbers between the firm Internal scheme and the "
           "client DOH scheme. Both schemes are stored permanently; nothing is "
           "lost. Apply copies a stored scheme into the live SheetNumber slot.")
__title__ = "Apply DOH\nSheetNum"

import os
import sys

from pyrevit import forms  # noqa

import proDUCKtion  # pyright: ignore
proDUCKtion.validify()
from EnneadTab import ERROR_HANDLE, NOTIFICATION, LOG
from EnneadTab.REVIT import REVIT_APPLICATION, REVIT_SELECTION, REVIT_FORMS
from Autodesk.Revit import DB  # pyright: ignore
import System  # pyright: ignore

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import apply_logic as AL  # noqa

UIDOC = REVIT_APPLICATION.get_uidoc()
DOC = REVIT_APPLICATION.get_doc()

INTERNAL_PARAM = "Sheet Number_Internal"
DOH_PARAM = "Sheet Number_DOH"


def get_all_sheets(doc):
    sheets = DB.FilteredElementCollector(doc).OfClass(DB.ViewSheet).ToElements()
    return list(sheets)


def _param_str(sheet, name):
    p = sheet.LookupParameter(name)
    if p is None:
        return None
    v = p.AsString()
    if v is None or v == "":
        return None
    return v


def read_rows(doc):
    rows = []
    for s in get_all_sheets(doc):
        rows.append(AL.SheetRow(
            REVIT_APPLICATION.get_element_id_value(s.Id),
            s.SheetNumber,
            _param_str(s, INTERNAL_PARAM),
            _param_str(s, DOH_PARAM),
            bool(s.IsPlaceholder),
            bool(REVIT_SELECTION.is_changable(s)),
        ))
    return rows


def params_bound(doc):
    sheets = get_all_sheets(doc)
    sample = None
    for s in sheets:
        if not s.IsPlaceholder:
            sample = s
            break
    if sample is None:
        sample = sheets[0] if sheets else None
    if sample is None:
        return (False, False)
    has_internal = sample.LookupParameter(INTERNAL_PARAM) is not None
    has_doh = sample.LookupParameter(DOH_PARAM) is not None
    return (has_internal, has_doh)


def reserved_placeholder_numbers(rows):
    return [r.live for r in rows if r.is_placeholder and r.live is not None]


def build_health(rows):
    internal_set = len([r for r in rows if not AL.is_empty(r.internal)])
    doh_set = len([r for r in rows if not AL.is_empty(r.doh)])
    return {
        "total": len(rows),
        "internal_set": internal_set,
        "doh_set": doh_set,
        "internal_dups": AL.find_duplicates(rows, AL.SOURCE_INTERNAL),
        "doh_dups": AL.find_duplicates(rows, AL.SOURCE_DOH),
        "incomplete": AL.find_incomplete(rows),
        "mode": AL.infer_mode(rows),
    }


def format_report(title, items):
    lines = [title, ""]
    for it in items:
        lines.append(str(it))
    return "\n".join(lines)


def format_health_detail(rows):
    """Multi-line, target-independent breakdown for the report panel: the
    concrete issues that could block an Apply, or a ready message when clean."""
    lines = []
    idup = AL.find_duplicates(rows, AL.SOURCE_INTERNAL)
    if idup:
        lines.append("Internal duplicates: " + ", ".join(sorted(idup.keys())))
    ddup = AL.find_duplicates(rows, AL.SOURCE_DOH)
    if ddup:
        lines.append("DOH duplicates: " + ", ".join(sorted(ddup.keys())))
    incomplete = AL.find_incomplete(rows)
    if incomplete:
        lines.append("Incomplete (need both numbers): %d sheet(s)" % len(incomplete))
    drift = [r for r in rows
             if not AL.is_empty(r.internal) and not AL.is_empty(r.doh)
             and AL.classify(r) == "N"]
    if drift:
        lines.append("Drift (live matches neither store): %d sheet(s) -- "
                     "Capture to repair" % len(drift))
    if AL.infer_mode(rows) == AL.MODE_MIXED:
        lines.append("Mixed: some sheets show Internal, some DOH -- "
                     "Apply will offer to normalize")
    non_ch = AL.find_non_changable(rows)
    if non_ch:
        lines.append("Not yours to edit: %d sheet(s) owned by others" % len(non_ch))
    if not lines:
        return "No blocking issues detected. Ready to Apply."
    return "\n".join(lines)


def _sheet_by_id(doc, sid):
    # Revit 2026: DB.ElementId(<python int>) is ambiguous (Int64 vs the
    # BuiltInParameter/BuiltInCategory enum overloads). Cast to System.Int64
    # to bind the ElementId(Int64) overload explicitly.
    return doc.GetElement(DB.ElementId(System.Int64(sid)))


def _write_two_pass(doc, plan):
    """plan: list of (sheet_id, final_number). Single transaction, two passes,
    per-run GUID temp tokens. Rolls back then RE-RAISES on failure so the
    caller's @ERROR_HANDLE.try_catch_error() surfaces it to ErrorDump instead
    of swallowing it into a soft message."""
    rows = read_rows(doc)
    run_guid = str(System.Guid.NewGuid()).replace("-", "")[:8]
    if AL.temp_prefix_collision(rows, run_guid):
        run_guid = str(System.Guid.NewGuid()).replace("-", "")[:8]
    ids = [sid for sid, _ in plan]
    tokens = AL.make_temp_tokens(ids, run_guid)
    t = DB.Transaction(doc, "Apply DOH SheetNum")
    t.Start()
    try:
        for sid in ids:                       # Pass 1: vacate
            _sheet_by_id(doc, sid).SheetNumber = tokens[sid]
        doc.Regenerate()
        for sid, final_number in plan:        # Pass 2: assign
            _sheet_by_id(doc, sid).SheetNumber = final_number
        t.Commit()
    except Exception:
        t.RollBack()
        raise


def _write_param(doc, txn_name, param_name, assignments):
    """assignments: list of (sheet_id, value). Single transaction. Rolls back
    then RE-RAISES on failure (surfaced by the caller's error handler)."""
    t = DB.Transaction(doc, txn_name)
    t.Start()
    try:
        for sid, value in assignments:
            p = _sheet_by_id(doc, sid).LookupParameter(param_name)
            p.Set(value)
        t.Commit()
    except Exception:
        t.RollBack()
        raise


def _apply_gate(rows, source):
    """Return a list of blocking reasons (empty list => allowed)."""
    problems = []
    incomplete = AL.find_incomplete(rows)
    if incomplete:
        problems.append("Incomplete: %d sheets missing Internal or DOH." % len(incomplete))
    dups = AL.find_duplicates(rows, source)
    if dups:
        problems.append("Duplicate %s values: %s" % (source, ", ".join(dups.keys())))
    coll = AL.find_collisions(rows, source, reserved_placeholder_numbers(rows))
    if coll:
        problems.append("Collides with placeholder numbers: %d" % len(coll))
    drift = [r.sheet_id for r in rows
             if not AL.is_empty(r.internal) and not AL.is_empty(r.doh)
             and AL.classify(r) == "N"]
    if drift:
        problems.append("Drift: %d sheets match neither store (Capture to repair)." % len(drift))
    non_ch = AL.find_non_changable(rows)
    if non_ch:
        problems.append("Owned by others: %d sheets not changable (need ownership)." % len(non_ch))
    return problems


def _confirm(main_text, sub_text, ok_label, icon="warning"):
    """EnneadTab-styled Yes/No confirm via REVIT_FORMS.dialogue (our TaskDialog
    wrapper) instead of pyrevit forms.alert. Returns True only if the user picks
    ok_label. dialogue() may return (result, checkbox) -- normalize to the text."""
    res = REVIT_FORMS.dialogue(
        main_text=main_text, sub_text=sub_text,
        options=[ok_label, "Cancel"], icon=icon)
    if isinstance(res, (tuple, list)):
        res = res[0]
    return res == ok_label


def run_apply(target):
    rows = read_rows(DOC)
    problems = _apply_gate(rows, target)
    if problems:
        NOTIFICATION.messenger(main_text=format_report("Cannot apply:", problems))
        return
    kind, plan = AL.plan_apply(rows, target)
    if kind == "noop":
        NOTIFICATION.messenger(main_text="Already in the requested mode. Nothing to do.")
        return
    target_label = "DOH" if target == AL.SOURCE_DOH else "Internal"
    if AL.infer_mode(rows) == AL.MODE_MIXED:
        n_internal = len([r for r in rows
                          if not r.is_placeholder and not AL.is_empty(r.internal)
                          and not AL.is_empty(r.doh) and AL.classify(r) == "P"])
        n_doh = len([r for r in rows
                     if not r.is_placeholder and not AL.is_empty(r.internal)
                     and not AL.is_empty(r.doh) and AL.classify(r) == "Q"])
        if not _confirm(
                "Model is mixed: %d sheets on Internal, %d on DOH." % (
                    n_internal, n_doh),
                "Normalize all %d sheets to %s numbering?" % (
                    len(plan), target_label),
                "Normalize to %s" % target_label):
            return
    else:
        if not _confirm(
                "Apply %s numbering" % target_label,
                "%d sheets will be renumbered. Continue?" % len(plan),
                "Apply %s" % target_label):
            return
    _write_two_pass(DOC, plan)
    NOTIFICATION.messenger(main_text="Applied %s numbering to %d sheets." % (
        target_label, len(plan)))


def run_capture():
    rows = read_rows(DOC)
    mode = AL.infer_mode(rows)
    kind, payload = AL.plan_capture(rows, mode)
    if kind == "refused":
        NOTIFICATION.messenger(main_text=payload)
        return
    if not payload:
        NOTIFICATION.messenger(main_text="Nothing to capture (Internal already complete).")
        return
    if not _confirm(
            "Capture current SheetNumber into Internal",
            "Write the live SheetNumber into Sheet Number_Internal for "
            "%d sheet(s)?" % len(payload),
            "Capture", icon="shield"):
        return
    _write_param(DOC, "Capture Internal", INTERNAL_PARAM, payload)
    NOTIFICATION.messenger(main_text="Captured %d sheets into Internal." % len(payload))


def run_fill_doh():
    rows = read_rows(DOC)
    payload = AL.plan_fill_doh(rows)
    if not payload:
        NOTIFICATION.messenger(main_text="No empty DOH cells to fill.")
        return
    if not _confirm(
            "Fill empty DOH from Internal",
            "Fill %d empty DOH cell(s) with the Internal number?" % len(payload),
            "Fill", icon="shield"):
        return
    _write_param(DOC, "Fill DOH", DOH_PARAM, payload)
    NOTIFICATION.messenger(main_text="Filled %d empty DOH cells." % len(payload))


class ApplyDohWindow(forms.WPFWindow):
    def __init__(self):
        forms.WPFWindow.__init__(self, "ApplyDOH_UI.xaml")
        self._refresh()

    def _refresh(self):
        has_i, has_d = params_bound(DOC)
        if not (has_i and has_d):
            missing = []
            if not has_i:
                missing.append(INTERNAL_PARAM)
            if not has_d:
                missing.append(DOH_PARAM)
            self.ModeText.Text = "Setup required"
            self.HealthText.Text = "Missing parameter(s): %s" % ", ".join(missing)
            self.ReportText.Text = ("Add each as a Text parameter bound to the "
                                    "Sheets category, then reopen this tool.")
            for b in (self.ApplyDohButton, self.ApplyInternalButton,
                      self.CaptureButton, self.FillDohButton):
                b.IsEnabled = False
            return
        rows = read_rows(DOC)
        h = build_health(rows)
        self.ModeText.Text = "Mode: %s" % h["mode"]
        self.HealthText.Text = (
            "Sheets %d     Internal set %d (dup %d)     "
            "DOH set %d (dup %d)     incomplete %d" % (
                h["total"], h["internal_set"], len(h["internal_dups"]),
                h["doh_set"], len(h["doh_dups"]), len(h["incomplete"])))
        self.ReportText.Text = format_health_detail(rows)
        # Capture / Fill are never gated by completeness (they satisfy it).
        # Apply buttons stay enabled (XAML default) -- run_apply() re-runs the
        # gate against the specific target and reports exact blocking reasons
        # on click, so no separate up-front disable is needed.
        self.CaptureButton.IsEnabled = True
        self.FillDohButton.IsEnabled = True

    # Each click handler is individually wrapped so an exception during a
    # transaction surfaces to EnneadTab's error handler (ErrorDump + traceback
    # log + critical dialog) rather than dying silently inside the WPF modal.
    @ERROR_HANDLE.try_catch_error()
    def apply_doh_click(self, sender, args):
        self.Close()
        run_apply(AL.SOURCE_DOH)

    @ERROR_HANDLE.try_catch_error()
    def apply_internal_click(self, sender, args):
        self.Close()
        run_apply(AL.SOURCE_INTERNAL)

    @ERROR_HANDLE.try_catch_error()
    def capture_click(self, sender, args):
        self.Close()
        run_capture()

    @ERROR_HANDLE.try_catch_error()
    def fill_doh_click(self, sender, args):
        self.Close()
        run_fill_doh()

    def close_Click(self, sender, args):
        self.Close()

    def mouse_down_main_panel(self, sender, args):
        # WindowStyle="None" removes the native title bar; drag by the chrome.
        try:
            self.DragMove()
        except Exception:
            pass


@LOG.log(__file__, __title__)
@ERROR_HANDLE.try_catch_error()
def main():
    ApplyDohWindow().ShowDialog()


################## main code below #####################

if __name__ == "__main__":
    main()
