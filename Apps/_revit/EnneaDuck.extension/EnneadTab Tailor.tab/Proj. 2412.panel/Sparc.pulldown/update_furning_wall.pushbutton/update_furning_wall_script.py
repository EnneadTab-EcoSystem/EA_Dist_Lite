#!/usr/bin/python
# -*- coding: utf-8 -*-

__doc__ = "PlaceHolder Documentation, To Be Updated."
__title__ = "Update Furning Wall"

import proDUCKtion  # pyright: ignore
proDUCKtion.validify()

from pyrevit import forms

from EnneadTab import ERROR_HANDLE, LOG, NOTIFICATION
from EnneadTab.REVIT import REVIT_APPLICATION, REVIT_SELECTION
from Autodesk.Revit import DB  # pyright: ignore

from furring_constants import (
    FURRING_WALL_TYPE_NAME,
    TARGET_LINK_TITLE,
    TARGET_PANEL_FAMILIES,
)
from furring_panel_data import (
    collect_levels_with_z,
    collect_panels_from_doc,
    print_panel_logs,
)
from furring_element_ops import (
    build_panel_selection_filter_name,
    create_furring_walls,
    create_room_separation_lines,
    delete_elements_in_selection_filter,
    get_wall_type_by_name,
    map_levels_by_name,
    update_panel_selection_filter,
)

UIDOC = REVIT_APPLICATION.get_uidoc()
DOC = REVIT_APPLICATION.get_doc()


def _format_panel_family_label(family_name, type_name):
    if type_name:
        return "{0} ({1})".format(family_name, type_name)
    return "{0} (All Types)".format(family_name)


def _select_target_panel_families():
    label_map = {}
    option_labels = []
    for family_name, type_name in TARGET_PANEL_FAMILIES:
        label = _format_panel_family_label(family_name, type_name)
        if label not in label_map:
            label_map[label] = []
            option_labels.append(label)
        label_map[label].append((family_name, type_name))
    selected_labels = forms.SelectFromList.show(
        option_labels,
        multiselect=True,
        title="Select Curtain Panel Families and types to process. Unpicked item will not be updated.",
        button_name="Run",
    )
    if not selected_labels:
        return []
    selected_pairs = []
    for label in selected_labels:
        pairs = label_map.get(label) or []
        for pair in pairs:
            if pair not in selected_pairs:
                selected_pairs.append(pair)
    return selected_pairs


def _coerce_element_id_sequence(value):
    if value is None:
        return []
    if isinstance(value, DB.ElementId):
        return [value]
    if isinstance(value, (list, tuple)):
        return [item for item in value if item is not None]
    try:
        return [item for item in value if item is not None]
    except TypeError:
        return []


@LOG.log(__file__, __title__)
@ERROR_HANDLE.try_catch_error()
def update_furning_wall(doc):
    printed_ids = set()

    selected_panel_families = _select_target_panel_families()
    if not selected_panel_families:
        NOTIFICATION.messenger("Update cancelled. No panel families selected.")
        return

    link_doc = REVIT_SELECTION.get_revit_link_doc_by_name(TARGET_LINK_TITLE, doc=doc)
    if link_doc is None:
        raise ValueError("Could not locate link document \"{0}\".".format(TARGET_LINK_TITLE))

    link_instance = REVIT_SELECTION.get_revit_link_instance_by_name(TARGET_LINK_TITLE, doc=doc)
    if link_instance is None:
        raise ValueError("Could not locate link instance \"{0}\".".format(TARGET_LINK_TITLE))

    levels = collect_levels_with_z(link_doc)
    if not levels:
        raise ValueError("Unable to collect level data from link \"{0}\".".format(link_doc.Title))

    if hasattr(link_instance, "GetTransform"):
        transform = link_instance.GetTransform()
    else:
        transform = link_instance.GetTotalTransform()

    link_source_name = "{0} (link)".format(link_doc.Title)
    panel_records, panel_logs = collect_panels_from_doc(
        link_doc,
        link_source_name,
        printed_ids,
        levels,
        transform,
        target_panel_families=selected_panel_families,
    )

    if not panel_records:
        family_labels = [_format_panel_family_label(name, type_name) for (name, type_name) in selected_panel_families]
        print("No curtain panels matching {0} were found in link \"{1}\".".format(", ".join(family_labels), TARGET_LINK_TITLE))
        return

    print_panel_logs(panel_logs)

    wall_type = get_wall_type_by_name(doc, FURRING_WALL_TYPE_NAME)
    if wall_type is None:
        raise ValueError("Wall type \"{0}\" was not found in the host document.".format(FURRING_WALL_TYPE_NAME))

    host_level_map = map_levels_by_name(doc)

    transaction = DB.Transaction(doc, __title__)
    transaction.Start()
    total_deleted_elements = 0
    total_deleted_walls = 0
    total_deleted_room_lines = 0
    total_created_walls = 0
    total_created_room_lines = 0
    selection_set_examples = []
    transaction_state = "unknown"
    try:
        panel_groups = {}
        for record in panel_records:
            family_name = record.get("family_name")
            type_name = record.get("type_name")
            key = (family_name, type_name)
            if key not in panel_groups:
                panel_groups[key] = []
            panel_groups[key].append(record)
        total_panel_records = sum(len(panel_groups[key]) for key in panel_groups)
        ordered_keys = []
        missing_labels = []
        processed_keys = set()
        for family_name, type_name in selected_panel_families:
            if type_name is None:
                found_any = False
                for key in panel_groups:
                    if key[0] == family_name and key not in processed_keys:
                        ordered_keys.append(key)
                        processed_keys.add(key)
                        found_any = True
                if not found_any:
                    missing_labels.append(_format_panel_family_label(family_name, type_name))
            else:
                key = (family_name, type_name)
                if key in panel_groups and key not in processed_keys:
                    ordered_keys.append(key)
                    processed_keys.add(key)
                else:
                    missing_labels.append(_format_panel_family_label(family_name, type_name))
        total_selection_sets = len(ordered_keys)
        if total_selection_sets:
            NOTIFICATION.messenger(
                "Updating {0} selection set(s) covering {1} panel record(s).".format(
                    total_selection_sets,
                    total_panel_records,
                )
            )
        processed_sets = 0
        processed_panels = 0
        for key in ordered_keys:
            family_name, type_name = key
            records = panel_groups.get(key) or []
            if not records:
                continue
            processed_sets += 1
            filter_name = build_panel_selection_filter_name(family_name, type_name)
            selection_set_examples.append((filter_name, family_name, type_name))
            label = _format_panel_family_label(family_name, type_name)
            print("Processing panel selection set: {0} ({1} panel record(s)).".format(label, len(records)))
            print("    Selection set name: {0}".format(filter_name))
            NOTIFICATION.messenger(
                "Processing {0}/{1}: {2} ({3} panel record(s))".format(
                    processed_sets,
                    total_selection_sets,
                    label,
                    len(records),
                )
            )
            deleted_total, deleted_walls, deleted_room_lines = delete_elements_in_selection_filter(doc, filter_name)
            if deleted_total:
                print("    Removed {0} existing element(s) from selection set (walls: {1}, room lines: {2}).".format(
                    deleted_total,
                    deleted_walls,
                    deleted_room_lines,
                ))
            walls_created_count, wall_ids = create_furring_walls(doc, records, wall_type, host_level_map)
            room_created_count, room_line_ids = create_room_separation_lines(doc, records, host_level_map)
            total_created_walls += walls_created_count
            total_created_room_lines += room_created_count
            total_deleted_elements += deleted_total
            total_deleted_walls += deleted_walls
            total_deleted_room_lines += deleted_room_lines
            processed_panels += len(records)
            wall_ids = _coerce_element_id_sequence(wall_ids)
            room_line_ids = _coerce_element_id_sequence(room_line_ids)
            combined_ids = list(wall_ids)
            combined_ids.extend(room_line_ids)
            saved_count = update_panel_selection_filter(doc, filter_name, combined_ids)
            print("    Recorded {0} element(s) in selection set.".format(saved_count))
            NOTIFICATION.messenger(
                "Completed {0}/{1}: {2}. Processed {3}/{4} panel record(s) overall.".format(
                    processed_sets,
                    total_selection_sets,
                    label,
                    processed_panels,
                    total_panel_records,
                )
            )
        if not ordered_keys:
            print("No panel records matched the selected panel families inside the link.")
        elif missing_labels:
            print("No panel records matched the following selections: {0}".format(", ".join(missing_labels)))
    except Exception:
        transaction.RollBack()
        transaction_state = "rolled back"
        NOTIFICATION.messenger("Update furring wall transaction rolled back due to an error.")
        raise
    else:
        transaction.Commit()
        transaction_state = "committed"
        NOTIFICATION.messenger(
            "Furring walls created: {0}; Room separation lines created: {1}; Removed prior elements: {2}".format(
                total_created_walls,
                total_created_room_lines,
                total_deleted_elements,
            )
        )
        if selection_set_examples:
            example_name, example_family, example_type = selection_set_examples[0]
            example_label = _format_panel_family_label(example_family, example_type)
            print("Example selection set for {0}: {1}".format(example_label, example_name))
    finally:
        if transaction_state != "unknown":
            print("Update furring wall transaction {0}.".format(transaction_state))
        else:
            print("Update furring wall transaction status unknown.")


################## main code below #####################
if __name__ == "__main__":
    update_furning_wall(DOC)







