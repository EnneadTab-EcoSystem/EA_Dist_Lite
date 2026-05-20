#!/usr/bin/python
# -*- coding: utf-8 -*-


__doc__ = """Update NYULI Kips Bay (Proj. 2538) Revit color schemes from the
project's color template Excel.

Source:
J:\\2538\\2_Master File\\B-70_Programming\\04_Colors\\Color Scheme_NYULI Kips Bay.xlsx

The Excel uses the firm Ennead Healthcare dual-pair layout:
    A: Department (full name)   B: Department Abbr.   C: Department Color
    D: Program (full name)      E: Program Abbr.      F: Program Color

For Kips Bay specifically, only the "CANCER CENTER" worksheet is loaded;
the "HEALTHCARE" sheet is intentionally excluded per team decision
(2026-05-20 -- the Kips Bay floor plates only use the Cancer Center
color set, and HEALTHCARE + CANCER CENTER are meant to live in two
independent color schemes, never combined).

Loaded targets:
    department  ->  "Department Type_Primary"
    program     ->  "Program Type_Primary"

NOTE: full names from col A / col D are used as Revit entry names,
NOT the abbreviations in col B / col E.

Multi-sheet merge logic with conflict detection is preserved below in
case a future project needs it -- just add sheet names to SOURCE_SHEETS.
With a single sheet, no conflicts can fire by construction.
"""
__title__ = "Load NYULI Kips Bay\nColor Template"


from pyrevit import script

import proDUCKtion  # pyright: ignore
proDUCKtion.validify()

from EnneadTab import ERROR_HANDLE, COLOR, NOTIFICATION, OUTPUT
from EnneadTab.REVIT import REVIT_SELECTION, REVIT_FORMS

from Autodesk.Revit import DB  # pyright: ignore

doc = __revit__.ActiveUIDocument.Document  # pyright: ignore


# ----------------------------------------------------------------------------
# Log file: every diagnostic + per-element scan result writes here so the team
# can share one file rather than copy-pasting a long pyRevit output buffer.
# ----------------------------------------------------------------------------
import os
import datetime

_LOG_PATH = None


def _open_log_file():
    """Open a fresh log file in %TEMP%; record path globally."""
    global _LOG_PATH
    try:
        ts = datetime.datetime.now().strftime("%Y%m%d_%H%M%S")
        tmp = (
            os.environ.get("TEMP")
            or os.environ.get("TMP")
            or os.path.expanduser("~")
            or "."
        )
        _LOG_PATH = os.path.join(
            tmp, "load_color_template_2538_{}.log".format(ts)
        )
        with open(_LOG_PATH, "w") as f:
            f.write("[{}] log opened\n".format(datetime.datetime.now().isoformat()))
    except Exception as e:
        _LOG_PATH = None
        print ("Failed to open log file: {}".format(e))


def _log(msg):
    """Append one line to the log file; safe no-op if open failed."""
    if _LOG_PATH is None:
        return
    try:
        with open(_LOG_PATH, "a") as f:
            f.write("[{}] {}\n".format(datetime.datetime.now().isoformat(), msg))
    except Exception:
        pass


EXCEL_PATH = "J:\\2538\\2_Master File\\B-70_Programming\\04_Colors\\Color Scheme_NYULI Kips Bay.xlsx"

# Sheets are read in order; the LAST sheet wins on entry-name conflict.
# Kips Bay uses CANCER CENTER only -- HEALTHCARE intentionally excluded
# (see __doc__ above for rationale). Add more sheets here if a future
# Kips Bay phase needs to overlay another color set.
SOURCE_SHEETS = ["CANCER CENTER"]

# Which merged data key feeds which Revit color scheme.
NAMING_MAP = {
    "department_color_map": ["Department Type_Primary"],
    "program_color_map":    ["Program Type_Primary"],
}


def _read_all_sheets(excel_path, source_sheets):
    """Read every source sheet once; return per_sheet[sheet] = data dict."""
    per_sheet = {}
    for sheet in source_sheets:
        try:
            per_sheet[sheet] = COLOR.get_color_template_data(excel_path, worksheet=sheet)
        except Exception as e:
            print ("Failed to read sheet [{}]: {}".format(sheet, e))
            per_sheet[sheet] = {"department_color_map": {}, "program_color_map": {}}
    return per_sheet


def _merge_template_data(per_sheet, source_sheets):
    """Merge with last-sheet-wins; also return conflict report.

    Returns:
        (merged, conflicts)
        merged    : same shape as a single get_color_template_data() return.
        conflicts : {map_key: {entry_name: [(sheet, color), ...]}} listing
                    every entry that appeared in >1 sheet with differing
                    colors. List order matches SOURCE_SHEETS reading order
                    so the LAST tuple is the winner.
    """
    merged    = {"department_color_map": {}, "program_color_map": {}}
    conflicts = {"department_color_map": {}, "program_color_map": {}}

    for map_key in ("department_color_map", "program_color_map"):
        all_occurrences = {}  # entry_name -> [(sheet, color, full_value), ...]
        for sheet in source_sheets:
            sheet_map = per_sheet.get(sheet, {}).get(map_key, {}) or {}
            for entry_name, entry_value in sheet_map.items():
                all_occurrences.setdefault(entry_name, []).append(
                    (sheet, entry_value.get("color"), entry_value)
                )

        for entry_name, occurrences in all_occurrences.items():
            # Last occurrence wins (per SOURCE_SHEETS ordering).
            merged[map_key][entry_name] = occurrences[-1][2]
            # ExcelHandler returns colors as lists ([R, G, B]) because they
            # round-trip through JSON. Lists aren't hashable, so tuple-cast
            # before putting them in a set for conflict detection.
            distinct_colors = set(
                tuple(c) if c is not None else None
                for (_s, c, _v) in occurrences
            )
            if len(distinct_colors) > 1:
                conflicts[map_key][entry_name] = [
                    (s, c) for (s, c, _v) in occurrences
                ]

    return merged, conflicts


def _markdown_text(text, color_rgb):
    """Wrap text in colored HTML span for pyRevit output."""
    return '<span style="color:rgb{};">{}</span>'.format(
        str(tuple(color_rgb)), text
    )


def _report_conflicts(conflicts):
    """Surface merge conflicts both to pyRevit output and as a toast."""
    total = sum(len(d) for d in conflicts.values())
    if total == 0:
        output.print_md("## Merge: no entry-name conflicts between sheets.")
        return

    output.print_md("# DISCREPANCIES FOUND DURING SHEET MERGE")
    output.print_md(
        "The following entries appear in multiple sheets with different "
        "colors. The **last sheet ({}) wins**. Please review and consider "
        "aligning the source Excel if these were unintentional.".format(
            SOURCE_SHEETS[-1]
        )
    )

    for map_key in ("department_color_map", "program_color_map"):
        sub = conflicts[map_key]
        if not sub:
            continue
        label = "Department" if map_key.startswith("department") else "Program"
        output.print_md("## {} discrepancies ({})".format(label, len(sub)))
        for entry_name, occurrences in sub.items():
            winner_sheet, winner_color = occurrences[-1]
            output.print_md(
                "**{}**  ->  winner: {} -> {}".format(
                    entry_name,
                    winner_sheet,
                    _markdown_text("RGB={}".format(winner_color), winner_color),
                )
            )
            for sheet, color in occurrences:
                output.print_md(
                    "  - {}: {}".format(
                        sheet,
                        _markdown_text("RGB={}".format(color), color),
                    )
                )

    NOTIFICATION.messenger(
        "{} entry conflict(s) between sheets resolved by '{} wins'.\n"
        "See pyRevit output window for the full list.".format(
            total, SOURCE_SHEETS[-1]
        )
    )


def _find_near_match(revit_name, excel_keys):
    """Find best fuzzy match for a Revit entry name within Excel template keys.

    Returns (excel_key, confidence_label) or None. Match tiers in priority:
        1. Case-insensitive exact match     -> "case match"
        2. Substring containment (>= 3 chr) -> "Excel contains Revit" / "Revit contains Excel"
        3. Acronym (2-5 letter all-caps)    -> "acronym match"
    """
    if not revit_name:
        return None
    rn = str(revit_name).strip()
    rn_lower = rn.lower()
    rn_upper = rn.upper()

    for ek in excel_keys:
        if ek and str(ek).strip().lower() == rn_lower:
            return (ek, "case match")

    if len(rn_lower) >= 3:
        for ek in excel_keys:
            ek_lower = str(ek).strip().lower()
            if rn_lower in ek_lower:
                return (ek, "Excel name contains Revit name")
            if ek_lower in rn_lower:
                return (ek, "Revit name contains Excel name")

    if rn_upper.isalpha() and 2 <= len(rn_upper) <= 5:
        for ek in excel_keys:
            ek_text = (
                str(ek).replace("/", " ").replace("(", " ").replace(")", " ").replace("-", " ")
            )
            words = ek_text.split()
            initials = "".join(w[0] for w in words if w and w[0].isalpha()).upper()
            if initials == rn_upper:
                return (ek, "acronym match")

    return None


def _get_param_name(doc, param_id):
    """Best-effort: derive the parameter NAME from its ParameterId.

    For built-in params (negative IntegerValue), use LabelUtils.GetLabelFor;
    for shared/project params, fetch the ParameterElement and read .Name.
    Returns None if neither path resolves.
    """
    if param_id is None or doc is None:
        return None
    try:
        if hasattr(param_id, "IntegerValue") and param_id.IntegerValue < 0:
            try:
                bip = DB.BuiltInParameter(param_id.IntegerValue)
                return DB.LabelUtils.GetLabelFor(bip)
            except Exception:
                pass
    except Exception:
        pass
    try:
        pe = doc.GetElement(param_id)
        if pe is not None:
            name = getattr(pe, "Name", None)
            if name:
                return name
    except Exception:
        pass
    return None


def _get_scheme_parameter(elem, param_id, doc=None):
    """Read the color-scheme parameter from an element via multi-path fallback.

    Tries in order:
      1. BuiltInParameter (negative IntegerValue) -> elem.get_Parameter(BIP)
      2. Direct ElementId lookup                  -> elem.get_Parameter(id)
      3. Parameter name lookup (project/shared)   -> elem.LookupParameter(name)

    Path 3 catches the common case where the color scheme is keyed on a
    project parameter (e.g. "Department Type" / "Program Type") -- those
    return None for both BIP and direct-Id lookups on the element but
    resolve via LookupParameter(name).
    """
    if param_id is None:
        return None
    try:
        if hasattr(param_id, "IntegerValue") and param_id.IntegerValue < 0:
            try:
                bip = DB.BuiltInParameter(param_id.IntegerValue)
                p = elem.get_Parameter(bip)
                if p is not None:
                    return p
            except Exception:
                pass
    except Exception:
        pass
    try:
        p = elem.get_Parameter(param_id)
        if p is not None:
            return p
    except Exception:
        pass
    if doc is not None:
        try:
            name = _get_param_name(doc, param_id)
            if name:
                p = elem.LookupParameter(name)
                if p is not None:
                    return p
        except Exception:
            pass
    return None


def _read_param_string(p):
    """Read a Parameter as a string, tolerating String / ElementId / numeric storage.

    For key-schedule (ElementId) params, AsString() returns None and the
    display string lives in AsValueString(); we try both.
    """
    if p is None:
        return None
    try:
        st = p.StorageType
    except Exception:
        st = None
    try:
        if st == DB.StorageType.String:
            return p.AsString()
    except Exception:
        pass
    try:
        v = p.AsValueString()
        if v is not None:
            return v
    except Exception:
        pass
    try:
        return p.AsString()
    except Exception:
        return None


_SCHEME_DIAG_DONE = {}    # scheme_name -> True once diagnostic printed
_INFERRED_PARAM_CACHE = {}  # scheme_name -> inferred parameter NAME


def _infer_parameter_name(doc, color_scheme, sample_cap=50):
    """Infer the scheme's underlying parameter by data matching.

    color_scheme.Title is the legend label, NOT the parameter name (a
    Kips Bay project uses Title='Department Type' while the actual
    parameter is 'Rooms_$LS_Occupancy Type'). ParameterId may also be
    missing in some Revit versions.

    Strategy: collect every entry's StringValue from the scheme. Walk
    placed elements; for each, iterate every Parameter and count how
    often each parameter NAME holds a value that exactly matches one
    of the entry strings. The parameter with the most matches wins.

    Requires >= 3 matches to be confident; below that, returns None
    (so candidate-name search can fall through to other heuristics).
    """
    try:
        cache_key = color_scheme.Name
    except Exception:
        cache_key = id(color_scheme)
    if cache_key in _INFERRED_PARAM_CACHE:
        return _INFERRED_PARAM_CACHE[cache_key]

    result = None
    try:
        entry_values = set()
        for e in color_scheme.GetEntries():
            try:
                v = e.GetStringValue()
                if v:
                    entry_values.add(v)
            except Exception:
                continue
        if not entry_values:
            _INFERRED_PARAM_CACHE[cache_key] = result
            return result

        try:
            cat_id = color_scheme.CategoryId
        except Exception:
            cat_id = None

        scan_cats = []
        if cat_id is not None:
            scan_cats.append(cat_id)
        for bic in (DB.BuiltInCategory.OST_Rooms, DB.BuiltInCategory.OST_Areas):
            try:
                fb = DB.ElementId(bic)
                if all(str(fb) != str(c) for c in scan_cats):
                    scan_cats.append(fb)
            except Exception:
                continue

        match_count = {}
        scanned = 0
        for scan_cat in scan_cats:
            try:
                collector = (
                    DB.FilteredElementCollector(doc)
                    .OfCategoryId(scan_cat)
                    .WhereElementIsNotElementType()
                )
            except Exception:
                continue
            for elem in collector:
                # Skip ghost / unplaced rooms.
                try:
                    if elem.Location is None:
                        continue
                except Exception:
                    continue
                scanned += 1
                if scanned > sample_cap:
                    break
                try:
                    for p in elem.Parameters:
                        try:
                            pname = p.Definition.Name
                        except Exception:
                            continue
                        v = _read_param_string(p)
                        if v and v in entry_values:
                            match_count[pname] = match_count.get(pname, 0) + 1
                except Exception:
                    continue
            if scanned > sample_cap:
                break

        if match_count:
            best_name, best_n = max(match_count.items(), key=lambda kv: kv[1])
            if best_n >= 3:
                result = best_name
                _log(
                    "inferred parameter for [{}]: '{}' ({} matches across "
                    "{} scanned placed elements; full counts={})".format(
                        cache_key, best_name, best_n, scanned, dict(match_count)
                    )
                )
            else:
                _log(
                    "inference inconclusive for [{}] (best='{}' with only "
                    "{} matches; counts={})".format(
                        cache_key, best_name, best_n, dict(match_count)
                    )
                )
    except Exception as e:
        _log("inference threw for [{}]: {}".format(cache_key, e))

    _INFERRED_PARAM_CACHE[cache_key] = result
    return result


def _candidate_param_names(scheme, resolved_name):
    """Return a short list of parameter names to probe via LookupParameter.

    Sources of candidate names (in priority order):
        1. scheme.Title           -- in modern Revit API this is the actual
                                     parameter name the scheme keys on
        2. resolved_name          -- ParameterElement.Name via doc.GetElement
        3. scheme.Name            -- the scheme's display name
        4. scheme.Name - suffix   -- strip _Primary / _Secondary / _Opt1 etc.
    """
    candidates = []
    # 1. scheme.Title (most reliable on recent Revit versions)
    try:
        title = scheme.Title
        if title:
            candidates.append(title)
    except Exception:
        pass
    # 2. resolved via ParameterElement
    if resolved_name:
        candidates.append(resolved_name)
    # 3. scheme.Name + suffix-stripped variants
    try:
        sn = scheme.Name
    except Exception:
        sn = None
    if sn:
        candidates.append(sn)
        for suffix in ("_Primary", "_Secondary", "_Opt1", "_Opt2", "_OPT1", "_OPT2"):
            if sn.endswith(suffix):
                candidates.append(sn[: -len(suffix)])
    # Dedup while preserving order.
    seen = set()
    out = []
    for c in candidates:
        if c and c not in seen:
            seen.add(c)
            out.append(c)
    return out


def _print_scheme_diagnostic(doc, color_scheme):
    """Print scheme metadata + sample element values, once per scheme per run.

    Called at the START of scanning each scheme (eager, not lazy) so it
    always appears in pyRevit output regardless of whether any orphan
    triggers a Tier-2 element scan.
    """
    key = color_scheme.Name if color_scheme is not None else "<unknown>"
    if _SCHEME_DIAG_DONE.get(key):
        return
    _SCHEME_DIAG_DONE[key] = True

    try:
        cat_id = color_scheme.CategoryId
    except Exception:
        cat_id = None
    try:
        param_id = color_scheme.ParameterId
    except Exception:
        param_id = None

    param_name = _get_param_name(doc, param_id) if param_id is not None else None
    param_int = "?"
    try:
        if param_id is not None:
            param_int = param_id.IntegerValue
    except Exception:
        pass

    candidates = _candidate_param_names(color_scheme, param_name)
    inferred = _infer_parameter_name(doc, color_scheme)
    if inferred and inferred not in candidates:
        candidates.insert(0, inferred)   # data-derived guess goes FIRST

    # Scan up to 10 PLACED elements across BOTH OST_Rooms AND OST_Areas
    # (future-proof: a team may use either or both categories for the
    # same conceptual scheme). For each, dump ALL non-empty parameters
    # with no truncation cap so the team can spot which parameter name
    # actually holds the value (e.g. 'Imaging' / 'Lobby').
    samples = []
    elem_total = 0
    placed_count = 0

    def _elem_id_safe(e):
        try:
            return str(e.Id.IntegerValue)
        except Exception:
            try:
                return str(e.Id)
            except Exception:
                return "?"

    def _elem_name_safe(e):
        # Try multiple paths since Element.Name varies by category.
        for getter in (
            lambda x: x.Name,
            lambda x: x.LookupParameter("Name").AsString(),
            lambda x: x.get_Parameter(DB.BuiltInParameter.ROOM_NAME).AsString(),
            lambda x: x.get_Parameter(DB.BuiltInParameter.ROOM_NUMBER).AsString(),
        ):
            try:
                v = getter(e)
                if v:
                    return str(v)
            except Exception:
                continue
        return ""

    def _is_placed(e):
        try:
            if e.Location is None:
                return False
        except Exception:
            return False
        for bip in (DB.BuiltInParameter.ROOM_AREA,):
            try:
                ap = e.get_Parameter(bip)
                if ap is not None:
                    if ap.AsDouble() <= 0:
                        return False
            except Exception:
                pass
        return True

    # Iterate the scheme's stated category PLUS the other room/area
    # category, so future schemes that mix categories still get sampled.
    diag_categories = []
    try:
        diag_categories.append(cat_id)
    except Exception:
        pass
    for fallback_bic in (DB.BuiltInCategory.OST_Rooms, DB.BuiltInCategory.OST_Areas):
        try:
            fb_id = DB.ElementId(fallback_bic)
            if all(str(fb_id) != str(c) for c in diag_categories):
                diag_categories.append(fb_id)
        except Exception:
            pass

    for scan_cat in diag_categories:
        if placed_count >= 10:
            break
        try:
            sample_collector = (
                DB.FilteredElementCollector(doc)
                .OfCategoryId(scan_cat)
                .WhereElementIsNotElementType()
            )
        except Exception:
            continue
        cat_count_local = 0
        for elem in sample_collector:
            cat_count_local += 1
            elem_total += 1
            if placed_count >= 10:
                continue
            if not _is_placed(elem):
                continue
            placed_count += 1

            elem_id_str = _elem_id_safe(elem)
            elem_name = _elem_name_safe(elem)
            samples.append(
                "  PLACED #{} cat={} id={} name='{}'".format(
                    placed_count, scan_cat, elem_id_str, elem_name
                )
            )

            # All non-empty parameters (NO cap) so we can see everything.
            all_params = []
            try:
                for p in elem.Parameters:
                    try:
                        pname = p.Definition.Name
                    except Exception:
                        continue
                    v = _read_param_string(p)
                    if v is None or v == "":
                        continue
                    all_params.append("    '{}' = '{}'".format(pname, v))
            except Exception:
                pass
            if all_params:
                samples.extend(all_params)
            else:
                samples.append("    (no non-empty parameters via iteration)")

            # Also try lookup paths explicitly.
            explicit_row = ["    [via lookup paths]"]
            p_main = _get_scheme_parameter(elem, param_id, doc=doc)
            v_main = _read_param_string(p_main)
            explicit_row.append(
                "byId={}".format(repr(v_main) if v_main is not None else "<None>")
            )
            for name in candidates:
                try:
                    p_named = elem.LookupParameter(name)
                    v_named = _read_param_string(p_named)
                    explicit_row.append(
                        "{}={}".format(name, repr(v_named) if v_named is not None else "<None>")
                    )
                except Exception:
                    explicit_row.append("{}=<error>".format(name))
            samples.append("    " + " | ".join(explicit_row))

    # Also enumerate the scheme's own attributes so we can see why
    # ParameterId came back as None (possibly a different API name).
    scheme_attrs = []
    for attr in ("ParameterId", "CategoryId", "SchemeFieldType", "Name",
                 "ColorFillSchemeId", "IsByValue", "Title"):
        try:
            val = getattr(color_scheme, attr, "<missing>")
            scheme_attrs.append("    {} = {!r}".format(attr, val))
        except Exception as ee:
            scheme_attrs.append("    {} = <error: {}>".format(attr, ee))

    diag_block = (
        "Scan diagnostic for [{}]:\n"
        "  - CategoryId: {}\n"
        "  - ParameterId: {} (IntegerValue={})\n"
        "  - Resolved name via ParameterElement: '{}'\n"
        "  - Candidate parameter names to probe: {}\n"
        "  - Category element count (total, incl. unplaced): {}\n"
        "  - Color scheme attributes (raw):\n{}\n"
        "  - First 3 PLACED elements, full parameter dump:\n{}".format(
            key, cat_id, param_id, param_int,
            param_name or "<unresolved>",
            candidates if candidates else "(none)",
            elem_total,
            "\n".join(scheme_attrs) if scheme_attrs else "    (no attributes captured)",
            "\n".join(samples) if samples else "  (no placed elements in category)",
        )
    )
    output.print_md("**" + diag_block.split("\n", 1)[0] + "**\n" + diag_block.split("\n", 1)[1])
    _log("=== " + diag_block + " ===")


def _find_elements_with_value(doc, color_scheme, value):
    """Return list of category-scoped elements whose color-scheme param equals value."""
    if value is None:
        return []
    try:
        cat_id = color_scheme.CategoryId
    except Exception:
        cat_id = None
    try:
        param_id = color_scheme.ParameterId
    except Exception:
        param_id = None
    if cat_id is None or param_id is None:
        return []

    # Strategy: try the byId lookup first (built-in or shared/project via ID).
    # If that returns nothing, fall back to LookupParameter using every name
    # we can derive from the scheme. Whichever path finds matches wins; if
    # none do, return empty (and the diagnostic block earlier in the output
    # tells the team why).
    #
    # Categories scanned: scheme's stated CategoryId first, then both
    # OST_Rooms and OST_Areas as fallbacks (future-proof for teams that
    # mix rooms + areas under one conceptual color scheme).
    param_name = _get_param_name(doc, param_id)
    candidates = _candidate_param_names(color_scheme, param_name)
    inferred = _infer_parameter_name(doc, color_scheme)
    if inferred and inferred not in candidates:
        candidates.insert(0, inferred)   # data-derived guess goes FIRST

    scan_categories = [cat_id]
    for fallback_bic in (DB.BuiltInCategory.OST_Rooms, DB.BuiltInCategory.OST_Areas):
        try:
            fb_id = DB.ElementId(fallback_bic)
            if all(str(fb_id) != str(c) for c in scan_categories):
                scan_categories.append(fb_id)
        except Exception:
            continue

    def _scan(get_value_fn, scan_cat):
        out = []
        try:
            collector = (
                DB.FilteredElementCollector(doc)
                .OfCategoryId(scan_cat)
                .WhereElementIsNotElementType()
            )
            for elem in collector:
                if get_value_fn(elem) == value:
                    out.append(elem)
        except Exception as e:
            print ("Error scanning elements for value '{}': {}".format(value, e))
        return out

    for scan_cat in scan_categories:
        # Path A: byId (built-in or direct ElementId lookup)
        results = _scan(
            lambda elem: _read_param_string(_get_scheme_parameter(elem, param_id, doc=doc)),
            scan_cat,
        )
        if results:
            _log(
                "scan byId-path matched {} element(s) for '{}' in cat={}".format(
                    len(results), value, scan_cat
                )
            )
            return results

        # Path B: LookupParameter by candidate name -- handles project /
        # shared params where the ParameterId binding doesn't resolve on
        # the instance.
        for name in candidates:
            def _by_name(elem, _n=name):
                try:
                    return _read_param_string(elem.LookupParameter(_n))
                except Exception:
                    return None
            rs = _scan(_by_name, scan_cat)
            if rs:
                _log(
                    "scan LookupParameter('{}') matched {} element(s) for "
                    "'{}' in cat={}".format(name, len(rs), value, scan_cat)
                )
                return rs

    _log(
        "scan returned 0 elements for '{}' across all lookup paths and "
        "categories {}".format(value, scan_categories)
    )
    return []


def _prompt_transfer(scheme_name, old_name, new_name, confidence, count):
    """Tier-2 prompt: near match found. Returns 'Transfer' / 'Skip' / 'Stop All'."""
    sub_text = (
        "Color scheme: [{}]\n"
        "Revit entry:        '{}'\n"
        "Excel near-match:   '{}'   ({})\n"
        "{} Revit element(s) currently use the value '{}'.\n"
        "\n"
        "Transferring will update the parameter value on those {} element(s) "
        "from '{}' (old) to '{}' (Excel), then delete the old Revit entry. "
        "Visual coloring stays intact -- the Excel entry holds the new color."
    ).format(
        scheme_name, old_name, new_name, confidence,
        count, old_name, count, old_name, new_name,
    )
    res = REVIT_FORMS.dialogue(
        title="Near match found",
        main_text="Transfer '{}' -> '{}'?".format(old_name, new_name),
        sub_text=sub_text,
        options=[
            ["Transfer", "Update parameter value on {} element(s); delete old entry".format(count)],
            ["Skip", "Keep the old entry in this scheme, leave elements as-is"],
            ["Stop All", "Skip all remaining orphan prompts in this run"],
        ],
        icon="warning",
    )
    return res


def _prompt_delete(scheme_name, old_name):
    """Tier-3 prompt: no match + not in use. Returns 'Delete' / 'Skip' / 'Stop All'."""
    sub_text = (
        "Color scheme: [{}]\n"
        "Revit entry:        '{}'\n"
        "Excel match:        none found\n"
        "Used by:            0 elements (safe to delete)\n"
        "\n"
        "Nothing references this entry, and the Excel template has no "
        "equivalent to migrate to."
    ).format(scheme_name, old_name)
    res = REVIT_FORMS.dialogue(
        title="Unmatched entry, not in use",
        main_text="Delete entry '{}'?".format(old_name),
        sub_text=sub_text,
        options=[
            ["Delete", "Remove this entry from the color scheme"],
            ["Skip", "Keep the entry, even though nothing uses it"],
            ["Stop All", "Skip all remaining orphan prompts in this run"],
        ],
        icon="warning",
    )
    return res


def _collect_orphan_decisions(doc, merged_data):
    """OUTSIDE transaction: scan all schemes, prompt user one-by-one, collect actions.

    Returns a list of approved-action dicts to be applied later inside the
    transaction. Doing prompts outside the transaction avoids Revit choking
    on modal dialogs that hold an open transaction.
    """
    approved = []
    stop_all = [False]   # mutable flag for nested loops

    for lookup_key, scheme_names in NAMING_MAP.items():
        template_data = merged_data.get(lookup_key, {}) or {}
        if not template_data:
            continue
        excel_keys = list(template_data.keys())
        for scheme_name in scheme_names:
            if stop_all[0]:
                break
            color_scheme = REVIT_SELECTION.get_color_scheme_by_name(scheme_name)
            if not color_scheme:
                continue
            # Eagerly print the diagnostic block at the top of this scheme's
            # processing so it's the FIRST thing the team sees if 0-element
            # transfers start happening.
            _print_scheme_diagnostic(doc, color_scheme)
            current_entries = list(color_scheme.GetEntries())
            for entry in current_entries:
                if stop_all[0]:
                    break
                try:
                    old_name = entry.GetStringValue()
                except Exception:
                    continue
                if old_name in template_data:
                    continue   # Tier 1 perfect match -- update step handles it.

                near = _find_near_match(old_name, excel_keys)
                if near is not None:
                    new_name, confidence = near
                    elements = _find_elements_with_value(doc, color_scheme, old_name)
                    res = _prompt_transfer(
                        scheme_name, old_name, new_name, confidence, len(elements)
                    )
                    if res == "Transfer":
                        approved.append({
                            "scheme": color_scheme,
                            "scheme_name": scheme_name,
                            "action": "transfer",
                            "old_entry": entry,
                            "old_name": old_name,
                            "new_name": new_name,
                            "elements": elements,
                        })
                    elif res == "Stop All":
                        stop_all[0] = True
                else:
                    # Tier 3: no fuzzy match. Skip silently if in use --
                    # there is no safe action without a manual remap target.
                    try:
                        can_remove = color_scheme.CanRemoveEntry(entry)
                    except Exception:
                        can_remove = False
                    if not can_remove:
                        output.print_md(
                            "??? [{}] entry [{}] has no Excel match AND is currently "
                            "in use -- silently kept (no safe action without a "
                            "remap target).".format(scheme_name, old_name)
                        )
                        continue
                    res = _prompt_delete(scheme_name, old_name)
                    if res == "Delete":
                        approved.append({
                            "scheme": color_scheme,
                            "scheme_name": scheme_name,
                            "action": "delete",
                            "old_entry": entry,
                            "old_name": old_name,
                        })
                    elif res == "Stop All":
                        stop_all[0] = True

    return approved


def _apply_orphan_decisions(doc, approved):
    """INSIDE transaction: apply each user-approved transfer/delete."""
    for act in approved:
        if act["action"] == "transfer":
            color_scheme = act["scheme"]
            new_name = act["new_name"]
            old_name = act["old_name"]
            elements = act["elements"]
            try:
                param_id = color_scheme.ParameterId
            except Exception:
                param_id = None
            transferred = 0
            for elem in elements:
                p = _get_scheme_parameter(elem, param_id, doc=doc) if param_id is not None else None
                if p is None or p.IsReadOnly:
                    continue
                try:
                    if p.Set(new_name):
                        transferred += 1
                except Exception:
                    continue
            entry = act["old_entry"]
            removed = False
            try:
                if color_scheme.CanRemoveEntry(entry):
                    color_scheme.RemoveEntry(entry)
                    removed = True
            except Exception as e:
                output.print_md(
                    "Failed to delete old entry [{}] after transfer: {}".format(old_name, e)
                )
            output.print_md(
                "**=>>** [{}] transferred {}/{} element(s) from [{}] to [{}]; "
                "old entry {}".format(
                    act["scheme_name"], transferred, len(elements),
                    old_name, new_name,
                    "deleted" if removed else "kept (CanRemoveEntry=False)",
                )
            )
        elif act["action"] == "delete":
            color_scheme = act["scheme"]
            old_name = act["old_name"]
            entry = act["old_entry"]
            try:
                if color_scheme.CanRemoveEntry(entry):
                    color_scheme.RemoveEntry(entry)
                    output.print_md(
                        "**---** [{}] entry [{}] deleted (user-approved, not in use)".format(
                            act["scheme_name"], old_name
                        )
                    )
                else:
                    output.print_md(
                        "Skipped delete of [{}] -- CanRemoveEntry returned False at "
                        "apply time (someone re-tagged an element?)".format(old_name)
                    )
            except Exception as e:
                output.print_md(
                    "Failed to delete entry [{}]: {}".format(old_name, e)
                )


def _add_missing_entry(color_scheme, template_data, current_entry_names, storage_type):
    for entry_name in template_data.keys():
        if entry_name in current_entry_names:
            continue
        entry = DB.ColorFillSchemeEntry(storage_type)
        entry.Color = COLOR.tuple_to_color(template_data[entry_name]["color"])
        entry.SetStringValue(entry_name)
        entry.FillPatternId = REVIT_SELECTION.get_solid_fill_pattern_id(doc)
        color_scheme.AddEntry(entry)
        output.print_md(
            "**+++** entry [{}] added with **{}**".format(
                entry_name,
                _markdown_text(
                    "COLOR RGB={}".format(template_data[entry_name]["color"]),
                    template_data[entry_name]["color"],
                ),
            )
        )


def _update_entry_color(color_scheme, template_data):
    for existing_entry in color_scheme.GetEntries():
        entry_title = existing_entry.GetStringValue()
        lookup = template_data.get(entry_title, None)
        if not lookup:
            output.print_md(
                "### ??? entry [{}] in current scheme has no match in merged "
                "template. New entry, or different spelling? Skipped.\n".format(
                    entry_title
                )
            )
            continue
        new_color = COLOR.tuple_to_color(lookup["color"])
        if COLOR.is_same_color(existing_entry.Color, new_color):
            continue
        old_rgb = (
            existing_entry.Color.Red,
            existing_entry.Color.Green,
            existing_entry.Color.Blue,
        )
        existing_entry.Color = new_color
        color_scheme.UpdateEntry(existing_entry)
        output.print_md(
            "**$$$** entry [{}] updated from **{}** to **{}**".format(
                entry_title,
                _markdown_text("OLD RGB={}".format(old_rgb), old_rgb),
                _markdown_text("NEW RGB={}".format(lookup["color"]), lookup["color"]),
            )
        )


def _update_color_scheme(merged_data, lookup_key, color_scheme_name):
    color_scheme = REVIT_SELECTION.get_color_scheme_by_name(color_scheme_name)
    if not color_scheme:
        NOTIFICATION.messenger(
            "Color Scheme [{}] not found in current document.\n"
            "Check the scheme name spelling.".format(color_scheme_name)
        )
        output.print_md(
            "## Color scheme **[{}]** NOT FOUND in document".format(color_scheme_name)
        )
        return

    template_data = merged_data.get(lookup_key, {})
    if not template_data:
        output.print_md("## No data for [{}] in merged template".format(lookup_key))
        return

    output.print_md("## Working on color scheme [{}]".format(color_scheme.Name))

    try:
        sample_entry = list(color_scheme.GetEntries())[0]
        storage_type = sample_entry.StorageType
    except Exception:
        NOTIFICATION.messenger(
            "Color scheme [{}] has no entries.\n"
            "Add at least one placeholder entry before running.".format(
                color_scheme_name
            )
        )
        return

    current_entry_names = [x.GetStringValue() for x in color_scheme.GetEntries()]
    _add_missing_entry(color_scheme, template_data, current_entry_names, storage_type)
    _update_entry_color(color_scheme, template_data)


@ERROR_HANDLE.try_catch_error()
def load_color_template():
    _open_log_file()
    output.print_md("# NYULI Kips Bay (Proj. 2538) - Load Color Template")
    output.print_md("Excel: `{}`".format(EXCEL_PATH))
    output.print_md(
        "Source sheets (LAST wins on conflict): {}".format(SOURCE_SHEETS)
    )
    if _LOG_PATH:
        output.print_md("Diagnostic log: `{}`".format(_LOG_PATH))
        _log("Excel: {}".format(EXCEL_PATH))
        _log("Source sheets: {}".format(SOURCE_SHEETS))

    per_sheet = _read_all_sheets(EXCEL_PATH, SOURCE_SHEETS)
    merged_data, conflicts = _merge_template_data(per_sheet, SOURCE_SHEETS)

    if not merged_data["department_color_map"] and not merged_data["program_color_map"]:
        NOTIFICATION.messenger("No color data could be read from the Excel template.")
        return

    output.print_md(
        "Loaded: **{}** department entries, **{}** program entries.".format(
            len(merged_data["department_color_map"]),
            len(merged_data["program_color_map"]),
        )
    )

    # OUTSIDE transaction: scan for orphan entries and gather user decisions.
    # Modal dialogs inside a Revit transaction can cause the transaction to
    # choke (UI state changes mid-flight); collect approvals first, then
    # apply them all in one transaction.
    output.print_md("### Scanning existing schemes for mismatched (orphan) entries...")
    approved_actions = _collect_orphan_decisions(doc, merged_data)
    if approved_actions:
        output.print_md(
            "User approved **{}** orphan action(s); applying inside transaction.".format(
                len(approved_actions)
            )
        )
    else:
        output.print_md("No orphan actions approved (or no orphans found).")

    t = DB.Transaction(doc, "Update NYULI Kips Bay Color Schemes")
    t.Start()
    try:
        # 1. Apply approved orphan transfers + deletes first so subsequent
        #    add/update sees a clean slate.
        _apply_orphan_decisions(doc, approved_actions)
        # 2. Then standard add-new + update-color for entries that already
        #    matched the Excel template exactly.
        for lookup_key, scheme_names in NAMING_MAP.items():
            for scheme_name in scheme_names:
                _update_color_scheme(merged_data, lookup_key, scheme_name)
        t.Commit()
    except Exception as e:
        t.RollBack()
        NOTIFICATION.messenger(
            "Failed to update color schemes:\n{}".format(e)
        )
        return

    _report_conflicts(conflicts)

    NOTIFICATION.messenger("NYULI Kips Bay color schemes updated!")
    OUTPUT.display_output_on_browser()


output = script.get_output()
output.close_others()


if __name__ == "__main__":
    load_color_template()
