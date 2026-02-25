#!/usr/bin/python
# -*- coding: utf-8 -*-

__doc__ = """Set grid visibility and grid bubble location per level from Excel view list. Reads Level Name, View Name, and Source of truth for this level from J drive Excel (Sheet1). Source-of-truth views define the reference: grid visibility (hidden/shown) and bubble position are copied from the SOT view to all other views on that level."""
__title__ = "Set Grid Bubble From Excel"

import proDUCKtion  # pyright: ignore
proDUCKtion.validify()

import os
import time

from pyrevit import script

from EnneadTab import ERROR_HANDLE, NOTIFICATION, EXCEL, DATA_CONVERSION
from EnneadTab.REVIT import REVIT_APPLICATION, REVIT_VIEW
from Autodesk.Revit import DB  # pyright: ignore

doc = REVIT_APPLICATION.get_doc()

EXCEL_PATH = r"J:\2142\6_Team\BS\NYU-SUF View List.xlsx"
WORKSHEET = "Sheet1"
HEADER_ROW = 1

COL_LEVEL_NAME = "Level Name"
COL_VIEW_NAME = "View Name"
COL_SOURCE_OF_TRUTH = "Source of truth for this level"

REQUIRED_COLUMNS = [COL_LEVEL_NAME, COL_VIEW_NAME, COL_SOURCE_OF_TRUTH]
SOURCE_OF_TRUTH_VALUES = ("yes", "y", "1", "true")

# Level/view strings that are invalid (Excel artifacts or empty-like); skip rows with these.
# _x000D_ / _x000A_ are OOXML escapes for carriage return (U+000D) and line feed (U+000A).
INVALID_LEVEL_OR_VIEW = ("none", "_x000d_", "_x000a_", "")


def _normalize_cell(s):
    """Strip whitespace and control chars; return empty string if None or invalid."""
    if s is None:
        return ""
    t = str(s).replace("\r", "").replace("\n", "").strip()
    if t.lower() in INVALID_LEVEL_OR_VIEW:
        return ""
    return t


def get_cell_value(data, row, col):
    """Get cell value from Excel data dict. Handles (row,col) 1-based and value as dict with 'value' key or plain."""
    key = (row, col)
    cell = data.get(key)
    if cell is None:
        return None
    if isinstance(cell, dict) and "value" in cell:
        return cell["value"]
    return cell


def parse_excel_to_mappings(data, header_to_col, output):
    """Build REF_VIEWS and VIEWS_TO_MODIFY. Abort on any validation failure."""
    if not isinstance(data, dict):
        msg = "parse_excel_to_mappings expects dict data (Excel return_dict=True). Abort."
        output.print_md("**ERROR:** " + msg)
        raise RuntimeError(msg)
    rows_by_number = set()
    for (row, _) in data.keys():
        if row > HEADER_ROW:
            rows_by_number.add(row)
    data_rows = sorted(rows_by_number)

    if not data_rows:
        msg = "Empty data: no rows after header (row {}).".format(HEADER_ROW)
        output.print_md("**ERROR:** " + msg)
        raise RuntimeError(msg)

    ref_views = {}
    views_to_modify = []
    skipped_rows = []

    for row in data_rows:
        level_name = get_cell_value(data, row, header_to_col[COL_LEVEL_NAME])
        view_name = get_cell_value(data, row, header_to_col[COL_VIEW_NAME])
        sot_raw = get_cell_value(data, row, header_to_col[COL_SOURCE_OF_TRUTH])

        level_str = _normalize_cell(level_name)
        view_str = _normalize_cell(view_name)
        sot = (str(sot_raw).strip().lower() if sot_raw is not None else "") in SOURCE_OF_TRUTH_VALUES

        if not level_str or not view_str:
            skipped_rows.append(row)
            continue

        if sot:
            if level_str in ref_views:
                if ref_views[level_str] != view_str:
                    msg = "Conflicting source-of-truth for level [{}]: view [{}] vs [{}] (Excel row {}). Abort.".format(
                        level_str, ref_views[level_str], view_str, row)
                    output.print_md("**ERROR:** " + msg)
                    raise RuntimeError(msg)
                # Same level + same view: redundant row, keep existing
            else:
                ref_views[level_str] = view_str
        else:
            views_to_modify.append((view_str, level_str, row))

    if skipped_rows:
        output.print_md("Skipped {} row(s) with empty or invalid Level Name or View Name (Excel rows: {}).".format(
            len(skipped_rows), ", ".join(str(r) for r in sorted(skipped_rows)[:15])))
        if len(skipped_rows) > 15:
            output.print_md("  ... and {} more.".format(len(skipped_rows) - 15))

    if not ref_views and not views_to_modify:
        msg = "No valid data rows: every row has empty Level Name or View Name, or no source-of-truth. Abort."
        output.print_md("**ERROR:** " + msg)
        raise RuntimeError(msg)

    levels_to_modify = set(ln for (_, ln, _) in views_to_modify)
    level_to_rows = {}
    for (_, ln, r) in views_to_modify:
        level_to_rows.setdefault(ln, []).append(r)
    levels_without_ref = [ln for ln in levels_to_modify if ln not in ref_views]
    if levels_without_ref:
        parts = []
        for ln in levels_without_ref:
            rows_str = ", ".join(str(r) for r in sorted(level_to_rows.get(ln, [])))
            parts.append("[{}] (Excel row(s): {})".format(ln, rows_str))
        msg = "Level(s) have no source-of-truth row: {}. Abort.".format("; ".join(parts))
        output.print_md("**ERROR:** " + msg)
        raise RuntimeError(msg)

    view_to_levels = {}
    for view_str, level_str, _ in views_to_modify:
        view_to_levels.setdefault(view_str, set()).add(level_str)
    duplicate_view_levels = [(v, list(s)) for v, s in view_to_levels.items() if len(s) > 1]
    if duplicate_view_levels:
        parts = ["View(s) appear for multiple levels (one view has one level in Revit):"]
        for view_str, levels in duplicate_view_levels:
            parts.append("  View [{}] -> levels {}".format(view_str, levels))
        msg = "\n".join(parts)
        output.print_md("**ERROR:** " + msg.replace("\n", "  \n"))
        raise RuntimeError(msg)

    return ref_views, views_to_modify


@ERROR_HANDLE.try_catch_error()
def set_grid_bubble_from_excel():
    output = script.get_output()
    output.close_others()

    output.print_md("**Set Grid Bubble From Excel** – reading {}".format(EXCEL_PATH))

    if doc is None:
        msg = "No Revit document open. Abort."
        output.print_md("**ERROR:** " + msg)
        raise RuntimeError(msg)

    if not os.path.isfile(EXCEL_PATH):
        msg = "Excel file not found or not a file: {}".format(EXCEL_PATH)
        output.print_md("**ERROR:** " + msg)
        raise RuntimeError(msg)

    raw_data = EXCEL.read_data_from_excel(EXCEL_PATH, worksheet=WORKSHEET, return_dict=True)
    if not raw_data:
        msg = "Failed to read Excel or worksheet '{}' is missing/empty.".format(WORKSHEET)
        output.print_md("**ERROR:** " + msg)
        raise RuntimeError(msg)
    if not isinstance(raw_data, dict):
        msg = "Excel read returned unexpected type (expected dict). Abort."
        output.print_md("**ERROR:** " + msg)
        raise RuntimeError(msg)

    num_cells = len(raw_data)
    row_count = len(set(k[0] for k in raw_data.keys()))
    output.print_md("Read {} rows from Sheet1 ({} cells).".format(row_count, num_cells))

    try:
        header_map = EXCEL.get_header_map(raw_data, header_row=HEADER_ROW)
    except (KeyError, TypeError) as e:
        msg = "Excel data format unexpected (cells may not have 'value' key). Check file. Detail: {}".format(str(e))
        output.print_md("**ERROR:** " + msg)
        raise RuntimeError(msg)

    if not header_map:
        msg = "No headers found in row {}.".format(HEADER_ROW)
        output.print_md("**ERROR:** " + msg)
        raise RuntimeError(msg)

    missing = [c for c in REQUIRED_COLUMNS if c not in header_map.values()]
    if missing:
        msg = "Required column(s) missing: {}. Abort.".format(", ".join(missing))
        output.print_md("**ERROR:** " + msg)
        raise RuntimeError(msg)

    header_to_col = EXCEL.flip_dict(header_map)
    for col_name in REQUIRED_COLUMNS:
        if col_name not in header_to_col:
            msg = "Required column missing after parse (duplicate header?): [{}]. Abort.".format(col_name)
            output.print_md("**ERROR:** " + msg)
            raise RuntimeError(msg)

    ref_views, views_to_modify = parse_excel_to_mappings(raw_data, header_to_col, output)

    output.print_md("Parsed: **{}** levels with source-of-truth, **{}** views to modify.".format(
        len(ref_views), len(views_to_modify)))
    for level_name, view_name in ref_views.items():
        output.print_md("  Level [{}] -> ref view [{}]".format(level_name, view_name))

    ref_views_resolved = {}
    missing_refs = []
    for level_name, view_name in ref_views.items():
        view = REVIT_VIEW.get_view_by_name(view_name)
        if view is None:
            missing_refs.append((level_name, view_name))
        else:
            ref_views_resolved[level_name] = view

    if missing_refs:
        parts = ["Source-of-truth view not in document:"]
        for level_name, view_name in missing_refs:
            parts.append("  Level [{}] -> view [{}] not found.".format(level_name, view_name))
        msg = "\n".join(parts)
        output.print_md("**ERROR:** " + msg.replace("\n", "  \n"))
        raise RuntimeError(msg)

    output.print_md("All ref views resolved.")

    output.print_md("Updating grid bubbles for **{}** views...".format(len(views_to_modify)))

    t = DB.Transaction(doc, __title__)
    t.Start()

    updated_count = 0
    try:
        for view_name, level_name, excel_row in views_to_modify:
            start_time = time.time()
            output.print_md("\nWorking on [{}] (level: {}, Excel row: {})".format(view_name, level_name, excel_row))

            view = REVIT_VIEW.get_view_by_name(view_name)
            if view is None:
                msg = "View not in document: [{}]. Abort.".format(view_name)
                output.print_md("**ERROR:** " + msg)
                t.RollBack()
                raise RuntimeError(msg)

            if level_name not in ref_views_resolved:
                msg = "Level [{}] has no source-of-truth in REF_VIEWS. Abort.".format(level_name)
                output.print_md("**ERROR:** " + msg)
                t.RollBack()
                raise RuntimeError(msg)

            ref_view = ref_views_resolved[level_name]
            if view.GenLevel is None:
                msg = "View [{}] has no associated level (e.g. drafting). Abort.".format(view_name)
                output.print_md("**ERROR:** " + msg)
                t.RollBack()
                raise RuntimeError(msg)

            actual_level = view.GenLevel.Name
            if actual_level != level_name:
                msg = "View [{}] is on level [{}] in Revit but Excel says level [{}]. Abort.".format(
                    view_name, actual_level, level_name)
                output.print_md("**ERROR:** " + msg)
                t.RollBack()
                raise RuntimeError(msg)

            all_grids = DB.FilteredElementCollector(doc, view.Id).OfClass(DB.Grid).WhereElementIsNotElementType().ToElements()
            for grid in all_grids:
                try:
                    ref_hidden = grid.IsHidden(ref_view)
                    cur_hidden = grid.IsHidden(view)
                    if ref_hidden != cur_hidden:
                        grid_ids = DATA_CONVERSION.list_to_system_list([grid.Id])
                        if ref_hidden:
                            view.HideElements(grid_ids)
                        else:
                            view.UnhideElements(grid_ids)
                except Exception as e:
                    msg = "Grid visibility failed: view [{}], grid [{}]: {}.".format(view_name, grid.Name, str(e))
                    output.print_md("**ERROR:** " + msg)
                    t.RollBack()
                    raise RuntimeError(msg)

                # Each grid has two ends (End0, End1); handle bubble and extent per end.
                for grid_end in [DB.DatumEnds.End0, DB.DatumEnds.End1]:
                    try:
                        # Bubble visibility for this end (show/hide bubble)
                        is_show_bubble = grid.IsBubbleVisibleInView(grid_end, ref_view)
                        if is_show_bubble:
                            grid.ShowBubbleInView(grid_end, view)
                        else:
                            grid.HideBubbleInView(grid_end, view)

                        # 2D extent for this end (type + curve in view)
                        extent_type = grid.GetDatumExtentTypeInView(grid_end, ref_view)
                        curves = grid.GetCurvesInView(extent_type, ref_view)
                        if not curves or len(curves) == 0:
                            msg = "Ref view has no curve for grid [{}] end [{}]. Abort.".format(grid.Name, grid_end)
                            output.print_md("**ERROR:** " + msg)
                            t.RollBack()
                            raise RuntimeError(msg)
                        grid.SetDatumExtentType(grid_end, view, extent_type)
                        grid.SetCurveInView(extent_type, view, curves[0])

                        # Leader for this end
                        leader = grid.GetLeader(grid_end, ref_view)
                        if leader and grid.IsLeaderValid(grid_end, view, leader):
                            current_leader = grid.GetLeader(grid_end, view)
                            if not current_leader:
                                grid.AddLeader(grid_end, view)
                            grid.SetLeader(grid_end, view, leader)
                    except Exception as e:
                        err_str = str(e)
                        if "unbound or not coincident" in err_str or "Parameter name: curve" in err_str:
                            view_link = output.linkify(view.Id, title=view_name)
                            grid_link = output.linkify(grid.Id, title=grid.Name)
                            msg = (
                                "Grid extent/curve from ref view cannot be applied in this view: "
                                "view {}, grid {}, end [{}] (Excel row {}). "
                                "The curve is unbound or not coincident with the datum in the target view. "
                                "Revit error: {}."
                            ).format(view_link, grid_link, grid_end, excel_row, err_str)
                            output.print_md("**ERROR:** " + msg)
                            output.print_md("**Suggestions:**")
                            output.print_md("1. Revit requires the curve to be **bound** and **coincident** with the grid's original 3D curve in the target view. Copying from another view can fail if crop, scope, or view extent differs.")
                            output.print_md("2. Use Revit's built-in **Propagate Extents**: select the grid(s) in the source-of-truth view, then use Propagate Extents to the target view(s) to copy 2D extents manually.")
                            output.print_md("3. Ensure the source-of-truth view and target view both show the same level and that the grid is visible and within crop in both.")
                            output.print_md("4. If the grid was just revealed in the target view, try adjusting its 2D extent manually in the target view once, then re-run this tool.")
                            t.RollBack()
                            raise RuntimeError(msg)
                        else:
                            view_link = output.linkify(view.Id, title=view_name)
                            grid_link = output.linkify(grid.Id, title=grid.Name)
                            msg = "Grid/leader failed: view {}, grid {}, end [{}]: {}.".format(
                                view_link, grid_link, grid_end, err_str)
                            output.print_md("**ERROR:** " + msg)
                            t.RollBack()
                            raise RuntimeError(msg)

            elapsed = time.time() - start_time
            output.print_md("  Done in {:.2f}s  {}".format(elapsed, output.linkify(view.Id, title=view.Name)))
            updated_count += 1

        t.Commit()
    except Exception:
        try:
            t.RollBack()
            output.print_md("**Transaction rolled back** due to error.")
        except Exception:
            pass
        raise

    output.print_md("\n**Finished.** Updated {} views.".format(updated_count))
    NOTIFICATION.messenger("Done!")


if __name__ == "__main__":
    set_grid_bubble_from_excel()
