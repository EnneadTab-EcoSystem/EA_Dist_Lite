#!/usr/bin/python
# -*- coding: utf-8 -*-

__doc__ = "Update a Revit color scheme from an Excel file where each row defines a value and its color."
__title__ = "Excel2ColorScheme"


import proDUCKtion  # pyright: ignore
proDUCKtion.validify()

from pyrevit import forms  # pyright: ignore

from EnneadTab import ERROR_HANDLE, LOG, NOTIFICATION, EXCEL, COLOR
from EnneadTab.REVIT import REVIT_APPLICATION, REVIT_COLOR_SCHEME, REVIT_SELECTION, REVIT_FORMS

from Autodesk.Revit import DB  # pyright: ignore


DOC = REVIT_APPLICATION.get_doc()


def _detect_header_row(raw_data, max_search_rows):
    """Detect the header row by looking for Entry/Color headers.

    Supports both older exported format ('Parameter Value' / 'Color')
    and the simple template format ('EntryName' / 'Color(No RGB)').
    """
    for header_row in range(1, max_search_rows + 1):
        header_map = EXCEL.get_header_map(raw_data, header_row)
        if not header_map:
            continue
        headers = [str(x) for x in header_map.values()]
        has_param = ("Parameter Value" in headers) or ("EntryName" in headers) or ("Entry Name" in headers)
        has_color = (
            ("COLOR" in headers)
            or ("Color" in headers)
            or ("Color(No RGB)" in headers)
        )
        if has_param and has_color:
            return header_row
    # Fallback: assume first row is header
    return 1


def _build_color_dict_from_excel(filepath, worksheet):
    """Read Excel and build a mapping of entry name -> hex color."""
    raw_data = EXCEL.read_data_from_excel(filepath, worksheet=worksheet, return_dict=True)
    if not raw_data:
        NOTIFICATION.messenger("No data found in Excel file:\n{}".format(filepath))
        return {}

    # Try first few rows to locate headers
    header_row = _detect_header_row(raw_data, max_search_rows=5)
    header_map = EXCEL.get_header_map(raw_data, header_row)
    if not header_map:
        NOTIFICATION.messenger("Could not detect header row in Excel.\n"
                               "Expected headers like 'Parameter Value' and 'Color'.")
        return {}

    name_col = None
    color_col = None
    for col, header in header_map.items():
        header_text = str(header).strip()
        if name_col is None and header_text in ["Parameter Value", "EntryName", "Entry Name"]:
            name_col = col
        if color_col is None and header_text in ["COLOR", "Color", "Color(No RGB)"]:
            color_col = col

    if name_col is None or color_col is None:
        NOTIFICATION.messenger("Excel header row must contain 'Parameter Value' and 'Color' columns.")
        return {}

    # Collect row indices after the header (these are the data rows)
    row_numbers = sorted(set(row for (row, _col) in raw_data.keys() if row > header_row))  # pyright: ignore[reportAttributeAccessIssue]

    color_dict = {}
    for row in row_numbers:
        name_cell = raw_data.get((row, name_col), {})   # pyright: ignore[reportAttributeAccessIssue]
        color_cell = raw_data.get((row, color_col), {})  # pyright: ignore[reportAttributeAccessIssue]

        entry_name = name_cell.get("value")
        if not entry_name or str(entry_name).strip() in ["", "None"]:
            continue

        # First try to use the background color captured by Excel handler
        cell_color = color_cell.get("color", (None, None, None))
        hex_color = None
        if cell_color and cell_color != (None, None, None):
            r, g, b = cell_color
            if r is not None and g is not None and b is not None:
                try:
                    hex_color = "#{:02x}{:02x}{:02x}".format(int(r), int(g), int(b))
                except Exception:
                    hex_color = None

        # Fallback: if cell text already stores a hex color, use that
        if not hex_color:
            value_text = color_cell.get("value")
            # In IronPython 2.7, unicode and str both inherit from basestring.
            # For linting compatibility, also fall back to str if basestring is not defined.
            try:
                string_type = basestring  # type: ignore[name-defined]
            except NameError:
                string_type = str
            if isinstance(value_text, string_type) and value_text.startswith("#"):
                hex_color = value_text

        if not hex_color:
            # No usable color info on this row
            continue

        color_dict[str(entry_name).strip()] = hex_color

    return color_dict


def _hex_to_revit_color(hex_color):
    """Convert hex color string to Revit Color."""
    rgb = COLOR.hex_to_rgb(hex_color)
    return COLOR.tuple_to_color(rgb)


def _update_color_scheme_from_dict(doc, color_scheme_name, color_dict):
    """Update a Revit color scheme with entries from a name->hex_color dict."""
    if not color_dict:
        print("No color data provided for scheme '{}'".format(color_scheme_name))
        return False

    color_schemes = REVIT_COLOR_SCHEME.get_color_schemes_by_name(color_scheme_name, doc)
    color_schemes = list(color_schemes) if color_schemes else []

    if not color_schemes:
        msg = "Color scheme '{}' not found in document.".format(color_scheme_name)
        NOTIFICATION.messenger(msg)
        print(msg)
        return False

    print("Found {} color scheme(s) named '{}'".format(len(color_schemes), color_scheme_name))

    for idx, color_scheme in enumerate(color_schemes, 1):
        print("  Processing color scheme #{}/{}: '{}' (ID: {})".format(
            idx, len(color_schemes), color_scheme_name, color_scheme.Id
        ))

        try:
            sample_entry = list(color_scheme.GetEntries())[0]
            storage_type = sample_entry.StorageType
        except Exception:
            print("  ERROR: Color scheme '{}' ({}/{}) has no entries. "
                  "Add at least one placeholder entry before running this tool.".format(
                      color_scheme_name, idx, len(color_schemes)
                  ))
            continue

        current_entries = {x.GetStringValue(): x for x in color_scheme.GetEntries()}

        entries_added = 0
        entries_updated = 0

        for entry_name, hex_color in color_dict.items():
            if not entry_name or not str(entry_name).strip() or entry_name == "None":
                print("    Skipping invalid entry name: '{}'".format(entry_name))
                continue

            if str(entry_name).strip().startswith('#'):
                print("    Skipping comment/header entry: '{}'".format(entry_name))
                continue

            if not hex_color or not str(hex_color).startswith('#'):
                print("    Skipping entry '{}' with invalid color: '{}'".format(entry_name, hex_color))
                continue

            original_name = str(entry_name)
            sanitized_name = original_name

            forbidden_chars = {
                '\\': '-',
                ':': '-',
                '{': '-',
                '}': '-',
                '[': '-',
                ']': '-',
                '|': '-',
                ';': '-',
                '<': '',
                '>': '',
                '?': '',
                '`': '',
                '~': ''
            }

            for forbidden, replacement in forbidden_chars.items():
                sanitized_name = sanitized_name.replace(forbidden, replacement)

            while '--' in sanitized_name:
                sanitized_name = sanitized_name.replace('--', '-')
            while '  ' in sanitized_name:
                sanitized_name = sanitized_name.replace('  ', ' ')

            sanitized_name = sanitized_name.strip(' -')

            if sanitized_name != original_name:
                print("    Sanitized name: '{}' -> '{}'".format(original_name, sanitized_name))

            entry_name = sanitized_name
            revit_color = _hex_to_revit_color(hex_color)

            if entry_name in current_entries:
                existing_entry = current_entries[entry_name]
                old_color = existing_entry.Color
                if not COLOR.is_same_color(old_color, revit_color):
                    existing_entry.Color = revit_color
                    color_scheme.UpdateEntry(existing_entry)
                    entries_updated += 1
                    print("    Updated '{}': {} -> {}".format(
                        entry_name,
                        COLOR.rgb_to_hex((old_color.Red, old_color.Green, old_color.Blue)),
                        hex_color
                    ))
            else:
                try:
                    entry = DB.ColorFillSchemeEntry(storage_type)
                    entry.Color = revit_color
                    entry.SetStringValue(entry_name)
                    entry.FillPatternId = REVIT_SELECTION.get_solid_fill_pattern_id(doc)
                    color_scheme.AddEntry(entry)
                    entries_added += 1
                    print("    Added '{}': {}".format(entry_name, hex_color))
                except Exception as e:
                    print("    ERROR adding entry '{}': {}".format(entry_name, str(e)))

        print("  Completed scheme #{}/{} '{}': {} added, {} updated".format(
            idx, len(color_schemes), color_scheme_name, entries_added, entries_updated
        ))

    print("Finished updating color scheme '{}' from Excel.".format(color_scheme_name))
    return True


def _prompt_for_excel_path():
    """Ask user to pick the Excel file that drives the color scheme."""
    excel_path = forms.pick_file(
        title="Select Excel file that defines the color scheme",
        files_filter="Excel Workbook (*.xlsx)|*.xlsx|Excel 97-2003 Workbook (*.xls)|*.xls"
    )
    if not excel_path:
        return None
    return excel_path


def _prompt_for_worksheet(excel_path):
    """Ask user which worksheet contains the color data."""
    try:
        worksheet_names = EXCEL.get_all_worksheets(excel_path)
    except Exception as e:
        NOTIFICATION.messenger("Cannot read worksheets from Excel file:\n{}\n\n{}".format(
            excel_path, str(e)
        ))
        return None

    if not worksheet_names:
        NOTIFICATION.messenger("No worksheets found in Excel file:\n{}".format(excel_path))
        return None

    worksheet_name = forms.SelectFromList.show(
        worksheet_names,
        multiselect=False,
        title="Which worksheet contains the color scheme data?"
    )
    if not worksheet_name:
        return None
    return worksheet_name

def _prompt_for_scheme_and_confirm(doc):
    """Ask user for target color scheme and confirm preconditions."""
    # Ask user to pick target color scheme in the current document
    scheme_name = REVIT_COLOR_SCHEME.pick_color_scheme(
        doc,
        title="Select target color scheme to update",
        button_name="Use this color scheme",
        multiselect=False
    )
    if not scheme_name:
        return None

    # Confirm with user before proceeding and make sure there is at least one entry
    color_schemes = REVIT_COLOR_SCHEME.get_color_schemes_by_name(scheme_name, doc)
    color_schemes = list(color_schemes) if color_schemes else []

    has_entries = False
    for cs in color_schemes:
        try:
            if list(cs.GetEntries()):
                has_entries = True
                break
        except Exception:
            continue

    sub_lines = []
    sub_lines.append("This will update Revit color scheme '{}' from Excel.".format(scheme_name))
    sub_lines.append("")
    sub_lines.append("Make sure the target color scheme already has at least one entry")
    sub_lines.append("(a placeholder is fine) so Revit knows the correct storage type.")
    if not has_entries:
        sub_lines.append("")
        sub_lines.append("WARNING: The selected color scheme currently appears to have NO entries.")
    sub_text = "\n".join(sub_lines)

    res = REVIT_FORMS.dialogue(
        title=__title__,
        main_text="Proceed with updating '{}' from Excel?".format(scheme_name),
        sub_text=sub_text,
        options=["Yes, continue", "No, cancel"],
        icon="warning"
    )
    if res != "Yes, continue":
        return None

    return scheme_name


def _run_update_transaction(doc, scheme_name, color_dict):
    """Run the Revit transaction to apply color updates to the scheme."""
    t = DB.Transaction(doc, __title__)
    t.Start()
    try:
        success = _update_color_scheme_from_dict(doc, scheme_name, color_dict)
        if success:
            t.Commit()
            NOTIFICATION.messenger(
                "Color scheme '{}' updated from Excel.\nEntries processed: {}".format(
                    scheme_name, len(color_dict)
                )
            )
            return
        t.RollBack()
    except Exception as e:
        t.RollBack()
        NOTIFICATION.messenger(
            "Failed to update color scheme from Excel.\n\n{}".format(str(e))
        )


@LOG.log(__file__, __title__)
@ERROR_HANDLE.try_catch_error()
def excel2_color_scheme(doc):
    """Main entry point for Excel2ColorScheme tool."""
    excel_path = _prompt_for_excel_path()
    if not excel_path:
        return

    worksheet_name = _prompt_for_worksheet(excel_path)
    if not worksheet_name:
        return

    scheme_name = _prompt_for_scheme_and_confirm(doc)
    if not scheme_name:
        return

    color_dict = _build_color_dict_from_excel(excel_path, worksheet_name)
    if not color_dict:
        NOTIFICATION.messenger(
            "No valid color entries were found in the Excel file.\n"
            "Make sure it has 'Parameter Value' and 'Color' columns with colored cells."
        )
        return

    _run_update_transaction(doc, scheme_name, color_dict)


################## main code below #####################
if __name__ == "__main__":
    excel2_color_scheme(DOC)


