#!/usr/bin/python
# -*- coding: utf-8 -*-

__doc__ = "PlaceHolder Documentation, To Be Updated."
__title__ = "Update Furning Wall"

import proDUCKtion  # pyright: ignore
proDUCKtion.validify()

from pyrevit import forms

from EnneadTab import ERROR_HANDLE, LOG, NOTIFICATION
from EnneadTab.REVIT import REVIT_APPLICATION, REVIT_FILTER, REVIT_SELECTION
from Autodesk.Revit import DB  # pyright: ignore

from furring_constants import (
    FURRING_WALL_TYPE_NAME,
    ROOM_SEPARATOR_SELECTION_NAME,
    TARGET_LINK_TITLE,
    TARGET_PANEL_FAMILIES,
)
from furring_panel_data import (
    collect_levels_with_z,
    collect_panels_from_doc,
    print_panel_logs,
)
from furring_element_ops import (
    create_furring_walls,
    create_room_separation_lines,
    delete_existing_furring_walls,
    delete_room_separation_lines,
    get_wall_type_by_name,
    map_levels_by_name,
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
        title="Select Curtain Panel Families",
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
    deleted_walls = 0
    created_walls = 0
    deleted_room_lines = 0
    created_room_lines = 0
    try:
        deleted_walls = delete_existing_furring_walls(doc, wall_type)
        deleted_room_lines = delete_room_separation_lines(doc)
        created_walls = create_furring_walls(doc, panel_records, wall_type, host_level_map)
        created_room_lines, room_line_ids = create_room_separation_lines(doc, panel_records, host_level_map)
        room_line_elements = []
        for element_id in room_line_ids:
            element = doc.GetElement(element_id)
            if element is not None and element.IsValidObject:
                room_line_elements.append(element)
        selection_filter_exists = REVIT_FILTER.get_selection_filter_by_name(doc, ROOM_SEPARATOR_SELECTION_NAME) is not None
        if room_line_elements or selection_filter_exists:
            REVIT_FILTER.update_selection_filter(doc, ROOM_SEPARATOR_SELECTION_NAME, room_line_elements)
    except Exception:
        transaction.RollBack()
        raise
    else:
        transaction.Commit()
        NOTIFICATION.messenger(
            "Furring walls created/updated: {0} (removed: {1}); Room separation lines created: {2} (removed: {3})".format(
                created_walls,
                deleted_walls,
                created_room_lines,
                deleted_room_lines,
            )
        )


################## main code below #####################
if __name__ == "__main__":
    update_furning_wall(DOC)







