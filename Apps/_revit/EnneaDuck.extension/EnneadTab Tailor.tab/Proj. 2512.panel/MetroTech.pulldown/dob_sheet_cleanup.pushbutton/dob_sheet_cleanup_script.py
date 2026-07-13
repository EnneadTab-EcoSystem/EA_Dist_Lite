#!/usr/bin/python
# -*- coding: utf-8 -*-

__doc__ = """Clean up MetroTech (2512) sheets: strip a trailing '.00' and set DOB_Rev to '00'.

Runs on every sheet you are able to edit.

Features:
- Removes a trailing '.00' from the sheet number
- Sets the DOB_Rev parameter to '00'
- Sheets owned by another user are skipped and reported, never changed"""
__title__ = "DOB Sheet\nCleanup"

import proDUCKtion  # pyright: ignore
proDUCKtion.validify()

from EnneadTab import ERROR_HANDLE, LOG, NOTIFICATION
from EnneadTab.REVIT import REVIT_APPLICATION, REVIT_SELECTION, REVIT_FORMS
from Autodesk.Revit import DB  # pyright: ignore

UIDOC = REVIT_APPLICATION.get_uidoc()
DOC = REVIT_APPLICATION.get_doc()

DOB_REV_PARAM = "DOB_Rev"
DOB_REV_VALUE = "00"
STRIP_SUFFIX = ".00"


def get_all_sheets(doc):
    return list(DB.FilteredElementCollector(doc).OfClass(DB.ViewSheet).ToElements())


def stripped_number(number):
    """Return the sheet number with a single literal trailing '.00' removed, or
    None when there is nothing to strip. Returning None (not '') lets callers
    tell 'no change needed' apart from 'stripped down to empty'. SheetNumber
    comes back as a .NET System.String, so coerce to a Python str before using
    Python string methods on it."""
    if number is None:
        return None
    number = str(number)
    if number.endswith(STRIP_SUFFIX):
        return number[:-len(STRIP_SUFFIX)]
    return None


def collect(doc):
    """Read every sheet once. Returns (editable, skipped_owned, all_numbers):
      editable      -- sheets we own / are free to edit
      skipped_owned -- sheets a different user is holding (we touch nothing)
      all_numbers   -- set of every live SheetNumber, i.e. the rename collision
                       targets. Includes owned sheets: their number still blocks
                       a strip target just as much as an editable one."""
    editable = []
    skipped_owned = []
    all_numbers = set()
    for s in get_all_sheets(doc):
        all_numbers.add(s.SheetNumber)
        if REVIT_SELECTION.is_changable(s):
            editable.append(s)
        else:
            skipped_owned.append(s)
    return editable, skipped_owned, all_numbers


def plan_renames(editable, existing_numbers):
    """Decide each strip outcome WITHOUT touching Revit, so we never rely on a
    caught in-transaction exception to stay correct. The only collision possible
    here is a stripped value hitting an already-existing sheet number (no two
    sheets strip to the same value, since originals are unique and the suffix is
    fixed). Returns (to_rename, collisions):
      to_rename  -- list of (sheet, old_number, new_number) that are safe to set
      collisions -- list of (old_number, reason) reported, never attempted."""
    to_rename = []
    collisions = []
    for s in editable:
        target = stripped_number(s.SheetNumber)
        if target is None:
            continue
        if target == "":
            collisions.append((s.SheetNumber, "would become empty"))
        elif target in existing_numbers:
            collisions.append(
                (s.SheetNumber, "'{}' already exists".format(target)))
        else:
            to_rename.append((s, s.SheetNumber, target))
    return to_rename, collisions


def apply_changes(doc, editable, to_rename):
    """Single transaction. Renames are limited to the collision-free set from
    plan_renames(); the per-sheet try/except is only a backstop. DOB_Rev is set
    on every editable sheet, overwriting any existing value. Sheets whose DOB_Rev
    is missing / read-only / not a text parameter are skipped and reported, never
    silently coerced. Any UNEXPECTED failure rolls back and re-raises so
    ERROR_HANDLE surfaces it to ErrorDump instead of a soft message."""
    renamed = []
    rename_failed = []
    dob_set = 0
    dob_skipped = []  # list of (number, reason)

    t = DB.Transaction(doc, "MetroTech DOB Sheet Cleanup")
    t.Start()
    try:
        # 1) strip trailing '.00' from sheet numbers (safe targets only)
        for s, old, new in to_rename:
            try:
                s.SheetNumber = new
                renamed.append((old, new))
            except Exception as e:
                rename_failed.append((old, str(e)))

        # 2) set DOB_Rev = '00' on every editable sheet (overwrite existing)
        for s in editable:
            p = s.LookupParameter(DOB_REV_PARAM)
            if p is None:
                dob_skipped.append((s.SheetNumber, "no DOB_Rev parameter"))
            elif p.IsReadOnly:
                dob_skipped.append((s.SheetNumber, "DOB_Rev is read-only"))
            elif p.StorageType != DB.StorageType.String:
                dob_skipped.append((s.SheetNumber, "DOB_Rev is not a text parameter"))
            else:
                p.Set(DOB_REV_VALUE)
                dob_set += 1
        t.Commit()
    except Exception:
        t.RollBack()
        raise
    return renamed, rename_failed, dob_set, dob_skipped


def _print_detail(renamed, skipped_owned, collisions, rename_failed, dob_skipped):
    """Full breakdown to the pyRevit output window -- the record of exactly what
    happened, sheet by sheet."""
    if renamed:
        print("Sheet numbers stripped of '.00':")
        for old, new in renamed:
            print("  {} -> {}".format(old, new))
    if skipped_owned:
        print("Skipped -- owned by another user (untouched):")
        for s in skipped_owned:
            print("  {} (owner: {})".format(
                s.SheetNumber, REVIT_SELECTION.get_owner(s)))
    if collisions:
        print("Sheet number NOT stripped -- would collide:")
        for old, reason in collisions:
            print("  {} : {}".format(old, reason))
    if rename_failed:
        print("Sheet number rename failed unexpectedly:")
        for old, reason in rename_failed:
            print("  {} : {}".format(old, reason))
    if dob_skipped:
        print("DOB_Rev NOT set:")
        for num, reason in dob_skipped:
            print("  {} : {}".format(num, reason))


@LOG.log(__file__, __title__)
@ERROR_HANDLE.try_catch_error()
def dob_sheet_cleanup(doc):
    editable, skipped_owned, all_numbers = collect(doc)
    to_rename, collisions = plan_renames(editable, all_numbers)

    confirm = REVIT_FORMS.dialogue(
        main_text="MetroTech (2512) DOB sheet cleanup",
        sub_text=(
            "{editable} sheet(s) you can edit:\n"
            "  - strip trailing '.00' from {strip} sheet number(s)\n"
            "  - set DOB_Rev = '00' on all {editable} of them\n\n"
            "{owned} sheet(s) owned by others will be skipped.\n"
            "{coll} sheet(s) can't be stripped (name would collide) -- "
            "reported, not changed.\n\nContinue?".format(
                editable=len(editable),
                strip=len(to_rename),
                owned=len(skipped_owned),
                coll=len(collisions))),
        options=["Run", "Cancel"],
        icon="warning")
    if confirm != "Run":
        return

    renamed, rename_failed, dob_set, dob_skipped = apply_changes(
        doc, editable, to_rename)

    _print_detail(renamed, skipped_owned, collisions, rename_failed, dob_skipped)

    lines = []
    lines.append("Sheet numbers stripped of '.00': {}".format(len(renamed)))
    lines.append("DOB_Rev set to '00': {}".format(dob_set))
    if skipped_owned:
        lines.append("Skipped (owned by others): {}".format(len(skipped_owned)))
    if collisions:
        lines.append("Not stripped (name collision): {}".format(len(collisions)))
    if rename_failed:
        lines.append("Rename failed unexpectedly: {}".format(len(rename_failed)))

    # Make an unbound / unwritable DOB_Rev impossible to miss: if we couldn't
    # set it anywhere but there were editable sheets, the parameter almost
    # certainly isn't bound to the Sheets category in this model.
    if dob_set == 0 and editable:
        lines.append("")
        lines.append("WARNING: DOB_Rev was not set on ANY sheet. Bind a text "
                     "parameter named 'DOB_Rev' to the Sheets category, then "
                     "run again.")
    elif dob_skipped:
        lines.append("DOB_Rev not set on {} sheet(s) (see output for why).".format(
            len(dob_skipped)))

    NOTIFICATION.messenger(main_text="\n".join(lines))


################## main code below #####################
if __name__ == "__main__":
    dob_sheet_cleanup(DOC)
