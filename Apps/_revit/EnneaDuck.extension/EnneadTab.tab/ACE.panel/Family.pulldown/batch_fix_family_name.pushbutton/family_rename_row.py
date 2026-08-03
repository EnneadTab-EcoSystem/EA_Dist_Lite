#!/usr/bin/python
# -*- coding: utf-8 -*-
"""Pure logic + row model for the Batch Format Family Name grid.

Kept free of Revit imports so the compose/parse/validate helpers run and
test under plain CPython. Revit family objects are passed in from the
caller; this module never imports Autodesk.* .
"""

import re

# Same pattern as the legacy tool. Keep verbatim.
FAMILY_NAME_PATTERN = re.compile(
    r"^"
    r"([A-Z]{2,6})"          # Category
    r"_"
    r"([A-Z][a-zA-Z0-9]+)"   # MainDescription (CamelCase)
    r"_"
    r"([A-Z]+)"              # FIRM
    r"(?:_([^_]+))?"         # optional AdditionalInfo
    r"(?:_([A-Z]{2}))?"      # optional HOSTING (2 uppercase)
    r"$"
)

FIRM_OPTIONS = ["EA", "EC"]
HOSTING_OPTIONS = ["", "WH", "CH", "FH", "FC"]
DEFAULT_FIRM = "EA"


def compose_family_name(category, description, firm, additional, hosting):
    """Build CATEGORY_Description_FIRM[_Additional][_HOSTING]."""
    category = (category or "").strip()
    description = (description or "").strip()
    firm = (firm or "").strip()
    additional = (additional or "").strip()
    hosting = (hosting or "").strip()

    name = "{}_{}_{}".format(category, description, firm)
    if additional:
        name = "{}_{}".format(name, additional)
    if hosting:
        name = "{}_{}".format(name, hosting)
    return name


def parse_family_name(name):
    """Return a dict of parsed components; blank strings if no match."""
    result = {
        "category": "",
        "description": "",
        "firm": "",
        "additional": "",
        "hosting": "",
    }
    if not name:
        return result
    match = FAMILY_NAME_PATTERN.match(name)
    if not match:
        return result
    groups = match.groups()
    result["category"] = groups[0] or ""
    result["description"] = groups[1] or ""
    result["firm"] = groups[2] or ""
    result["additional"] = groups[3] or ""
    result["hosting"] = groups[4] or ""

    # Post-process: if optional group matched a hosting-only code (not additional),
    # move it from additional to hosting. The regex `(?:_([^_]+))?` matches any
    # non-underscore suffix, so "CH" in "LITE_PendantLamp_EA_CH" greedily fills
    # the additional slot, leaving hosting empty. Detect and fix this case.
    hosting_codes = [code for code in HOSTING_OPTIONS if code]
    if result["additional"] and not result["hosting"] and result["additional"] in hosting_codes:
        result["hosting"] = result["additional"]
        result["additional"] = ""

    return result


def is_valid_family_name(name):
    """True if name matches the standard format."""
    return bool(FAMILY_NAME_PATTERN.match(name or ""))


def derive_description(current_name, category_abbr):
    """Derive a CamelCase description from a non-conforming current name.

    When parse_family_name yields no description (the name is free text with
    spaces/dashes, e.g. "BLST_Baluster - Square"), this preserves the real
    descriptive info instead of collapsing every family to "CAT__FIRM":
    strip a leading category prefix, drop a trailing firm marker, then join
    the remaining alphanumeric words in CamelCase.
    Example: "BLST_Baluster - Square" -> "BalusterSquare".
    """
    text = current_name or ""
    if category_abbr and text.startswith(category_abbr + "_"):
        text = text[len(category_abbr) + 1:]
    else:
        text = re.sub(r"^[A-Z]{2,6}_", "", text)
    tokens = [token for token in re.split(r"[^A-Za-z0-9]+", text) if token]
    while tokens and tokens[-1] in FIRM_OPTIONS:
        tokens.pop()
    if not tokens:
        return ""
    parts = []
    for token in tokens:
        parts.append(token[0].upper() + token[1:])
    return "".join(parts)


class FamilyRenameRow(object):
    """One editable grid row wrapping a Revit family.

    category_abbr is derived by the caller from the family's real Revit
    category (read-only). actual_hosting_abbr is the family's real hosting
    behavior abbreviation (or None). Editable fields are pre-filled by
    parsing the current name (moderate pre-parse); when the name does not
    conform, description/additional stay blank, firm defaults to EA, and
    hosting falls back to the family's actual hosting.
    """

    def __init__(self, family, category_abbr, actual_hosting_abbr):
        # Store the element's integer id, NOT the live Revit element. This row
        # object is the item a modeless WPF DataGrid selects, and on selection
        # WPF calls GetHashCode/ToString/property-enumeration on it outside
        # Revit's API context. A held DB.Family element throws there, inside
        # WPF's selection machinery, as an uncatchable CLR fatal error
        # (0xe0434352). Re-fetch the element by id at apply time instead.
        try:
            self.family_id = family.Id.Value          # Revit 2026+
        except AttributeError:
            self.family_id = family.Id.IntegerValue    # Revit <= 2025
        self.current_name = family.Name
        self.category = category_abbr or ""

        parsed = parse_family_name(self.current_name)
        self.description = parsed["description"] or derive_description(
            self.current_name, self.category)
        self.firm = parsed["firm"] or DEFAULT_FIRM
        self.additional = parsed["additional"]
        self.hosting = actual_hosting_abbr or parsed["hosting"] or ""

        self.is_checked = True
        self.new_name = ""
        self.valid = ""
        self.recompute()

    def __repr__(self):
        # Plain-string repr only (no Revit element) so WPF's ToString on the
        # selected item can never touch the API.
        return "FamilyRenameRow({})".format(self.current_name)

    def recompute(self):
        """Recompute new_name + valid from the current editable fields."""
        self.new_name = compose_family_name(
            self.category, self.description, self.firm,
            self.additional, self.hosting)
        self.valid = "OK" if is_valid_family_name(self.new_name) else "X"


if __name__ == "__main__":
    pass
