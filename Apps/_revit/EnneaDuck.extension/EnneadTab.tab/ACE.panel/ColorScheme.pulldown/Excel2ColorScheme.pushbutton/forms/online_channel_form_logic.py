# -*- coding: utf-8 -*-
"""Online source for Excel2ColorScheme.

Pull the resolved project color book from enneadtab.com (no Excel file needed) and apply it to the
Department + Program color schemes. Only the SOURCE differs from the dual-channel Excel flow; the
apply path (REVIT_COLOR_SCHEME.apply_color_dict_to_scheme) is the same, so colors land identically.

IronPython 2.7 (pyRevit): .format() not f-strings, no type hints, fully-qualified EnneadTab imports.
Token is acquired the Revit-safe way: AUTH.get_token() is NON-BLOCKING (never freezes the UI thread).
"""
from pyrevit import forms  # pyright: ignore
from Autodesk.Revit import DB  # pyright: ignore

from EnneadTab import NOTIFICATION, COLOR, AUTH
from EnneadTab.REVIT import REVIT_COLOR_SCHEME


def _get_all_color_schemes(doc):
    out = []
    coll = DB.FilteredElementCollector(doc).OfCategory(DB.BuiltInCategory.OST_ColorFillSchema)
    for cs in coll.WhereElementIsNotElementType().ToElements():
        out.append((cs.Name, cs))
    out.sort(key=lambda pair: pair[0])
    return out


def _fuzzy_default(schemes, keyword):
    """First (name, el) whose name contains keyword (case-insensitive), else (None, None)."""
    kw = keyword.lower()
    for name, el in schemes:
        if kw in name.lower():
            return (name, el)
    return (None, None)


def _to_hex_dict(color_map):
    """{name: {"abbr", "color": rgb}} -> {name: "#rrggbb"}, dropping entries with bad colors."""
    out = {}
    for name, info in color_map.items():
        hex_color = REVIT_COLOR_SCHEME._rgb_tuple_to_hex(info.get("color"))
        if hex_color:
            out[name] = hex_color
    return out


def show(doc):
    project_number = forms.ask_for_string(
        default="", prompt="Project number (e.g. 2512):", title="Online Color Book")
    if not project_number:
        return
    sector = forms.ask_for_string(
        default="HEALTHCARE", prompt="Sector:", title="Online Color Book")
    if not sector:
        return

    # Revit UI thread -> non-blocking get_token(). On None: kick off auth, tell the user to retry.
    token = AUTH.get_token()
    if not token:
        AUTH.request_auth()
        NOTIFICATION.messenger("Sign in to enneadtab.com, then re-run Online import.")
        return

    # Always a dict (COLOR returns the empty shape on auth/network trouble; never None).
    data = COLOR.get_color_template_data(
        source="online", project_number=project_number, sector=sector.upper(), token=token)
    dept_map = _to_hex_dict(data.get("department_color_map", {}))
    prog_map = _to_hex_dict(data.get("program_color_map", {}))
    if not dept_map and not prog_map:
        NOTIFICATION.messenger(
            "No colors returned. Check sign-in, project number ({}), and sector.".format(project_number))
        return

    schemes = _get_all_color_schemes(doc)
    if not schemes:
        NOTIFICATION.messenger("No color fill schemes in this document to update.")
        return
    by_name = dict(schemes)
    names = [n for n, _ in schemes]

    _, dept_el = _fuzzy_default(schemes, "Department")
    if dept_el is None:
        picked = forms.SelectFromList.show(names, title="Pick the DEPARTMENT color scheme")
        if not picked:
            return
        dept_el = by_name[picked]

    _, prog_el = _fuzzy_default(schemes, "Program")
    if prog_el is None:
        picked = forms.SelectFromList.show(names, title="Pick the PROGRAM color scheme")
        if not picked:
            return
        prog_el = by_name[picked]

    # Apply both channels in one transaction; roll back together on any failure.
    t = DB.Transaction(doc, "Online Color Book -> Schemes")
    t.Start()
    try:
        d_add, d_upd, _ = REVIT_COLOR_SCHEME.apply_color_dict_to_scheme(doc, dept_el, dept_map)
        p_add, p_upd, _ = REVIT_COLOR_SCHEME.apply_color_dict_to_scheme(doc, prog_el, prog_map)
        t.Commit()
        NOTIFICATION.messenger(
            u"Applied online color book:\n  Dept +{}/\u0394{}\n  Program +{}/\u0394{}".format(
                d_add, d_upd, p_add, p_upd))
    except Exception as ex:
        t.RollBack()
        NOTIFICATION.messenger("Apply failed (rolled back both schemes): {}".format(ex))
