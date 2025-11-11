from Autodesk.Revit import DB  # pyright: ignore

from EnneadTab import NOTIFICATION
from EnneadTab.REVIT import REVIT_FILTER, REVIT_SELECTION
from furring_constants import (
    BASE_OFFSET,
    FULL_SPANDREL_PARAMETER,
    HEIGHT_OFFSET,
    PIER_MARKER_ORDER,
    ROOM_SEPARATOR_MARKER_ORDER,
    ROOM_SEPARATOR_SELECTION_NAME,
    SILL_MARKER_ORDER,
    SILL_WALL_HEIGHT,
)


def _prefix_log_tag(prefix_value):
    if prefix_value in (None, ""):
        return ""
    return "[{0}] ".format(prefix_value)


def _prefix_description(prefix_value):
    if prefix_value in (None, ""):
        return ""
    return " (prefix \"{0}\")".format(prefix_value)


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


def delete_existing_furring_walls(doc, wall_type):
    walls = list(DB.FilteredElementCollector(doc).OfClass(DB.Wall).WhereElementIsNotElementType().ToElements())
    walls = [wall for wall in walls if wall.WallType.Id == wall_type.Id]
    walls = list(REVIT_SELECTION.filter_elements_changable(walls))
    deleted_count = 0
    for wall in walls:
        if getattr(wall, "IsReadOnly", False):
            print("        Cannot delete wall {0}; element is read-only.".format(wall.Id))
            continue
        if hasattr(wall, "Pinned") and wall.Pinned:
            print("        Cannot delete wall {0}; element is pinned.".format(wall.Id))
            continue
        try:
            if hasattr(doc, "IsElementModifiable") and not doc.IsElementModifiable(wall.Id):
                print("        Cannot delete wall {0}; element is not modifiable.".format(wall.Id))
                continue
        except Exception:
            pass
        doc.Delete(wall.Id)
        deleted_count += 1
    return deleted_count


def create_furring_walls(doc, panel_records, wall_type, host_level_map):
    base_offset = BASE_OFFSET
    created_count = 0
    segment_plans = []
    for record in panel_records:
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
            })

        sill_markers = record.get("sill_markers", {})
        sill_points = []
        sill_missing = False
        for marker_key in SILL_MARKER_ORDER:
            entry = sill_markers.get(marker_key)
            if entry is None or entry["point_host"] is None:
                sill_missing = True
                if entry is None or entry["element"] is None:
                    print("        Missing sill marker \"{0}\" for panel {1}; skipping sill wall.".format(marker_key, record["panel_unique_id"]))
                else:
                    print("        Cannot determine host point for sill marker \"{0}\" on panel {1}; skipping sill wall.".format(marker_key, record["panel_unique_id"]))
                break
            sill_points.append(entry["point_host"])
        if not sill_missing and len(sill_points) == len(SILL_MARKER_ORDER):
            segment_plans.append({
                "panel_id": record["panel_unique_id"],
                "host_level": host_level,
                "height": SILL_WALL_HEIGHT,
                "points": sill_points,
                "marker_order": SILL_MARKER_ORDER,
                "prefix": None,
                "room_bounding": False,
            })

    total_segments = 0
    for plan in segment_plans:
        points = plan.get("points")
        if points and len(points) > 1:
            total_segments += len(points) - 1
    if total_segments == 0:
        return created_count

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
                    try:
                        room_bounding_param.Set(0)
                    except Exception as exc:
                        print("        Unable to disable room bounding for wall {0}: {1}".format(new_wall.Id, exc))
            try:
                new_wall.CrossSection = DB.WallCrossSection.SingleSlanted
            except Exception as exc:
                print("        Unable to set cross section to SingleSlanted for wall {0}: {1}".format(new_wall.Id, exc))
            start_name = marker_order[idx] if idx < len(marker_order) else "?"
            end_name = marker_order[idx + 1] if (idx + 1) < len(marker_order) else "?"
            if current_index == total_segments or current_index % 99 == 0 or current_index == 1:
                print("        [{0}/{1}] {2}Created furring wall ({3}->{4}) UniqueId: {5}".format(
                    current_index,
                    total_segments,
                    _prefix_log_tag(prefix_value),
                    start_name,
                    end_name,
                    new_wall.UniqueId
                ))
            if total_segments and (current_index % 200 == 0 or current_index == total_segments):
                NOTIFICATION.messenger("{0} of {1} furring wall segments processed.".format(current_index, total_segments))
            created_count += 1
    return created_count


def delete_room_separation_lines(doc):
    selection_filter = REVIT_FILTER.get_selection_filter_by_name(doc, ROOM_SEPARATOR_SELECTION_NAME)
    if not selection_filter:
        return 0
    element_ids = list(selection_filter.GetElementIds())
    deleted_count = 0
    for element_id in element_ids:
        element = doc.GetElement(element_id)
        if element is None or not element.IsValidObject:
            continue
        try:
            doc.Delete(element_id)
            deleted_count += 1
        except Exception as exc:
            print("        Failed to delete room separation line {0} because {1}".format(element_id, exc))
    if deleted_count and len(element_ids) != deleted_count:
        print("        Removed {0} of {1} saved room separation elements.".format(deleted_count, len(element_ids)))
    return deleted_count


def create_room_separation_lines(doc, panel_records, host_level_map):
    sketch_plane_cache = {}
    plan_view_cache = {}
    line_plans = []
    total_segments = 0
    for record in panel_records:
        level = record.get("nearest_level")
        if level is None:
            print("    Skipping room lines for panel {0}; missing nearest level.".format(record["panel_unique_id"]))
            continue
        host_level = host_level_map.get(level.Name)
        if host_level is None:
            print("    Host level {0} missing for panel {1}; cannot create room separation lines.".format(level.Name, record["panel_unique_id"]))
            continue
        ordered_entries = []
        for marker_key in ROOM_SEPARATOR_MARKER_ORDER:
            entry = record["room_markers"].get(marker_key)
            if entry is None or entry["point_host"] is None:
                print("        Cannot create room line for panel {0}; missing host point for index {1}.".format(record["panel_unique_id"], marker_key))
                ordered_entries = []
                break
            host_point = entry["point_host"]
            adjusted_point = DB.XYZ(host_point.X, host_point.Y, host_level.ProjectElevation)
            ordered_entries.append((marker_key, adjusted_point))
        if len(ordered_entries) < 2:
            continue
        line_plans.append((record["panel_unique_id"], host_level, ordered_entries))
        total_segments += len(ordered_entries) - 1

    if total_segments == 0:
        return 0, []

    created_ids = []
    current_index = 0
    for panel_id, host_level, ordered_entries in line_plans:
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
            if current_index == total_segments or current_index % 99 == 0 or current_index == 1:
                start_name, end_name = segment_names[idx] if idx < len(segment_names) else ("?", "?")
                unique_id = element.UniqueId if element is not None else "Unknown"
                print("        [{0}/{1}] Created room separation line for panel {2} ({3}->{4}) UniqueId: {5}".format(
                    current_index,
                    total_segments,
                    panel_id,
                    start_name,
                    end_name,
                    unique_id,
                ))
            if total_segments and (current_index % 200 == 0 or current_index == total_segments):
                NOTIFICATION.messenger("{0} of {1} room separation segments processed.".format(current_index, total_segments))
    return len(created_ids), created_ids


def _get_or_create_sketch_plane(doc, level, cache):
    cached_plane = cache.get(level.Id)
    if cached_plane is not None and cached_plane.IsValidObject:
        return cached_plane
    try:
        sketch_plane = DB.SketchPlane.Create(doc, level.Id)
    except Exception:
        plane = DB.Plane.CreateByNormalAndOrigin(DB.XYZ.BasisZ, DB.XYZ(0, 0, level.ProjectElevation))
        sketch_plane = DB.SketchPlane.Create(doc, plane)
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
    try:
        view = DB.ViewPlan.Create(doc, view_family_type.Id, level.Id)
        view.Name = _generate_room_plan_view_name(level.Name, doc)
        cache[level.Id] = view
        return view
    except Exception as exc:
        print("        Unable to create plan view for level {0}: {1}".format(level.Name, exc))
        return None


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

