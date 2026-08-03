#!/usr/bin/python
# -*- coding: utf-8 -*-

__doc__ = """Copy every entry, color, and fill pattern from one color scheme onto another.

Saves rebuilding a scheme by hand when a second one needs to look the same. Entries
missing from the destination are added; where an entry already exists you are asked
before its color is overwritten.

Features:
- The two schemes must cover the same category, and you are told if they do not
- A summary lists what was added and what was overwritten
- The transfer is one undo step

Usage:
1. Run the button and pick the scheme to copy from, then the one to copy onto"""
__title__ = "Transfer\nColor Scheme"

import proDUCKtion # pyright: ignore 
proDUCKtion.validify()

from EnneadTab import ERROR_HANDLE, LOG, NOTIFICATION
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


def _element_id_value(element_id):
    """Return integer value for ElementId across Revit versions. Uses shared REVIT_APPLICATION helper."""
    if not element_id:
        return None
    return REVIT_APPLICATION.get_element_id_value(element_id)


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

    message = "Transferred color scheme entries: added {}, updated {}.".format(stats["added"], stats["updated"])
    LOGGER.info(message)
    NOTIFICATION.messenger(main_text=message)



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
    return _element_id_value(source_scheme.CategoryId) == _element_id_value(destination_scheme.CategoryId)


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
                return ("ELEMENTID", _element_id_value(element_id))
        return ("ELEMENTID", None)
    return ("UNKNOWN", None)


def _storage_type_to_key(storage_type):
    if storage_type == DB.StorageType.String:
        return "STRING"
    if storage_type == DB.StorageType.Double:
        return "DOUBLE"
    if storage_type == DB.StorageType.Integer:
        return "INTEGER"
    if storage_type == DB.StorageType.ElementId:
        return "ELEMENTID"
    return "UNKNOWN"


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

    storage_type = _resolve_storage_type(destination_scheme, destination_entries)
    if storage_type is None:
        if not destination_entries:
            # The destination scheme is empty AND this Revit version did not give us a
            # usable ColorFillScheme.StorageType, so nothing here can tell us what value
            # type it expects. Rather than guess (guessing from the source is the bug
            # this whole change fixes), hand the user the one action that resolves it.
            _notify("{} has no entries yet, so Revit cannot tell what kind of value it expects.\n\n"
                    "Please add one entry to it in Revit first -- any value is fine -- then run this "
                    "tool again. The rest of the entries will come across automatically.".format(
                        _scheme_subject(destination_scheme)))
        else:
            _notify("Unable to determine entry storage type for destination scheme.")
        return stats

    mismatch_reported = False
    for source_entry in source_entries:
        key = _entry_key(source_entry)
        if key and key[0] != _storage_type_to_key(storage_type):
            if not mismatch_reported:
                _notify("Source entry storage type does not match destination scheme.\nPlease ensure both schemes use the same parameter type.")
                mismatch_reported = True
            continue
        existing_entry = destination_map.get(key)
        if existing_entry:
            if override_matches:
                _apply_entry_data(existing_entry, source_entry)
                if not _commit_entry(destination_scheme, existing_entry, update=True):
                    continue
                destination_map[key] = existing_entry
                stats["updated"] += 1
            continue
        new_entry = DB.ColorFillSchemeEntry(storage_type)
        _apply_entry_data(new_entry, source_entry)
        if not _commit_entry(destination_scheme, new_entry, update=False):
            continue
        destination_map[key] = new_entry
        stats["added"] += 1
    return stats


def _resolve_storage_type(destination_scheme, destination_entries):
    """Storage type the DESTINATION scheme requires for its entries.

    2026-07-30: this used to read destination_entries[0] and, when the destination
    scheme had NO entries, fall back to source_entries[0]. That made the caller's
    "does the source match the destination?" guard compare the source against
    ITSELF, so it could never fire, and AddEntry then threw
    "The scheme and the entry have different parameter storage type."
    (senzhang-todo #3260). The scheme is the authority, never the source.

    ColorFillScheme.StorageType exists in Revit 2022+ and is valid even when the
    scheme has no entries yet; the entries[0] read is kept only as a fallback for
    older API surfaces. There is deliberately NO source-based fallback -- if the
    destination's type cannot be determined we return None and the caller aborts,
    rather than guessing a value that defeats the guard.
    """
    # StorageType.None cannot be written literally -- "None" is a Python keyword --
    # so it is fetched by name; the 3-arg getattr keeps this total if the member
    # is ever absent, in which case any non-null StorageType is accepted.
    storage_type_none = getattr(DB.StorageType, "None", None)
    scheme_storage_type = getattr(destination_scheme, "StorageType", None)
    if scheme_storage_type is not None and scheme_storage_type != storage_type_none:
        return scheme_storage_type
    if destination_entries:
        return destination_entries[0].StorageType
    return None


def _scheme_subject(scheme):
    """Sentence subject for a color scheme, quoted when we have a real name."""
    name = getattr(scheme, "Name", None)
    if name:
        return "\"{}\"".format(name)
    return "The destination color scheme"


def _commit_entry(destination_scheme, entry, update):
    """Add/update one entry, converting a Revit rejection into a readable message.

    Backstop for the cases the storage-type guard cannot see: AddEntry also rejects
    duplicate values, out-of-range values, and invalid fill-pattern ids. Without this
    a single bad entry aborted the whole transfer with a raw exception dialog.
    """
    if not update and hasattr(destination_scheme, "IsEntryConsistentWithScheme"):
        if not destination_scheme.IsEntryConsistentWithScheme(entry):
            _notify("An entry is not compatible with the destination scheme and was skipped.")
            return False
    try:
        if update:
            destination_scheme.UpdateEntry(entry)
        else:
            destination_scheme.AddEntry(entry)
        return True
    except Exception as e:
        ERROR_HANDLE.print_note("transfer_color_scheme: entry rejected by Revit: {}".format(e))
        _notify("Revit rejected one color scheme entry, so it was skipped:\n{}".format(e))
        return False


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






