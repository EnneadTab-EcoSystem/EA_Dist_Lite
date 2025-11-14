#!/usr/bin/python
# -*- coding: utf-8 -*-

__doc__ = "PlaceHolder Documentation, To Be Updated."
__title__ = "Transfer Color Scheme"

import proDUCKtion # pyright: ignore 
proDUCKtion.validify()

from EnneadTab import ERROR_HANDLE, LOG
from EnneadTab.REVIT import REVIT_APPLICATION, REVIT_COLOR_SCHEME, REVIT_FORMS
from Autodesk.Revit import DB # pyright: ignore 
try:
    from pyrevit import script # pyright: ignore
    LOGGER = script.get_logger()
except: # pylint: disable=bare-except
    class _LoggerFallback(object):
        def info(self, message):
            ERROR_HANDLE.print_note(message)

    LOGGER = _LoggerFallback()

UIDOC = REVIT_APPLICATION.get_uidoc()
DOC = REVIT_APPLICATION.get_doc()


@LOG.log(__file__, __title__)
@ERROR_HANDLE.try_catch_error()
def transfer_color_scheme(doc):
    source_name, destination_name = _pick_color_schemes(doc)
    if not source_name or not destination_name:
        return

    source_scheme = REVIT_COLOR_SCHEME.get_color_scheme_by_name(source_name, doc)
    destination_scheme = REVIT_COLOR_SCHEME.get_color_scheme_by_name(destination_name, doc)
    if not source_scheme or not destination_scheme:
        return

    if not _is_same_category(source_scheme, destination_scheme):
        _notify("Selected color schemes belong to different categories.\nPlease pick schemes that target the same category.")
        return

    source_entries = list(source_scheme.GetEntries())
    destination_entries = list(destination_scheme.GetEntries())
    if not source_entries:
        _notify("Source color scheme has no entries to transfer.")
        return

    conflict_keys = _find_conflicts(source_entries, destination_entries)
    override_matches = True
    if conflict_keys:
        override_matches = _ask_conflict_strategy(conflict_keys)
        if override_matches is None:
            return

    t = DB.Transaction(doc, __title__)
    t.Start()
    stats = _copy_entries(source_scheme, destination_scheme, source_entries, destination_entries, override_matches)
    t.Commit()

    LOGGER.info("Transferred color scheme entries: added {}, updated {}.".format(stats["added"], stats["updated"]))



def _pick_color_schemes(doc):
    source_name = REVIT_COLOR_SCHEME.pick_color_scheme(doc,
                                                       title="Select source color scheme",
                                                       button_name="Use as source",
                                                       multiselect=False)
    if not source_name:
        return None, None

    destination_name = REVIT_COLOR_SCHEME.pick_color_scheme(doc,
                                                            title="Select destination color scheme",
                                                            button_name="Use as destination",
                                                            multiselect=False)
    if not destination_name:
        return None, None

    if source_name == destination_name:
        _notify("Source and destination color schemes cannot be the same.")
        return None, None
    return source_name, destination_name


def _is_same_category(source_scheme, destination_scheme):
    if not source_scheme or not destination_scheme:
        return False
    return source_scheme.CategoryId.IntegerValue == destination_scheme.CategoryId.IntegerValue


def _find_conflicts(source_entries, destination_entries):
    source_keys = set([_entry_key(x) for x in source_entries])
    destination_keys = set([_entry_key(x) for x in destination_entries])
    conflicts = source_keys.intersection(destination_keys)
    sorted_conflicts = sorted([_entry_label_from_key(x) for x in conflicts])
    return sorted_conflicts


def _entry_key(entry):
    storage_type = entry.StorageType
    if storage_type == DB.StorageType.String:
        getter = getattr(entry, "GetStringValue", None)
        if getter:
            return ("STRING", getter())
    if storage_type == DB.StorageType.Double:
        getter = getattr(entry, "GetDoubleValue", None)
        if getter:
            return ("DOUBLE", getter())
    if storage_type == DB.StorageType.Integer:
        getter = getattr(entry, "GetIntegerValue", None)
        if getter:
            return ("INTEGER", getter())
    if storage_type == DB.StorageType.ElementId:
        getter = getattr(entry, "GetElementValueId", None)
        if getter:
            element_id = getter()
            if element_id:
                return ("ELEMENTID", element_id.IntegerValue)
        return ("ELEMENTID", None)
    return ("UNKNOWN", None)


def _entry_label_from_key(key):
    if not key:
        return "Unknown"
    storage_type, value = key
    if storage_type == "STRING":
        return value or "Blank"
    if storage_type == "DOUBLE":
        return "Value {}".format(value)
    if storage_type == "INTEGER":
        return "Value {}".format(value)
    if storage_type == "ELEMENTID":
        return "ElementId {}".format(value)
    return "Unknown"


def _ask_conflict_strategy(conflict_keys):
    preview = conflict_keys[:10]
    sub_text = "Found {} matching entries:\n{}".format(len(conflict_keys), "\n".join(preview))
    res = REVIT_FORMS.dialogue(title=__title__,
                               main_text="How should matching entries be handled?",
                               sub_text=sub_text,
                               options=["Override Matches", "Add New Only"],
                               icon="warning")
    if not res or res in ["Cancel", "Close"]:
        return None
    return res == "Override Matches"


def _copy_entries(source_scheme, destination_scheme, source_entries, destination_entries, override_matches):
    stats = {"added": 0, "updated": 0}
    destination_map = {}
    for entry in destination_entries:
        destination_map[_entry_key(entry)] = entry

    storage_type = _resolve_storage_type(destination_entries, source_entries)
    if storage_type is None:
        _notify("Unable to determine entry storage type for destination scheme.")
        return stats

    for source_entry in source_entries:
        key = _entry_key(source_entry)
        existing_entry = destination_map.get(key)
        if existing_entry:
            if override_matches:
                _apply_entry_data(existing_entry, source_entry)
                destination_scheme.UpdateEntry(existing_entry)
                destination_map[key] = existing_entry
                stats["updated"] += 1
            continue
        new_entry = DB.ColorFillSchemeEntry(storage_type)
        _apply_entry_data(new_entry, source_entry)
        destination_scheme.AddEntry(new_entry)
        destination_map[key] = new_entry
        stats["added"] += 1
    return stats


def _resolve_storage_type(destination_entries, source_entries):
    if destination_entries:
        return destination_entries[0].StorageType
    if source_entries:
        return source_entries[0].StorageType
    return None


def _apply_entry_data(target_entry, source_entry):
    _apply_value(target_entry, source_entry)
    target_entry.Color = source_entry.Color
    target_entry.FillPatternId = source_entry.FillPatternId


def _apply_value(target_entry, source_entry):
    storage_type = source_entry.StorageType
    if storage_type == DB.StorageType.String:
        getter = getattr(source_entry, "GetStringValue", None)
        setter = getattr(target_entry, "SetStringValue", None)
        if getter and setter:
            setter(getter())
        return
    if storage_type == DB.StorageType.Double:
        getter = getattr(source_entry, "GetDoubleValue", None)
        setter = getattr(target_entry, "SetDoubleValue", None)
        if getter and setter:
            setter(getter())
        return
    if storage_type == DB.StorageType.Integer:
        getter = getattr(source_entry, "GetIntegerValue", None)
        setter = getattr(target_entry, "SetIntegerValue", None)
        if getter and setter:
            setter(getter())
        return
    if storage_type == DB.StorageType.ElementId:
        getter = getattr(source_entry, "GetElementValueId", None)
        setter = getattr(target_entry, "SetElementValueId", None)
        if getter and setter:
            element_id = getter()
            setter(element_id)
        return


def _notify(message):
    REVIT_FORMS.dialogue(title=__title__,
                         main_text=message,
                         options=["OK"],
                         icon="warning")


################## main code below #####################
if __name__ == "__main__":
    transfer_color_scheme(DOC)






