#!/usr/bin/python
# -*- coding: utf-8 -*-

__doc__ = "PlaceHolder Documentation, To Be Updated."
__title__ = "Update Furning Wall"

import proDUCKtion # pyright: ignore 
proDUCKtion.validify()

from EnneadTab import ERROR_HANDLE, LOG
from EnneadTab.REVIT import REVIT_APPLICATION
from EnneadTab.REVIT import REVIT_SELECTION
from Autodesk.Revit import DB # pyright: ignore 

UIDOC = REVIT_APPLICATION.get_uidoc()
DOC = REVIT_APPLICATION.get_doc()

TARGET_FAMILY_NAME = "EA_CW-1 (Tower)"
TARGET_LINK_TITLE = "SPARC_A_EA_Exterior"
CHILD_FAMILY_NAME = "RefMarker"
EXPECTED_CHILD_COUNT = 4
FAMILY_INSTANCE_FILTER = DB.ElementClassFilter(DB.FamilyInstance)
MARKER_INDEX_ORDER = [
    "pier_furring_pt1",
    "pier_furring_pt2",
    "pier_furring_pt3",
    "pier_furring_pt4",
]
FURRING_WALL_TYPE_NAME = "FacadeFurringSpecial(DO_NOT_MANUAL_EDIT)"


def _get_family_name(element):
    symbol = getattr(element, "Symbol", None)

    if symbol:
        family = symbol.Family
        if family:
            return family.Name

    param = element.get_Parameter(DB.BuiltInParameter.ELEM_FAMILY_PARAM)
    if param:
        return param.AsString()
    return None


def _collect_panels_from_doc(source_doc, source_name, printed_ids, levels, panel_records, transform):
    collector = DB.FilteredElementCollector(source_doc).OfCategory(DB.BuiltInCategory.OST_CurtainWallPanels).WhereElementIsNotElementType()

    for element in collector:
        family_name = _get_family_name(element)
        if family_name == TARGET_FAMILY_NAME:
            unique_id = element.UniqueId
            if unique_id in printed_ids:
                continue
            printed_ids.add(unique_id)
            ref_markers = _get_child_family_instances(element, source_doc, CHILD_FAMILY_NAME)
            first_marker_point = None
            marker_data = {}
            for marker_key in MARKER_INDEX_ORDER:
                marker_element = ref_markers.get(marker_key)
                entry = {
                    "name": marker_key,
                    "element": marker_element,
                    "unique_id": None,
                    "point_link": None,
                    "point_host": None,
                }
                if marker_element is not None:
                    entry["unique_id"] = marker_element.UniqueId
                    location = marker_element.Location
                    point = getattr(location, "Point", None)
                    if point is not None:
                        entry["point_link"] = point
                        entry["point_host"] = transform.OfPoint(point) if transform is not None else point
                        if first_marker_point is None:
                            first_marker_point = point
                marker_data[marker_key] = entry
            if first_marker_point is not None:
                nearest_level, level_z = _find_nearest_level(first_marker_point, levels)
            else:
                nearest_level = None
                level_z = None
            height_value = _get_parameter_double(element, "CWPL_$Height")
            panel_record = {
                "source_name": source_name,
                "panel_unique_id": unique_id,
                "markers": marker_data,
                "ref_marker_count": len([entry for entry in marker_data.values() if entry["element"] is not None]),
                "nearest_level": nearest_level,
                "nearest_level_z": level_z,
                "panel_element": element,
                "panel_height": height_value,
            }
            panel_records.append(panel_record)
            _print_panel_info(panel_record)


def _print_panel_info(panel_record):
    print("\nPanel ({0}): {1}".format(panel_record["source_name"], panel_record["panel_unique_id"]))
    print("    RefMarker count: {0}".format(panel_record["ref_marker_count"]))
    for marker_key in MARKER_INDEX_ORDER:
        entry = panel_record["markers"].get(marker_key)
        if entry is None:
            print("        Missing RefMarker for index \"{0}\".".format(marker_key))
            continue
        if entry["element"] is None:
            print("        Missing RefMarker for index \"{0}\".".format(marker_key))
            continue
        point = entry["point_link"]
        if point is None:
            print("        {0}: Location not available.".format(marker_key))
        else:
            print("        {0}: {1}, {2}, {3} (UniqueId: {4})".format(
                marker_key,
                point.X,
                point.Y,
                point.Z,
                entry["unique_id"]
            ))
    if panel_record["ref_marker_count"] != EXPECTED_CHILD_COUNT:
        print("    Warning: Expected {0} RefMarker children but found {1}.".format(
            EXPECTED_CHILD_COUNT,
            panel_record["ref_marker_count"]
        ))
    nearest_level = panel_record["nearest_level"]
    level_z = panel_record["nearest_level_z"]
    first_marker_entry = panel_record["markers"].get(MARKER_INDEX_ORDER[0])
    first_point = first_marker_entry["point_link"] if first_marker_entry else None
    if nearest_level is not None and level_z is not None and first_point is not None:
        offset = abs(first_point.Z - level_z)
        print("    Closest level: {0} (Z={1}, delta={2})".format(nearest_level.Name, level_z, offset))
    else:
        print("    Closest level: Not found.")


def _get_child_family_instances(parent_element, source_doc, target_family_name):
    child_elements = {}

    child_ids = parent_element.GetDependentElements(FAMILY_INSTANCE_FILTER)

    for child_id in child_ids:
        child_element = source_doc.GetElement(child_id)
        if not child_element:
            continue
        child_family = _get_family_name(child_element)
        if child_family == target_family_name:
            index_value = _get_parameter_value(child_element, "index")
            key = index_value if index_value else "unknown"
            child_elements[key] = child_element
    return child_elements


def _get_parameter_value(element, parameter_name):
    parameter = element.LookupParameter(parameter_name)
    if parameter is None:
        return None
    value = parameter.AsString()
    if value:
        return value
    try:
        value = parameter.AsValueString()
    except Exception:
        value = None
    if value:
        return value
    if parameter.StorageType == DB.StorageType.Integer:
        return str(parameter.AsInteger())
    if parameter.StorageType == DB.StorageType.Double:
        return str(parameter.AsDouble())
    return None


def _get_parameter_double(element, parameter_name):
    parameter = element.LookupParameter(parameter_name)
    if parameter is None:
        return None
    if parameter.StorageType != DB.StorageType.Double:
        try:
            return parameter.AsDouble()
        except Exception:
            return None
    return parameter.AsDouble()


def _collect_levels_with_z(doc):
    levels = DB.FilteredElementCollector(doc).OfClass(DB.Level).WhereElementIsNotElementType()
    level_data = []
    for level in levels:
        level_z = level.ProjectElevation
        level_data.append((level, level_z))
    return level_data


def _find_nearest_level(point, level_data):
    if not level_data:
        return (None, None)
    nearest_level = None
    nearest_level_z = None
    min_distance = None
    for level, level_z in level_data:
        distance = abs(point.Z - level_z)
        if (min_distance is None) or (distance < min_distance):
            min_distance = distance
            nearest_level = level
            nearest_level_z = level_z
    return (nearest_level, nearest_level_z)


def _map_levels_by_name(doc):
    level_map = {}
    levels = DB.FilteredElementCollector(doc).OfClass(DB.Level).WhereElementIsNotElementType()
    for level in levels:
        level_map[level.Name] = level
    return level_map


def _get_wall_type_by_name(doc, type_name):
    wall_types = DB.FilteredElementCollector(doc).OfClass(DB.WallType)
    for wall_type in wall_types:
        if wall_type.Name == type_name:
            return wall_type
    return None


def _delete_existing_furring_walls(doc, wall_type):
    walls = DB.FilteredElementCollector(doc).OfClass(DB.Wall).WhereElementIsNotElementType()
    for wall in walls:
        if wall.WallType.Id == wall_type.Id:
            doc.Delete(wall.Id)


def _create_furring_walls(doc, panel_records, wall_type, host_level_map):
    base_offset = 0.0
    for record in panel_records:
        level = record["nearest_level"]
        if level is None:
            print("    Skipping panel {0} due to missing nearest level.".format(record["panel_unique_id"]))
            continue
        host_level = host_level_map.get(level.Name)
        if host_level is None:
            raise ValueError("Host document is missing level named \"{0}\" required for panel {1}.".format(level.Name, record["panel_unique_id"]))
        panel_height = record.get("panel_height")
        if panel_height is None:
            print("        Cannot determine height for panel {0}; missing parameter.".format(record["panel_unique_id"]))
            continue
        height = panel_height - 3.0
        if height <= 0:
            print("        Computed height {0} for panel {1} is not positive; skipping.".format(height, record["panel_unique_id"]))
            continue
        ordered_points = []
        for marker_key in MARKER_INDEX_ORDER:
            entry = record["markers"].get(marker_key)
            if entry is None or entry["point_host"] is None:
                print("        Cannot create walls for panel {0}; missing host point for index {1}.".format(record["panel_unique_id"], marker_key))
                ordered_points = []
                break
            ordered_points.append(entry["point_host"])
        if len(ordered_points) < 2:
            continue
        for idx in range(len(ordered_points) - 1):
            start_point = ordered_points[idx]
            end_point = ordered_points[idx + 1]
            line = DB.Line.CreateBound(start_point, end_point)
            new_wall = DB.Wall.Create(doc, line, wall_type.Id, host_level.Id, height, base_offset, False, False)
            param_height = new_wall.get_Parameter(DB.BuiltInParameter.WALL_USER_HEIGHT_PARAM)
            if param_height is not None:
                param_height.Set(height)
            param_base_offset = new_wall.get_Parameter(DB.BuiltInParameter.WALL_BASE_OFFSET)
            if param_base_offset is not None:
                param_base_offset.Set(base_offset)
            start_name = MARKER_INDEX_ORDER[idx]
            end_name = MARKER_INDEX_ORDER[idx + 1]
            print("        Created furring wall ({0}->{1}) UniqueId: {2}".format(
                start_name,
                end_name,
                new_wall.UniqueId
            ))


@LOG.log(__file__, __title__)
@ERROR_HANDLE.try_catch_error()
def update_furning_wall(doc):
    printed_ids = set()

    link_doc = REVIT_SELECTION.get_revit_link_doc_by_name(TARGET_LINK_TITLE, doc=doc)
    if link_doc is None:
        raise ValueError("Could not locate link document \"{0}\".".format(TARGET_LINK_TITLE))

    link_instance = REVIT_SELECTION.get_revit_link_instance_by_name(TARGET_LINK_TITLE, doc=doc)
    if link_instance is None:
        raise ValueError("Could not locate link instance \"{0}\".".format(TARGET_LINK_TITLE))

    levels = _collect_levels_with_z(link_doc)
    if not levels:
        raise ValueError("Unable to collect level data from link \"{0}\".".format(link_doc.Title))

    if hasattr(link_instance, "GetTransform"):
        transform = link_instance.GetTransform()
    else:
        transform = link_instance.GetTotalTransform()
    link_source_name = "{0} (link)".format(link_doc.Title)
    panel_records = []
    _collect_panels_from_doc(link_doc, link_source_name, printed_ids, levels, panel_records, transform)

    if not panel_records:
        print("No curtain panels named \"{0}\" were found in link \"{1}\".".format(TARGET_FAMILY_NAME, TARGET_LINK_TITLE))
        return

    wall_type = _get_wall_type_by_name(doc, FURRING_WALL_TYPE_NAME)
    if wall_type is None:
        raise ValueError("Wall type \"{0}\" was not found in the host document.".format(FURRING_WALL_TYPE_NAME))

    host_level_map = _map_levels_by_name(doc)

    transaction = DB.Transaction(doc, __title__)
    transaction.Start()
    try:
        _delete_existing_furring_walls(doc, wall_type)
        _create_furring_walls(doc, panel_records, wall_type, host_level_map)
        transaction.Commit()
    except Exception:
        transaction.RollBack()
        raise



################## main code below #####################
if __name__ == "__main__":
    update_furning_wall(DOC)







