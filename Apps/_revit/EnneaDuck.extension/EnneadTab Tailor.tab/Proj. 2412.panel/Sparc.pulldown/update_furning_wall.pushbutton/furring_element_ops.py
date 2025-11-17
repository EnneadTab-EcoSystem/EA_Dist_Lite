from Autodesk.Revit import DB  # pyright: ignore

from EnneadTab import NOTIFICATION
from EnneadTab.REVIT import REVIT_FILTER
from furring_constants import (
    BASE_OFFSET,
    FULL_SPANDREL_PARAMETER,
    HEIGHT_OFFSET,
    PIER_MARKER_ORDER,
    ROOM_SEPARATOR_MARKER_ORDER,
    PANEL_SELECTION_FILTER_PREFIX,
    ROOM_SEPARATION_FILTER_PREFIX,
    SILL_MARKER_ORDER,
    SILL_WALL_HEIGHT_DEFAULT,
    SILL_WALL_HEIGHT_RAISED,
    SILL_WALL_HEIGHT_HIGHER,
    IGNORE_FURRING_PARAMETER,
)


ENABLE_VERBOSE_LOGS = False


def _prefix_log_tag(prefix_value):
    if prefix_value in (None, ""):
        return ""
    return "[{0}] ".format(prefix_value)


def _prefix_description(prefix_value):
    if prefix_value in (None, ""):
        return ""
    return " (prefix \"{0}\")".format(prefix_value)


def _format_xyz(point):
    if point is None:
        return "None"
    try:
        return "{0}, {1}, {2}".format(point.X, point.Y, point.Z)
    except Exception:
        return "Unknown"


def _format_parameter_value(parameter):
    if parameter is None:
        return "Unavailable"
    storage_type = parameter.StorageType
    try:
        value = parameter.AsString()
        if value:
            return value
        value = parameter.AsValueString()
        if value:
            return value
        if storage_type == DB.StorageType.Integer:
            return str(parameter.AsInteger())
        if storage_type == DB.StorageType.Double:
            return str(parameter.AsDouble())
        if storage_type == DB.StorageType.ElementId:
            element_id = parameter.AsElementId()
            if element_id is not None:
                return "ElementId({0})".format(element_id.IntegerValue)
    except Exception as error:
        return "Error retrieving value: {0}".format(error)
    return "None"


def _print_panel_parameter_dump(panel_record):
    panel_element = panel_record.get("panel_element")
    if panel_element is None:
        print("        Panel element not available; cannot dump parameters.")
        return
    print("        Panel parameter dump for {0}:".format(panel_record.get("panel_unique_id")))
    parameter_entries = []
    parameters = getattr(panel_element, "Parameters", None)
    if parameters is None:
        print("            No parameters available on element.")
        return
    for parameter in parameters:
        if parameter is None:
            continue
        definition = getattr(parameter, "Definition", None)
        name = getattr(definition, "Name", None) if definition is not None else None
        if not name:
            name = "Unnamed Parameter"
        storage_type = str(parameter.StorageType)
        value_text = _format_parameter_value(parameter)
        parameter_entries.append((name, storage_type, value_text))
    try:
        parameter_entries.sort(key=lambda item: item[0])
    except Exception:
        pass
    for name, storage_type, value_text in parameter_entries:
        print("            {0} (StorageType: {1}): {2}".format(name, storage_type, value_text))


def _print_room_marker_points(panel_record):
    panel_id = panel_record.get("panel_unique_id")
    print("        Room separation marker points for panel {0}:".format(panel_id))
    marker_groups = panel_record.get("room_marker_groups") or []
    if marker_groups:
        for group in marker_groups:
            prefix_value = group.get("prefix")
            print("            Group prefix: {0}".format(prefix_value if prefix_value else "None"))
            marker_data = group.get("markers", {})
            _print_room_marker_entries(marker_data, indent="                ")
    else:
        marker_data = panel_record.get("room_markers", {})
        _print_room_marker_entries(marker_data, indent="            ")


def _print_room_marker_entries(marker_data, indent):
    for marker_key in ROOM_SEPARATOR_MARKER_ORDER:
        entry = marker_data.get(marker_key)
        if entry is None:
            print("{0}{1}: marker entry missing.".format(indent, marker_key))
            continue
        element = entry.get("element")
        unique_id = entry.get("unique_id", "Unknown")
        host_point = entry.get("point_host")
        link_point = entry.get("point_link")
        location_kind = entry.get("location_kind", "Unknown")
        diagnostic_note = entry.get("diagnostic_note")
        element_text = element.UniqueId if element is not None else unique_id
        print("{0}{1}: element UniqueId: {2}".format(indent, marker_key, element_text))
        print("{0}    Host XYZ: {1}".format(indent, _format_xyz(host_point)))
        print("{0}    Link XYZ: {1}".format(indent, _format_xyz(link_point)))
        print("{0}    Location kind: {1}".format(indent, location_kind))
        if diagnostic_note:
            print("{0}    Note: {1}".format(indent, diagnostic_note))


def _summarize_marker_sets(marker_sets, marker_order, context_label):
    summaries = []
    total_required = len(marker_order)
    for prefix_value, marker_map in marker_sets:
        available = 0
        for marker_key in marker_order:
            entry = marker_map.get(marker_key)
            if entry is not None and entry.get("point_host") is not None:
                available += 1
        if prefix_value in (None, ""):
            prefix_label = "no-prefix"
        else:
            prefix_label = str(prefix_value)
        summaries.append("{0}:{1}/{2}".format(prefix_label, available, total_required))
    if summaries:
        print("        {0} marker groups: {1}".format(context_label, ", ".join(summaries)))


def _log_room_marker_debug(panel_record, marker_sets):
    _summarize_marker_sets(marker_sets, ROOM_SEPARATOR_MARKER_ORDER, "Room separation")
    if ENABLE_VERBOSE_LOGS:
        _print_room_marker_points(panel_record)
        _print_panel_parameter_dump(panel_record)


def _iter_room_marker_sets(panel_record):
    marker_groups = panel_record.get("room_marker_groups") or []
    if marker_groups:
        result = []
        for group in marker_groups:
            marker_data = group.get("markers", {})
            prefix_value = group.get("prefix")
            result.append((prefix_value, marker_data))
        return result
    return [(None, panel_record.get("room_markers", {}))]


def _sanitize_filter_token(raw_value, fallback_value):
    if raw_value is None:
        token = fallback_value
    else:
        token = str(raw_value)
    if token is None:
        token = fallback_value
    token = token.strip()
    if not token:
        token = fallback_value
    replacement_pairs = [
        ("\r", " "),
        ("\n", " "),
        ("\t", " "),
    ]
    for search_value, replace_value in replacement_pairs:
        token = token.replace(search_value, replace_value)
    invalid_chars = [
        ":", "/", "\\", "<", ">", "\"", "|", "?", "*",
    ]
    for char in invalid_chars:
        token = token.replace(char, "_")
    while "  " in token:
        token = token.replace("  ", " ")
    return token


def build_panel_selection_filter_name(family_name, type_name):
    family_token = _sanitize_filter_token(family_name, "Unknown Family")
    if type_name is None:
        type_fallback = "All Types"
    else:
        type_fallback = "Unnamed Type"
    type_token = _sanitize_filter_token(type_name, type_fallback)
    return "{0}__{1}__{2}".format(PANEL_SELECTION_FILTER_PREFIX, family_token, type_token)


def build_room_separation_filter_name(family_name, type_name):
    family_token = _sanitize_filter_token(family_name, "Unknown Family")
    if type_name is None:
        type_fallback = "All Types"
    else:
        type_fallback = "Unnamed Type"
    type_token = _sanitize_filter_token(type_name, type_fallback)
    return "{0}__{1}__{2}".format(ROOM_SEPARATION_FILTER_PREFIX, family_token, type_token)


def delete_elements_in_selection_filter(doc, filter_name):
    selection_filter = REVIT_FILTER.get_selection_filter_by_name(doc, filter_name)
    if not selection_filter:
        return (0, 0, 0)
    element_ids = list(selection_filter.GetElementIds())
    deleted_total = 0
    deleted_walls = 0
    deleted_room_lines = 0
    room_line_category_id = DB.ElementId(DB.BuiltInCategory.OST_RoomSeparationLines)
    for element_id in element_ids:
        element = doc.GetElement(element_id)
        if element is None or not element.IsValidObject:
            continue
        if getattr(element, "IsReadOnly", False):
            print("        Cannot delete element {0}; element is read-only.".format(element.Id))
            continue
        if hasattr(element, "Pinned") and element.Pinned:
            print("        Cannot delete element {0}; element is pinned.".format(element.Id))
            continue
        is_wall = isinstance(element, DB.Wall)
        is_room_line = False
        if not is_wall and room_line_category_id is not None:
            category = getattr(element, "Category", None)
            if category is not None and category.Id == room_line_category_id:
                is_room_line = True
        doc.Delete(element_id)
        deleted_total += 1
        if is_wall:
            deleted_walls += 1
        elif is_room_line:
            deleted_room_lines += 1
    REVIT_FILTER.update_selection_filter(doc, filter_name, [])
    return (deleted_total, deleted_walls, deleted_room_lines)


def update_panel_selection_filter(doc, filter_name, element_ids):
    selection = []
    seen_ids = set()
    for element_id in element_ids or []:
        if element_id is None:
            continue
        integer_value = element_id.IntegerValue
        if integer_value is not None and integer_value in seen_ids:
            continue
        element = doc.GetElement(element_id)
        if element is None or not element.IsValidObject:
            continue
        if integer_value is not None:
            seen_ids.add(integer_value)
        selection.append(element)
    REVIT_FILTER.update_selection_filter(doc, filter_name, selection)
    return len(selection)


def map_levels_by_name(doc):
    level_map = {}
    levels = DB.FilteredElementCollector(doc).OfClass(DB.Level).WhereElementIsNotElementType()
    for level in levels:
        level_map[level.Name] = level
    return level_map


def get_wall_type_by_name(doc, type_name):
    wall_types = DB.FilteredElementCollector(doc).OfClass(DB.WallType)
    for wall_type in wall_types:
        type_name_param = wall_type.get_Parameter(DB.BuiltInParameter.ALL_MODEL_TYPE_NAME)
        current_name = type_name_param.AsString() if type_name_param else None
        if current_name == type_name:
            return wall_type
    return None


def _calculate_sill_height(panel_record):
    is_raised_higher = panel_record.get("is_sill_raised_higher")
    is_raised = panel_record.get("is_sill_raised")
    
    if is_raised_higher is True:
        return SILL_WALL_HEIGHT_HIGHER
    elif is_raised is True:
        return SILL_WALL_HEIGHT_RAISED
    else:
        return SILL_WALL_HEIGHT_DEFAULT


def create_furring_walls(doc, panel_records, wall_type, host_level_map):
    base_offset = BASE_OFFSET
    created_count = 0
    created_wall_ids = []
    segment_plans = []
    pier_wall_baselines = []
    for record in panel_records:
        ignore_flag = record.get("ignore_furring_flag")
        if ignore_flag is True:
            raw_value = record.get("ignore_furring_raw")
            print("    Skipping furring walls for panel {0}; \"{1}\" parameter is True (raw value: {2}).".format(
                record["panel_unique_id"],
                IGNORE_FURRING_PARAMETER,
                raw_value if raw_value is not None else "N/A",
            ))
            continue
        if record.get("is_full_spandrel"):
            print("    Skipping furring walls for panel {0}; \"{1}\" is True.".format(
                record["panel_unique_id"],
                FULL_SPANDREL_PARAMETER,
            ))
            continue
        level = record["nearest_level"]
        if level is None:
            print("    Skipping panel {0} due to missing nearest level.".format(record["panel_unique_id"]))
            continue
        host_level = host_level_map.get(level.Name)
        if host_level is None:
            print("        Host document missing level \"{0}\"; skipping panel {1} for furring walls.".format(level.Name, record["panel_unique_id"]))
            continue
        panel_height = record.get("panel_height")
        if panel_height is None:
            print("        Cannot determine height for panel {0}; missing parameter.".format(record["panel_unique_id"]))
            continue
        height = panel_height - HEIGHT_OFFSET
        if height <= 0:
            print("        Computed height {0} for panel {1} is not positive; skipping.".format(height, record["panel_unique_id"]))
            continue
        pier_marker_groups = record.get("pier_marker_groups")
        if not pier_marker_groups:
            fallback_group = {
                "prefix": None,
                "markers": record.get("pier_markers", {}),
            }
            pier_marker_groups = [fallback_group]
        for group in pier_marker_groups:
            marker_data = group.get("markers", {})
            prefix_value = group.get("prefix")
            ordered_points = []
            missing_key = None
            for marker_key in PIER_MARKER_ORDER:
                entry = marker_data.get(marker_key)
                if entry is None or entry["point_host"] is None:
                    missing_key = marker_key
                    break
                ordered_points.append(entry["point_host"])
            if missing_key is not None:
                print("        Cannot create walls for panel {0}; missing host point for index {1}{2}.".format(
                    record["panel_unique_id"],
                    missing_key,
                    _prefix_description(prefix_value)
                ))
                continue
            if len(ordered_points) < 2:
                continue
            segment_plans.append({
                "panel_id": record["panel_unique_id"],
                "host_level": host_level,
                "height": height,
                "points": ordered_points,
                "marker_order": PIER_MARKER_ORDER,
                "prefix": prefix_value,
                "room_bounding": True,
                "is_sill": False,
            })

        sill_height = _calculate_sill_height(record)
        sill_marker_groups = record.get("sill_marker_groups") or []
        sill_segments_found = False
        if sill_marker_groups:
            for group in sill_marker_groups:
                marker_data = group.get("markers", {})
                prefix_value = group.get("prefix")
                sill_points = []
                missing_key = None
                missing_entry = None
                for marker_key in SILL_MARKER_ORDER:
                    entry = marker_data.get(marker_key)
                    if entry is None or entry["point_host"] is None:
                        missing_key = marker_key
                        missing_entry = entry
                        break
                    sill_points.append(entry["point_host"])
                if missing_key is not None:
                    if missing_entry is None or missing_entry.get("element") is None:
                        print("        Missing sill marker \"{0}\" for panel {1}{2}; skipping sill wall.".format(
                            missing_key,
                            record["panel_unique_id"],
                            _prefix_description(prefix_value),
                        ))
                    else:
                        print("        Cannot determine host point for sill marker \"{0}\" on panel {1}{2}; skipping sill wall.".format(
                            missing_key,
                            record["panel_unique_id"],
                            _prefix_description(prefix_value),
                        ))
                    continue
                if len(sill_points) != len(SILL_MARKER_ORDER):
                    continue
                sill_segments_found = True
                segment_plans.append({
                    "panel_id": record["panel_unique_id"],
                    "host_level": host_level,
                    "height": sill_height,
                    "points": sill_points,
                    "marker_order": SILL_MARKER_ORDER,
                    "prefix": prefix_value,
                    "room_bounding": False,
                    "is_sill": True,
                })
        if not sill_segments_found:
            sill_markers = record.get("sill_markers", {})
            sill_points = []
            sill_missing = False
            for marker_key in SILL_MARKER_ORDER:
                entry = sill_markers.get(marker_key)
                if entry is None or entry["point_host"] is None:
                    sill_missing = True
                    if entry is None or entry.get("element") is None:
                        print("        Missing sill marker \"{0}\" for panel {1}; skipping sill wall.".format(marker_key, record["panel_unique_id"]))
                    else:
                        print("        Cannot determine host point for sill marker \"{0}\" on panel {1}; skipping sill wall.".format(marker_key, record["panel_unique_id"]))
                    break
                sill_points.append(entry["point_host"])
            if not sill_missing and len(sill_points) == len(SILL_MARKER_ORDER):
                segment_plans.append({
                    "panel_id": record["panel_unique_id"],
                    "host_level": host_level,
                    "height": sill_height,
                    "points": sill_points,
                    "marker_order": SILL_MARKER_ORDER,
                    "prefix": None,
                    "room_bounding": False,
                    "is_sill": True,
                })

    total_segments = 0
    for plan in segment_plans:
        points = plan.get("points")
        if points and len(points) > 1:
            total_segments += len(points) - 1
    if total_segments == 0:
        return created_count, created_wall_ids

    current_index = 0
    for plan in segment_plans:
        host_level = plan["host_level"]
        height = plan["height"]
        ordered_points = plan["points"]
        marker_order = plan["marker_order"]
        prefix_value = plan.get("prefix")
        room_bounding_enabled = plan.get("room_bounding", True)
        for idx in range(len(ordered_points) - 1):
            current_index += 1
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
            if not room_bounding_enabled:
                room_bounding_param = new_wall.get_Parameter(DB.BuiltInParameter.WALL_ATTR_ROOM_BOUNDING)
                if room_bounding_param is not None and not room_bounding_param.IsReadOnly:
                    room_bounding_param.Set(0)
            new_wall.CrossSection = DB.WallCrossSection.SingleSlanted
            start_name = marker_order[idx] if idx < len(marker_order) else "?"
            end_name = marker_order[idx + 1] if (idx + 1) < len(marker_order) else "?"
            if ENABLE_VERBOSE_LOGS and (current_index == total_segments or current_index % 99 == 0 or current_index == 1):
                print("        [{0}/{1}] {2}Created furring wall ({3}->{4}) UniqueId: {5}".format(
                    current_index,
                    total_segments,
                    _prefix_log_tag(prefix_value),
                    start_name,
                    end_name,
                    new_wall.UniqueId
                ))
            if total_segments and ((ENABLE_VERBOSE_LOGS and current_index % 200 == 0) or current_index == total_segments):
                NOTIFICATION.messenger("{0} of {1} furring wall segments processed.".format(current_index, total_segments))
            created_count += 1
            created_wall_ids.append(new_wall.Id)
            if not plan.get("is_sill"):
                baseline_key = _build_baseline_key(start_point, end_point)
                if baseline_key is not None:
                    pier_wall_baselines.append((baseline_key, new_wall.Id))
            if plan.get("is_sill"):
                DB.WallUtils.DisallowWallJoinAtEnd(new_wall, 0)
                DB.WallUtils.DisallowWallJoinAtEnd(new_wall, 1)
    deleted_duplicates = _cleanup_duplicate_pier_walls(doc, pier_wall_baselines)
    if deleted_duplicates:
        deleted_values = set()
        for wall_id in deleted_duplicates:
            deleted_values.add(wall_id.IntegerValue)
        if deleted_values:
            remaining_ids = []
            for wall_id in created_wall_ids:
                integer_value = wall_id.IntegerValue
                if integer_value is not None and integer_value in deleted_values:
                    continue
                remaining_ids.append(wall_id)
            created_wall_ids = remaining_ids
    created_count = len(created_wall_ids)
    return created_count, created_wall_ids


def _build_baseline_key(start_point, end_point, precision=6):
    if start_point is None or end_point is None:
        return None
    start_tuple = (round(start_point.X, precision), round(start_point.Y, precision), round(start_point.Z, precision))
    end_tuple = (round(end_point.X, precision), round(end_point.Y, precision), round(end_point.Z, precision))
    if start_tuple <= end_tuple:
        return (start_tuple, end_tuple)
    return (end_tuple, start_tuple)


def _cleanup_duplicate_pier_walls(doc, baseline_records):
    if not baseline_records:
        return []
    baseline_map = {}
    for baseline_key, wall_id in baseline_records:
        if baseline_key is None:
            continue
        if baseline_key not in baseline_map:
            baseline_map[baseline_key] = []
        baseline_map[baseline_key].append(wall_id)
    deleted_ids = []
    for baseline_key in baseline_map:
        wall_ids = baseline_map[baseline_key]
        if len(wall_ids) <= 1:
            continue
        for wall_id in wall_ids:
            doc.Delete(wall_id)
            deleted_ids.append(wall_id)
    if deleted_ids:
        print("    Removed {0} duplicate pier furring wall(s) with matching baselines.".format(len(deleted_ids)))
    return deleted_ids


def create_room_separation_lines(doc, panel_records, host_level_map):
    sketch_plane_cache = {}
    plan_view_cache = {}
    line_plans = []
    total_segments = 0
    for record in panel_records:
        ignore_flag = record.get("ignore_furring_flag")
        if ignore_flag is True:
            raw_value = record.get("ignore_furring_raw")
            print("    Ignore furring flag is True for panel {0}; \"{1}\" raw value: {2}. Proceeding with room separation lines.".format(
                record["panel_unique_id"],
                IGNORE_FURRING_PARAMETER,
                raw_value if raw_value is not None else "N/A",
            ))
        level = record.get("nearest_level")
        if level is None:
            print("    Skipping room lines for panel {0}; missing nearest level.".format(record["panel_unique_id"]))
            continue
        host_level = host_level_map.get(level.Name)
        if host_level is None:
            print("    Host level {0} missing for panel {1}; cannot create room separation lines.".format(level.Name, record["panel_unique_id"]))
            continue
        debug_logged = False
        marker_sets = _iter_room_marker_sets(record)
        valid_set_found = False
        for prefix_value, marker_map in marker_sets:
            ordered_entries = []
            for marker_key in ROOM_SEPARATOR_MARKER_ORDER:
                entry = marker_map.get(marker_key)
                if entry is None or entry["point_host"] is None:
                    continue
                host_point = entry["point_host"]
                adjusted_point = DB.XYZ(host_point.X, host_point.Y, host_level.ProjectElevation)
                ordered_entries.append((marker_key, adjusted_point))
            if len(ordered_entries) < 2:
                if not debug_logged:
                    _log_room_marker_debug(record, marker_sets)
                    debug_logged = True
                continue
            valid_set_found = True
            line_plans.append((record["panel_unique_id"], host_level, ordered_entries, prefix_value))
            total_segments += len(ordered_entries) - 1
        if not valid_set_found:
            continue

    if total_segments == 0:
        return 0, []

    created_ids = []
    current_index = 0
    for panel_id, host_level, ordered_entries, prefix_value in line_plans:
        sketch_plane = _get_or_create_sketch_plane(doc, host_level, sketch_plane_cache)
        plan_view = _get_or_create_level_plan_view(doc, host_level, plan_view_cache)
        if plan_view is None:
            print("        Unable to determine plan view for level {0}; skipping room lines for panel {1}.".format(
                host_level.Name,
                panel_id,
            ))
            continue
        curve_array = DB.CurveArray()
        segment_names = []
        for idx in range(len(ordered_entries) - 1):
            start_name, start_point = ordered_entries[idx]
            end_name, end_point = ordered_entries[idx + 1]
            if start_point is None or end_point is None:
                continue
            if start_point.DistanceTo(end_point) <= 0.0001:
                continue
            line = DB.Line.CreateBound(start_point, end_point)
            curve_array.Append(line)
            segment_names.append((start_name, end_name))
        if curve_array.Size == 0:
            continue
        new_lines = doc.Create.NewRoomBoundaryLines(sketch_plane, curve_array, plan_view)
        for idx, item in enumerate(new_lines):
            if isinstance(item, DB.ElementId):
                element_id = item
                element = doc.GetElement(element_id)
            else:
                element = item
                element_id = element.Id if element is not None else None
            if element_id is None:
                continue
            created_ids.append(element_id)
            current_index += 1
            if ENABLE_VERBOSE_LOGS and (current_index == total_segments or current_index % 99 == 0 or current_index == 1):
                start_name, end_name = segment_names[idx] if idx < len(segment_names) else ("?", "?")
                unique_id = element.UniqueId if element is not None else "Unknown"
                print("        [{0}/{1}] {2}Created room separation line for panel {3} ({4}->{5}) UniqueId: {6}".format(
                    current_index,
                    total_segments,
                    _prefix_log_tag(prefix_value),
                    panel_id,
                    start_name,
                    end_name,
                    unique_id,
                ))
            if total_segments and ((ENABLE_VERBOSE_LOGS and current_index % 200 == 0) or current_index == total_segments):
                NOTIFICATION.messenger("{0} of {1} room separation segments processed.".format(current_index, total_segments))
    return len(created_ids), created_ids


def _get_or_create_sketch_plane(doc, level, cache):
    cached_plane = cache.get(level.Id)
    if cached_plane is not None and cached_plane.IsValidObject:
        return cached_plane
    sketch_plane = DB.SketchPlane.Create(doc, level.Id)
    cache[level.Id] = sketch_plane
    return sketch_plane


def _get_or_create_level_plan_view(doc, level, cache):
    cached_view = cache.get(level.Id)
    if cached_view is not None and cached_view.IsValidObject:
        return cached_view
    collector = DB.FilteredElementCollector(doc).OfClass(DB.ViewPlan)
    for view in collector:
        if view.IsTemplate:
            continue
        if getattr(view, "GenLevel", None) and view.GenLevel.Id == level.Id:
            cache[level.Id] = view
            return view
    view_family_type = _get_default_floor_plan_view_type(doc)
    if view_family_type is None:
        return None
    view = DB.ViewPlan.Create(doc, view_family_type.Id, level.Id)
    view.Name = _generate_room_plan_view_name(level.Name, doc)
    cache[level.Id] = view
    return view


def _get_default_floor_plan_view_type(doc):
    collector = DB.FilteredElementCollector(doc).OfClass(DB.ViewFamilyType)
    for view_type in collector:
        if view_type.ViewFamily == DB.ViewFamily.FloorPlan:
            return view_type
    return None


def _generate_room_plan_view_name(level_name, doc):
    base_name = "MagicPlanDoNotDelete_{0}".format(level_name)
    existing = set()
    collector = DB.FilteredElementCollector(doc).OfClass(DB.View)
    for view in collector:
        if view.IsTemplate:
            continue
        existing.add(view.Name)
    candidate = base_name
    index = 1
    while candidate in existing:
        candidate = "{0} ({1})".format(base_name, index)
        index += 1
    return candidate

