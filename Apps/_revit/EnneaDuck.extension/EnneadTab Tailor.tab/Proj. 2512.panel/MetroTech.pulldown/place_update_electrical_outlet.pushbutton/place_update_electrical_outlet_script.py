#!/usr/bin/python
# -*- coding: utf-8 -*-

__doc__ = """Place new electrical outlet instances by picking faces or walls, from a
furniture family's nested position marker, or batch-update the type of outlets
already in the model.

Works with any loaded family, so it is not locked to a single MetroTech (2512)
outlet family: pick whichever family/type your project uses each time.

Features:
- Face-based outlet families are placed on the wall or floor face you click
- Wall-hosted outlet families are placed at the point you click on a wall
- No furniture family name is ever hardcoded: this discovers every furniture family
  that carries a `_para_map` marker by scanning for the parameter and walking up to
  the host instance, then lets you multi-select which of those discovered families to
  process, so you can run surgically on just one furniture type after a model fix
  instead of always reprocessing everything
- Within each selected furniture instance, every nested marker fans rays outward from
  its corrected point to the nearest wall/floor (the marker carries position only, no
  dependable facing rotation to aim a single ray), and places or updates the matching
  outlet in the current model
- Each marker instance names its own outlet family/type and mount height via its
  `_para_map` JSON parameter, so markers nested in the same furniture instance can
  each place a different outlet at a different height; the outlet's Z always comes
  from its host furniture instance's level plus that mount height, never the
  marker's raw position (markers are modeled above the furniture body on purpose, to
  stay visible/pickable -- see the comment above PARA_MAP_TEMPLATE)
- Every "Place From Marker" run writes a timestamped debug log to the local dump
  folder (path printed at the end of the run) recording what was found, resolved,
  skipped, and placed -- open it when a run gets stuck to see exactly what happened.
  If many markers in a row fail for the identical reason, the run aborts early
  instead of grinding through the rest of a large model with a doomed setup
- An outlet already sitting near a marker is never deleted: a review grid lists
  every conflict (level, family, type, reason) so you can Keep or Move each one,
  with a Zoom button and Previous/Next navigation to inspect it in the model first
- Existing outlet instances of a type can be swapped to a different type in one pass
- Instances owned by another user in a workshared model are skipped, never changed

Usage:
1. Run the button and choose Place, Place From Marker, or Update Type
2. Place: pick a family and type, then click faces/walls until you press Escape
3. Place From Marker: pick any furniture instance or one of its markers (just to pick
   which document to search -- host model or a link), then multi-select which
   discovered furniture families to process. Each nested marker's own `_para_map`
   names the outlet family/type and mount height to place there. Markers with no
   outlet nearby are placed once you Apply; markers with an outlet already nearby
   open a review grid first (Zoom, Previous/Next, Keep/Move per row)
4. Update Type: pick the family, current type, new type, then confirm"""
__title__ = "Place/Update\nElectrical Outlet"

import datetime
import json
import math

import proDUCKtion  # pyright: ignore
proDUCKtion.validify()

from Autodesk.Revit import DB  # pyright: ignore
from Autodesk.Revit.UI import IExternalEventHandler, ExternalEvent  # pyright: ignore
from Autodesk.Revit.UI.Selection import ObjectType, ISelectionFilter  # pyright: ignore
from Autodesk.Revit.Exceptions import OperationCanceledException, InvalidOperationException  # pyright: ignore
from System.Collections.Generic import List  # pyright: ignore
from pyrevit import forms
from pyrevit.forms import WPFWindow

from EnneadTab import ERROR_HANDLE, FOLDER, LOG, NOTIFICATION
from EnneadTab.REVIT import REVIT_APPLICATION, REVIT_SELECTION, REVIT_FORMS, REVIT_FAMILY

from outlet_conflict_row import OutletConflictRow, OutletPlacementTarget, ACTION_OPTIONS

UIDOC = REVIT_APPLICATION.get_uidoc()
DOC = REVIT_APPLICATION.get_doc()
__persistentengine__ = True

# The marker family carries position only, no dependable facing rotation, so the
# host wall/floor is found with a fan of rays cast outward from the marker point
# rather than trusting one axis of its orientation. Horizontal rays (evenly spaced
# around a full circle) cover walls; a straight-down and straight-up ray cover
# floors, which the horizontal fan alone would never hit.
MARKER_RAYCAST_FAN_COUNT = 16  # horizontal rays in the fan; higher = finer angular coverage

MARKER_RAYCAST_MAX_DISTANCE = 3.0  # feet; how far to ray-cast to find a host face
EXISTING_OUTLET_SEARCH_RADIUS = 1.0  # feet; how close counts as "already at this marker"
EXISTING_OUTLET_SAME_SPOT_TOLERANCE = 0.05  # feet; close enough to skip as a no-op

# Which furniture families carry markers is NEVER hardcoded here: discover_qualified_
# furniture_family_names() finds them live, by scanning for _para_map-carrying
# markers and walking each one up to its host furniture instance's family name (via
# SuperComponent). This survives new furniture families getting markers added later
# with zero code changes, and place_from_markers lets the user multi-select a subset
# of the discovered names for a surgical run (e.g. re-running on just one furniture
# type after a model fix) instead of always processing every qualified family.

# If this many markers in a row fail with the EXACT SAME reason, resolve_marker_targets
# stops early instead of grinding through the rest of a possibly large model: an
# identical repeated reason (e.g. "host furniture has no level") signals a systemic
# modeling/setup problem, not a string of unrelated one-off marker issues, so nothing
# is gained by continuing -- fail fast, fix the root cause, rerun.
CONSECUTIVE_UNRESOLVED_ABORT_THRESHOLD = 5

# Revit has no native JSON/dict parameter type, so a marker instance carries its
# per-instance info (which outlet family/type to place there, at what mount height)
# as one Multiline Text parameter holding a JSON-serialized dict. Multiline (not
# plain Text) so a human opening the marker instance inside the furniture family can
# actually read and hand-edit the indented JSON in the Properties palette. Read with
# get_marker_para_map, write with set_marker_para_map -- neither ever touches the
# parameter as a raw string anywhere else in this file.
PARA_MAP_PARAMETER_NAME = "_para_map"

# Template/default shape of that dict. "family_name"/"type_name" name the outlet to
# place at THIS marker; "mount_height" is the outlet's height in feet above its HOST
# FURNITURE INSTANCE's level (see resolve_marker_targets -- the furniture instance
# that directly nests this marker). All three keys are required: a marker missing any
# one of them cannot be placed. There is no marker-family-wide fallback for any of
# them -- each marker names its own outlet and height independently, even markers
# nested in the same furniture instance.
#
# WHY NOT THE MARKER'S RAW POSITION: markers are deliberately modeled ABOVE the
# furniture geometry, not at the outlet's real-world height. Many outlets sit low
# (floor boxes, base plugs); a marker placed at that real height would be buried
# inside or below the furniture body, making it hard to see and pick in views/3D. So
# the marker's raw Z is a MODELING/VISIBILITY convenience only -- it has no design
# meaning and must never be read as the outlet's height. The actual intended height is
# `mount_height`, applied against the host furniture instance's level; the marker's
# X/Y are still trustworthy (that's real plan position) and are used as-is.
PARA_MAP_TEMPLATE = {
    "family_name": None,
    "type_name": None,
    "mount_height": None,
}


def get_marker_para_map(marker):
    """Read and JSON-parse `marker`'s _para_map text parameter.

    Returns PARA_MAP_TEMPLATE's shape with every key defaulted to None, overlaid with
    whatever the parameter actually holds -- missing keys, a missing/empty parameter,
    or unparsable JSON all fall back to the all-None default rather than raising, since
    the vast majority of markers are expected to carry no override at all.
    """
    data = dict(PARA_MAP_TEMPLATE)
    param = marker.LookupParameter(PARA_MAP_PARAMETER_NAME)
    raw = param.AsString() if param else None
    if not raw:
        return data
    try:
        parsed = json.loads(raw)
    except ValueError:
        debug_log(
            "Marker [{}]'s {} is not valid JSON, ignoring: {}".format(
                marker.Id, PARA_MAP_PARAMETER_NAME, raw))
        return data
    if isinstance(parsed, dict):
        data.update(parsed)
    return data


def set_marker_para_map(marker, data):
    """JSON-serialize `data` and write it into `marker`'s _para_map text parameter.

    Indented (not compact) so a human opening this marker instance inside the
    furniture family sees readable, multi-line JSON in the Properties palette --
    the parameter is Multiline Text specifically to make that legible.

    Must run inside an open transaction. No-ops (with a note) if the marker's family
    has no such parameter -- e.g. an older loaded instance of the family predating
    this parameter's addition.
    """
    param = marker.LookupParameter(PARA_MAP_PARAMETER_NAME)
    if not param:
        ERROR_HANDLE.print_note(
            "Marker [{}] has no {} parameter, cannot write.".format(marker.Id, PARA_MAP_PARAMETER_NAME))
        return
    param.Set(json.dumps(data, indent=2))


_run_log_lines = []
_run_log_path = None


def start_run_log():
    """Reset the debug log buffer and pick a fresh timestamped file path for one
    "Place From Marker" run.

    Call once, before resolve_marker_targets. Every debug_log() call for the rest of
    the run -- including the Apply step, which fires later from a separate
    ExternalEvent after the review window closes -- appends to the same buffer and
    gets flushed to the SAME file by save_run_log().
    """
    global _run_log_lines, _run_log_path
    _run_log_lines = []
    timestamp = datetime.datetime.now().strftime("%Y%m%d_%H%M%S")
    _run_log_path = FOLDER.get_local_dump_folder_file("MetroTechOutlet_{}.log".format(timestamp))


def debug_log(message):
    """Append one line to this run's debug log and echo it via ERROR_HANDLE.print_note.

    Unlike print_note (gated on USER.IS_DEVELOPER), the buffered copy is never gated:
    the whole point of this per-run log file is that whoever is testing the tool can
    open it afterward and see exactly what happened, not just a developer watching
    the pyRevit output window live.
    """
    _run_log_lines.append(message)
    try:
        ERROR_HANDLE.print_note(message)
    except Exception:
        pass


def save_run_log():
    """Flush this run's accumulated debug lines to _run_log_path.

    Safe to call more than once per run (once after marker resolution, again after
    Apply) -- each call rewrites the same file with everything logged so far. Quietly
    no-ops if start_run_log() was never called or nothing was logged.

    Returns:
        str or None: the file path written, or None if there was nothing to save.
    """
    if not _run_log_path or not _run_log_lines:
        return None
    try:
        with open(_run_log_path, "w") as f:
            f.write("\n".join(_run_log_lines))
        return _run_log_path
    except Exception as e:
        ERROR_HANDLE.print_note("Failed to save debug log: {}".format(e))
        return None


class WallOrFloorFaceFilter(ISelectionFilter):
    """Restrict face picking to walls and floors, the two hosts an outlet is placed on."""
    def AllowElement(self, elem):
        return isinstance(elem, (DB.Wall, DB.Floor))

    def AllowReference(self, ref, point):
        return True


class WallPointFilter(ISelectionFilter):
    """Restrict point-on-element picking to walls, for wall-hosted outlet families."""
    def AllowElement(self, elem):
        return isinstance(elem, DB.Wall)

    def AllowReference(self, ref, point):
        return True


def type_name_of(family_type):
    return family_type.LookupParameter("Type Name").AsString()


def pick_faces_on_walls_and_floors():
    """Loop DB.Reference picks on wall/floor faces until the user presses Escape.

    Returns:
        list of (DB.Element host, DB.Face face, DB.XYZ point)
    """
    picks = []
    face_filter = WallOrFloorFaceFilter()
    while True:
        try:
            ref = UIDOC.Selection.PickObject(
                ObjectType.Face, face_filter,
                "Pick a wall or floor face to place an outlet (Escape to finish)")
        except OperationCanceledException:
            break
        host = DOC.GetElement(ref)
        face = host.GetGeometryObjectFromReference(ref)
        picks.append((host, face, ref.GlobalPoint))
    return picks


def pick_points_on_walls():
    """Loop point-on-wall picks until the user presses Escape.

    Returns:
        list of (DB.Wall wall, DB.XYZ point)
    """
    picks = []
    wall_filter = WallPointFilter()
    while True:
        try:
            ref = UIDOC.Selection.PickObject(
                ObjectType.PointOnElement, wall_filter,
                "Pick a point on a wall to place an outlet (Escape to finish)")
        except OperationCanceledException:
            break
        wall = DOC.GetElement(ref.ElementId)
        picks.append((wall, ref.GlobalPoint))
    return picks


def place_face_based(doc, family_symbol, picks):
    placed = []
    failed = []
    for host, face, point in picks:
        try:
            if isinstance(host, DB.Floor):
                instance = REVIT_FAMILY.place_instance_by_floor(family_symbol, host, location=point, doc=doc)
            else:
                instance = REVIT_FAMILY.place_instance_by_face(family_symbol, face, point, doc=doc)
            if instance:
                placed.append(instance)
            else:
                failed.append(host.Id)
        except Exception as e:
            ERROR_HANDLE.print_note("Failed to place outlet on host [{}]: {}".format(host.Id, e))
            failed.append(host.Id)
    return placed, failed


def place_wall_hosted(doc, family_symbol, picks):
    placed = []
    failed = []
    for wall, point in picks:
        try:
            level = doc.GetElement(wall.LevelId)
            instance = REVIT_FAMILY.place_instance_by_wall(family_symbol, point, wall, level=level, doc=doc)
            if instance:
                placed.append(instance)
            else:
                failed.append(wall.Id)
        except Exception as e:
            ERROR_HANDLE.print_note("Failed to place outlet on wall [{}]: {}".format(wall.Id, e))
            failed.append(wall.Id)
    return placed, failed


def get_any_3d_view(doc):
    """Return an existing non-template 3D view, or create a temporary isometric one.

    A view is required by DB.ReferenceIntersector for the marker-driven raycast; a
    plan/section view cannot be used for it.
    """
    views = DB.FilteredElementCollector(doc).OfClass(DB.View3D).WhereElementIsNotElementType().ToElements()
    for view in views:
        if not view.IsTemplate:
            return view
    view_family_type = next(
        (v for v in DB.FilteredElementCollector(doc).OfClass(DB.ViewFamilyType).ToElements()
         if v.ViewFamily == DB.ViewFamily.ThreeDimensional),
        None)
    if view_family_type is None:
        return None
    return DB.View3D.CreateIsometric(doc, view_family_type.Id)


def element_int_id(element):
    """Return an element's ElementId as a plain int (Revit 2026 uses .Value)."""
    try:
        return element.Id.Value
    except AttributeError:
        return element.Id.IntegerValue


def get_level_name(instance, doc):
    level_id = getattr(instance, "LevelId", None)
    if not level_id or level_id == DB.ElementId.InvalidElementId:
        host = getattr(instance, "Host", None)
        level_id = getattr(host, "LevelId", None) if host else None
    if level_id and level_id != DB.ElementId.InvalidElementId:
        level = doc.GetElement(level_id)
        if level:
            return level.Name
    return None


def get_instance_level(doc, instance):
    """Return `instance`'s hosting DB.Level, or None.

    Tries LevelId first (most family instances, including Level-hosted furniture),
    then Host.LevelId (a host-based instance, e.g. wall-hosted). Used to turn a
    marker's _para_map mount_height (feet above its host furniture's level) into an
    absolute Z -- see resolve_marker_targets.
    """
    level_id = getattr(instance, "LevelId", None)
    if not level_id or level_id == DB.ElementId.InvalidElementId:
        host = getattr(instance, "Host", None)
        level_id = getattr(host, "LevelId", None) if host else None
    if level_id and level_id != DB.ElementId.InvalidElementId:
        return doc.GetElement(level_id)
    return None


def build_wall_floor_intersector(view3d):
    """Build the DB.ReferenceIntersector used by every ray of every marker in one run.

    Constructing a ReferenceIntersector is NOT free -- Revit builds a spatial index
    over the view's walls/floors -- so it must be built ONCE per run and reused, not
    rebuilt per ray. The original version rebuilt it inside find_host_face_along_ray,
    i.e. up to 18 times (MARKER_RAYCAST_FAN_COUNT + 2) for every single marker; on a
    model with many markers that is the dominant cost of the whole tool. Reusing one
    instance here is a straight ~18x cut to intersector-construction overhead.
    """
    categories = List[DB.BuiltInCategory]([DB.BuiltInCategory.OST_Walls, DB.BuiltInCategory.OST_Floors])
    multi_filter = DB.ElementMulticategoryFilter(categories)
    intersector = DB.ReferenceIntersector(multi_filter, DB.FindReferenceTarget.Face, view3d)
    intersector.FindReferencesInRevitLinks = False
    return intersector


def find_host_face_along_ray(doc, intersector, point, direction):
    """Ray-cast from `point` along `direction` for the nearest wall/floor face.

    `intersector` is built once per run by build_wall_floor_intersector and reused
    across every ray of every marker -- see that function's docstring for why.

    Returns:
        tuple (DB.Element host, DB.Face face, DB.XYZ hit_point, str stable_ref), or
        (None, None, None, None) when nothing is hit within MARKER_RAYCAST_MAX_DISTANCE.
        `stable_ref` is the Reference's stable representation, so the exact face can
        be re-resolved later (via DB.Reference.ParseFromStableRepresentation) without
        holding the live Face/Reference object across a modeless dialog's idle time.
    """
    hits = intersector.Find(point, direction)
    best = None
    for hit in hits:
        if hit.Proximity > MARKER_RAYCAST_MAX_DISTANCE:
            continue
        if best is None or hit.Proximity < best.Proximity:
            best = hit
    if best is None:
        return None, None, None, None
    reference = best.GetReference()
    host = doc.GetElement(reference)
    face = host.GetGeometryObjectFromReference(reference)
    stable_ref = reference.ConvertToStableRepresentation(doc)
    return host, face, reference.GlobalPoint, stable_ref


def build_fan_directions(horizontal_count):
    """Return `horizontal_count` evenly-spaced unit vectors around a full horizontal
    circle, plus straight-down and straight-up.

    Horizontal rays find walls; a marker's own rotation cannot be trusted to point
    at one (see MARKER_RAYCAST_FAN_COUNT), so every angle is tried and the nearest
    hit wins. Floors are horizontal planes, so only the vertical rays can hit one --
    no amount of horizontal fan density would.
    """
    directions = []
    for i in range(horizontal_count):
        angle = 2.0 * math.pi * i / horizontal_count
        directions.append(DB.XYZ(math.cos(angle), math.sin(angle), 0.0))
    directions.append(DB.XYZ(0.0, 0.0, -1.0))
    directions.append(DB.XYZ(0.0, 0.0, 1.0))
    return directions


def find_nearest_host_face(doc, intersector, point):
    """Cast a fan of rays outward from `point` and return the nearest wall/floor hit.

    The marker only carries a position, not a dependable facing rotation, so the
    direction to the host wall/floor cannot be read off its orientation the way a
    single trusted axis would. Trying every direction in the fan and keeping the
    globally nearest hit finds the host regardless of which way the marker sits.

    `intersector` is built once per run by build_wall_floor_intersector and passed
    through here -- see that function's docstring for why it must not be rebuilt per
    ray or per marker.

    Returns:
        tuple (DB.Element host, DB.Face face, DB.XYZ hit_point, str stable_ref), or
        (None, None, None, None) when nothing is hit within MARKER_RAYCAST_MAX_DISTANCE
        in any direction.
    """
    directions = build_fan_directions(MARKER_RAYCAST_FAN_COUNT)
    best = None
    best_distance = None
    hit_count = 0
    for direction in directions:
        host, face, hit_point, stable_ref = find_host_face_along_ray(doc, intersector, point, direction)
        if host is None:
            continue
        hit_count += 1
        distance = point.DistanceTo(hit_point)
        if best_distance is None or distance < best_distance:
            best = (host, face, hit_point, stable_ref)
            best_distance = distance
    if best is None:
        debug_log(
            "Fan-cast from ({}, {}, {}): 0 of {} rays hit a wall/floor within {} ft".format(
                round(point.X, 2), round(point.Y, 2), round(point.Z, 2),
                len(directions), MARKER_RAYCAST_MAX_DISTANCE))
        return None, None, None, None
    host, face, hit_point, stable_ref = best
    debug_log(
        "Fan-cast from ({}, {}, {}): {} of {} rays hit; nearest host [{}] at {} ft".format(
            round(point.X, 2), round(point.Y, 2), round(point.Z, 2),
            hit_count, len(directions), host.Id, round(best_distance, 3)))
    return best


def discover_qualified_furniture_family_names(doc):
    """Scan `doc` project-wide for every family instance carrying a _para_map
    parameter (a marker, by convention), walk each one up to its host furniture
    instance via SuperComponent, and return the distinct furniture family names found.

    This is the whole reason a furniture family name is never hardcoded in this file:
    any family that happens to nest a _para_map-carrying marker qualifies
    automatically, so a new furniture family with markers needs zero code changes --
    it just shows up in the picker place_from_markers shows next.
    """
    instances = DB.FilteredElementCollector(doc).OfClass(DB.FamilyInstance).WhereElementIsNotElementType().ToElements()
    names = set()
    for instance in instances:
        if instance.LookupParameter(PARA_MAP_PARAMETER_NAME) is None:
            continue
        furniture = getattr(instance, "SuperComponent", None)
        if furniture is None:
            continue
        name = REVIT_FAMILY.get_family_name(furniture)
        if name:
            names.add(name)
    return sorted(names)


def get_furniture_instances(doc, family_names):
    """Return every top-level FamilyInstance in `doc` whose family name is in
    `family_names` (a subset picked from discover_qualified_furniture_family_names).
    """
    instances = DB.FilteredElementCollector(doc).OfClass(DB.FamilyInstance).WhereElementIsNotElementType().ToElements()
    return [instance for instance in instances if REVIT_FAMILY.get_family_name(instance) in family_names]


def get_para_map_markers(host_instance, doc=None):
    """Return every nested family instance directly inside `host_instance` that
    carries a _para_map parameter -- these are outlet position markers, whatever
    their own family name is. A furniture instance can nest more than one marker,
    each independently naming its own outlet/height via that parameter.
    """
    doc = doc or DOC
    class_filter = DB.ElementClassFilter(DB.FamilyInstance)
    try:
        dependent_ids = host_instance.GetDependentElements(class_filter)
    except Exception:
        return []
    markers = []
    for element_id in dependent_ids:
        element = doc.GetElement(element_id)
        if element is None or element.Id == host_instance.Id:
            continue
        if element.LookupParameter(PARA_MAP_PARAMETER_NAME) is not None:
            markers.append(element)
    return markers


def resolve_outlet_symbol(doc, family_name, type_name, cache):
    """Resolve an outlet family/type by name, once per (family_name, type_name) pair.

    `cache` is a plain dict the caller owns and reuses across every marker in one run,
    since many markers typically name the same outlet family/type in their _para_map.

    Returns:
        tuple (DB.Family family, DB.FamilySymbol family_type); either may be None.
    """
    key = (family_name, type_name)
    if key not in cache:
        family = REVIT_FAMILY.get_family_by_name(family_name, doc=doc)
        family_type = REVIT_FAMILY.get_family_type_by_name(family_name, type_name, doc=doc) if family else None
        cache[key] = (family, family_type)
    return cache[key]


def resolve_marker_targets(doc, furniture_family_names, view3d, symbol_cache, marker_doc=None, link_transform=None):
    """Find every instance of `furniture_family_names`, and within each one, every
    nested marker (get_para_map_markers). Each marker's own _para_map names the
    outlet family/type and mount height to place there, so this also resolves that
    outlet symbol and fan-casts the marker's corrected point to its host face.

    A furniture instance can nest more than one marker (each independently naming its
    own outlet/height), so the outlet's final Z always comes from the FURNITURE
    instance's own level -- the marker's direct parent in this top-down walk -- plus
    that marker's _para_map mount_height. Never the marker's raw Z (meaningless
    outside the furniture family's local geometry) and never the ray-cast hit's Z.
    Only the marker's X/Y are taken as-is. That corrected point is what the fan is
    cast FROM, not a value applied after the cast.

    There is no marker-family-wide outlet mapping: two markers in the same furniture
    instance can each name a completely different outlet family/type/height.

    `marker_doc` is searched for furniture instances (defaults to `doc`, the
    current/host document); pass the linked document here when the furniture lives in
    a link. The corrected point is built in `marker_doc`'s local space (X/Y raw, Z
    corrected) and only then mapped into host-doc space via `link_transform` (a link
    instance's total transform), since the ray-cast and every downstream placement
    always target the CURRENT (host) document's walls/floors -- never the link's.
    `symbol_cache` is a plain dict the caller owns, passed straight through to
    resolve_outlet_symbol so repeated (family_name, type_name) pairs are only looked
    up once for the whole run.

    Fails fast: if CONSECUTIVE_UNRESOLVED_ABORT_THRESHOLD markers in a row hit the
    EXACT SAME unresolved reason, this stops immediately instead of grinding through
    every remaining marker of a possibly large model -- an identical repeated reason
    is a systemic modeling/setup problem, not independent one-off marker issues, so
    continuing wastes time without finding anything new. All furniture instances and
    their markers are enumerated up front (cheap) before any ray-casting starts (the
    expensive part), so the abort check can fire before the costly work even begins
    on doomed entries.

    Returns:
        tuple (resolved, unresolved):
          resolved   -- list of (marker, host, face, hit_point, stable_ref, family, family_type)
          unresolved -- list of (marker, reason) for markers that can't be placed --
              possibly a PREFIX of all markers if the abort threshold was hit
    """
    marker_doc = marker_doc or doc
    furniture_instances = get_furniture_instances(marker_doc, furniture_family_names)
    debug_log("Found {} furniture instance(s) of {} in [{}]".format(
        len(furniture_instances), furniture_family_names, marker_doc.Title))

    # Enumerate every (furniture, level, marker) up front -- cheap (GetDependentElements
    # + parameter lookups) -- before the expensive ray-casting loop below even starts.
    marker_entries = []
    for furniture in furniture_instances:
        furniture_level = get_instance_level(marker_doc, furniture)
        markers = get_para_map_markers(furniture, doc=marker_doc)
        debug_log("Furniture [{}] ({}): {} marker(s), level [{}]".format(
            furniture.Id, REVIT_FAMILY.get_family_name(furniture), len(markers),
            furniture_level.Name if furniture_level else "NONE"))
        for marker in markers:
            marker_entries.append((furniture, furniture_level, marker))

    intersector = build_wall_floor_intersector(view3d)

    resolved = []
    unresolved = []
    streak_reason = None
    streak_count = 0

    for index, (furniture, furniture_level, marker) in enumerate(marker_entries):
        para_map = get_marker_para_map(marker)
        if any(value is not None for value in para_map.values()):
            debug_log("Marker [{}] {}: {}".format(marker.Id, PARA_MAP_PARAMETER_NAME, para_map))

        reason = None
        outlet_family_name = para_map.get("family_name")
        outlet_type_name = para_map.get("type_name")
        mount_height = para_map.get("mount_height")
        family = family_type = None
        corrected_point = None
        host = face = hit_point = stable_ref = None

        if not outlet_family_name or not outlet_type_name or mount_height is None:
            reason = "{} needs family_name, type_name, and mount_height all set".format(PARA_MAP_PARAMETER_NAME)
        else:
            family, family_type = resolve_outlet_symbol(doc, outlet_family_name, outlet_type_name, symbol_cache)
            if not family or not family_type:
                reason = "outlet [{}] - [{}] is not loaded".format(outlet_family_name, outlet_type_name)
            elif family.FamilyPlacementType not in (DB.FamilyPlacementType.WorkPlaneBased, DB.FamilyPlacementType.OneLevelBasedHosted):
                reason = "outlet [{}] is neither face-based nor wall-hosted".format(outlet_family_name)
            elif furniture_level is None:
                reason = "host furniture [{}] has no level".format(furniture.Id)
            else:
                local_point, _orientation = REVIT_FAMILY.get_nested_instance_placement(marker)
                if local_point is None:
                    reason = "no location available"
                else:
                    corrected_point = DB.XYZ(local_point.X, local_point.Y, furniture_level.Elevation + mount_height)
                    if link_transform is not None:
                        corrected_point = link_transform.OfPoint(corrected_point)
                    debug_log(
                        "Marker [{}]: furniture [{}] level [{}] (elev {}) + mount_height {} -> corrected point {}".format(
                            marker.Id, furniture.Id, furniture_level.Name, round(furniture_level.Elevation, 2),
                            mount_height, (round(corrected_point.X, 2), round(corrected_point.Y, 2), round(corrected_point.Z, 2))))
                    host, face, hit_point, stable_ref = find_nearest_host_face(doc, intersector, corrected_point)
                    if host is None:
                        reason = "no wall/floor within {} ft in any direction".format(MARKER_RAYCAST_MAX_DISTANCE)

        if reason is None:
            resolved.append((marker, host, face, hit_point, stable_ref, family, family_type))
            streak_reason = None
            streak_count = 0
            continue

        unresolved.append((marker, reason))
        if reason == streak_reason:
            streak_count += 1
        else:
            streak_reason = reason
            streak_count = 1
        if streak_count >= CONSECUTIVE_UNRESOLVED_ABORT_THRESHOLD:
            remaining = len(marker_entries) - index - 1
            debug_log(
                "Aborting early: {} consecutive markers failed with the same reason [{}] -- likely a systemic "
                "model/family setup issue, not independent per-marker problems. Stopping before checking the "
                "remaining {} marker(s); fix the root cause and rerun.".format(streak_count, reason, remaining))
            break

    debug_log("resolve_marker_targets: {} resolved, {} unresolved".format(len(resolved), len(unresolved)))
    return resolved, unresolved


def get_instance_point(instance):
    location = getattr(instance, "Location", None)
    point = getattr(location, "Point", None) if location else None
    if point is None and hasattr(instance, "GetTransform"):
        point = instance.GetTransform().Origin
    return point


def find_nearby_instance(point, instances, radius):
    nearest = None
    nearest_distance = None
    for instance in instances:
        instance_point = get_instance_point(instance)
        if instance_point is None:
            continue
        distance = point.DistanceTo(instance_point)
        if distance <= radius and (nearest_distance is None or distance < nearest_distance):
            nearest = instance
            nearest_distance = distance
    return nearest, nearest_distance


class SimpleEventHandler(IExternalEventHandler):
    """Runs a passed-in function inside Revit's API context.

    Copied from the proven batch_fix_family_name pattern (ACE.panel/Family.pulldown):
    a modeless WPF button click is not in API context, so any Revit API call it
    triggers (a transaction, ShowElements/SetElementIds) must go through an
    ExternalEvent. The callable's return value is read back from `self.OUT`
    synchronously after `.Raise()` returns.
    """
    def __init__(self, do_this):
        self.do_this = do_this
        self.kwargs = None
        self.OUT = None

    def Execute(self, uiapp):
        try:
            try:
                self.OUT = self.do_this(*self.kwargs)
            except Exception as ex:
                ERROR_HANDLE.print_note("outlet marker apply failed: {}".format(ex))
                try:
                    NOTIFICATION.messenger(main_text="Apply failed: {}".format(ex))
                except Exception:
                    pass
        except InvalidOperationException:
            print("InvalidOperationException caught")

    def GetName(self):
        return "outlet marker external event"


def zoom_to_instance(instance_id):
    """Zoom/select a single element by id. Runs in API context via ExternalEvent."""
    element = DOC.GetElement(DB.ElementId(instance_id))
    if element is None:
        return "Element not found (it may have been deleted)."
    ids = List[DB.ElementId]([element.Id])
    UIDOC.ShowElements(ids)
    UIDOC.Selection.SetElementIds(ids)
    return None


def apply_marker_outlets(to_place, conflict_rows):
    """Place new outlets and apply the reviewed Keep/Move decisions, in one transaction.

    Runs in API context via ExternalEvent. Each `to_place` item names its own outlet
    family/type (read from its marker's _para_map -- different markers can name
    different outlets), re-resolved here by name rather than trusting anything held on
    the WPF window, since none of that is guaranteed still valid after however long the
    modeless review grid stayed open. `conflict_rows` only ever moves an ALREADY
    PLACED instance, so it never needs to resolve a family/type.
    """
    doc = DOC
    symbol_cache = {}

    def resolve_symbol(family_name, type_name):
        key = (family_name, type_name)
        if key not in symbol_cache:
            family = REVIT_FAMILY.get_family_by_name(family_name, doc=doc)
            family_type = REVIT_FAMILY.get_family_type_by_name(family_name, type_name, doc=doc) if family else None
            symbol_cache[key] = family_type
        return symbol_cache[key]

    placed = 0
    moved = 0
    kept = 0
    failed = []
    t = DB.Transaction(doc, "Place/Update Electrical Outlet From Marker")
    t.Start()
    try:
        for item in to_place:
            try:
                family_type = resolve_symbol(item.family_name, item.type_name)
                if not family_type:
                    debug_log("Outlet [{}] - [{}] is no longer loaded, skipping host [{}].".format(
                        item.family_name, item.type_name, item.host_id))
                    failed.append(item.host_id)
                    continue
                host = doc.GetElement(DB.ElementId(item.host_id))
                point = DB.XYZ(item.point[0], item.point[1], item.point[2])
                if item.stable_ref:
                    reference = DB.Reference.ParseFromStableRepresentation(doc, item.stable_ref)
                    face = host.GetGeometryObjectFromReference(reference)
                    instance = REVIT_FAMILY.place_instance_by_face(family_type, face, point, doc=doc)
                elif isinstance(host, DB.Wall):
                    level = doc.GetElement(host.LevelId)
                    instance = REVIT_FAMILY.place_instance_by_wall(family_type, point, host, level=level, doc=doc)
                else:
                    instance = None
                if instance:
                    placed += 1
                    debug_log("Placed outlet [{}] - [{}]/[{}] on host [{}] at {}".format(
                        instance.Id, item.family_name, item.type_name, item.host_id, item.point))
                else:
                    failed.append(item.host_id)
            except Exception as e:
                debug_log("Failed to place outlet on host [{}]: {}".format(item.host_id, e))
                failed.append(item.host_id)

        for row in conflict_rows:
            if row.action != "Move":
                kept += 1
                continue
            try:
                existing = doc.GetElement(DB.ElementId(row.existing_instance_id))
                if existing is None:
                    failed.append(row.existing_instance_id)
                    continue
                current_point = get_instance_point(existing)
                target_point = DB.XYZ(row.target_point[0], row.target_point[1], row.target_point[2])
                DB.ElementTransformUtils.MoveElement(doc, existing.Id, target_point - current_point)
                moved += 1
                debug_log("Moved outlet [{}] to {}".format(row.existing_instance_id, row.target_point))
            except Exception as e:
                debug_log("Failed to move outlet [{}]: {}".format(row.existing_instance_id, e))
                failed.append(row.existing_instance_id)
        t.Commit()
    except Exception:
        t.RollBack()
        raise

    lines = ["Placed {} | Moved {} | Kept {}".format(placed, moved, kept)]
    if failed:
        lines.append("Failed on {} item(s), see output for detail.".format(len(failed)))
    NOTIFICATION.messenger(main_text="\n".join(lines))
    debug_log(" | ".join(lines))
    log_path = save_run_log()
    if log_path:
        print("Debug log saved to: {}".format(log_path))
    return " | ".join(lines)


class OutletConflictReviewWindow(WPFWindow):
    """Modeless per-row review for outlets that already sit near a marker.

    Follows CLAUDE.md's "Modeless WPF DataGrid forms" checklist: rows
    (OutletConflictRow) hold only plain ints/strings/tuples, never a live
    FamilyInstance; Revit API calls (zoom, apply) are routed through
    ExternalEvent and re-fetch elements by id; the grid's ItemsSource is
    reassigned rather than refreshed in place; WPF control types are
    duck-typed, never imported by name.
    """
    _instance = None

    def pre_actions(self):
        self.zoom_handler = SimpleEventHandler(zoom_to_instance)
        self.ext_event_zoom = ExternalEvent.Create(self.zoom_handler)
        self.apply_handler = SimpleEventHandler(apply_marker_outlets)
        self.ext_event_apply = ExternalEvent.Create(self.apply_handler)

    def __init__(self, to_place, conflict_rows, furniture_label):
        self.pre_actions()
        WPFWindow.__init__(self, "OutletConflictReview.xaml")
        self.Title = "EnneadTab Outlet Marker Review"
        self._form_closed = False
        self._navigating = False
        self.current_index = -1
        self._to_place = to_place
        self._furniture_label = furniture_label
        OutletConflictReviewWindow._instance = self
        self.Closed += self._on_closed

        # Populate the combo column's options via Columns[] rather than an x:Name
        # attribute: pyRevit's WPFWindow does not reliably expose x:Name on a
        # DataGridComboBoxColumn (same caveat as batch_fix_family_name).
        self.main_grid.Columns[4].ItemsSource = ACTION_OPTIONS

        self.main_grid.ItemsSource = conflict_rows
        self.count_text.Text = "{} conflict(s) to review. {} new outlet(s) ready to place on Apply.".format(
            len(conflict_rows), len(to_place))
        self.update_nav_label()
        self.Show()
        if conflict_rows:
            self.go_to_index(0)

    def _on_closed(self, sender, e):
        self._form_closed = True
        if getattr(OutletConflictReviewWindow, "_instance", None) is self:
            OutletConflictReviewWindow._instance = None

    def update_nav_label(self):
        rows = self.main_grid.ItemsSource or []
        if not rows:
            self.nav_text.Text = "No conflicts"
            return
        self.nav_text.Text = "{} / {}".format(self.current_index + 1, len(rows))

    def go_to_index(self, index):
        rows = list(self.main_grid.ItemsSource or [])
        if not rows:
            return
        index = max(0, min(index, len(rows) - 1))
        self.current_index = index
        row = rows[index]
        self._navigating = True
        try:
            self.main_grid.SelectedIndex = index
            self.main_grid.ScrollIntoView(row)
        finally:
            self._navigating = False
        self.update_nav_label()
        self.zoom_handler.kwargs = (row.existing_instance_id,)
        self.ext_event_zoom.Raise()
        err = self.zoom_handler.OUT
        if err:
            self.debug_textbox.Text = err

    @ERROR_HANDLE.try_catch_error()
    def grid_selection_changed(self, sender, e):
        if self._navigating:
            return
        index = self.main_grid.SelectedIndex
        if index < 0:
            return
        self.go_to_index(index)

    @ERROR_HANDLE.try_catch_error()
    def previous_click(self, sender, e):
        self.go_to_index(self.current_index - 1)

    @ERROR_HANDLE.try_catch_error()
    def next_click(self, sender, e):
        self.go_to_index(self.current_index + 1)

    @ERROR_HANDLE.try_catch_error()
    def zoom_row_click(self, sender, e):
        # Duck-typed: sender.Tag is the bound OutletConflictRow (Tag="{Binding}" in
        # XAML), never a live Revit element (see class docstring).
        row = getattr(sender, "Tag", None)
        if row is None:
            return
        rows = list(self.main_grid.ItemsSource or [])
        try:
            index = rows.index(row)
        except ValueError:
            index = self.current_index
        self.go_to_index(index)

    @ERROR_HANDLE.try_catch_error()
    def apply_click(self, sender, e):
        rows = list(self.main_grid.ItemsSource or [])
        self.apply_handler.kwargs = (self._to_place, rows)
        self.ext_event_apply.Raise()
        res = self.apply_handler.OUT
        self.debug_textbox.Text = res or "Applied."

    def close_Click(self, sender, e):
        self._form_closed = True
        try:
            self.Close()
        except Exception as ex:
            print("close failed: {}".format(ex))

    def mouse_down_main_panel(self, sender, args):
        try:
            sender.DragMove()
        except Exception:
            pass


def resolve_picked_element(doc, ref):
    """Resolve a PickObject Reference to the element it points at, whether picked
    directly in `doc` or drilled (Tab) into a linked model instance.

    Picking through into a link is standard PickObject(ObjectType.Element,...)
    behavior: `ref.ElementId` is then the RevitLinkInstance's id in `doc`, and
    `ref.LinkedElementId` is the element's id inside the link's own document.

    Returns:
        tuple (DB.Element element, DB.Document element_doc, DB.Transform link_transform)
        `link_transform` is None for an element picked directly in `doc`.
    """
    picked = doc.GetElement(ref.ElementId)
    if isinstance(picked, DB.RevitLinkInstance) and ref.LinkedElementId != DB.ElementId.InvalidElementId:
        link_doc = picked.GetLinkDocument()
        element = link_doc.GetElement(ref.LinkedElementId) if link_doc else None
        return element, link_doc, picked.GetTotalTransform()
    return picked, doc, None


def resolve_picked_furniture(doc, ref):
    """Resolve a pick to its top-level furniture instance, whether the user clicked
    the furniture body itself or one of its nested markers.

    Walks up through SuperComponent so either click works: a picked marker's
    SuperComponent is the furniture instance directly; a picked furniture instance's
    SuperComponent is already None, so the loop is a no-op for it.

    Returns:
        tuple (DB.Element furniture, DB.Document element_doc, DB.Transform link_transform)
        `link_transform` is None for an element picked directly in `doc`.
    """
    element, element_doc, link_transform = resolve_picked_element(doc, ref)
    if element is None:
        return None, None, None
    furniture = element
    while getattr(furniture, "SuperComponent", None) is not None:
        furniture = furniture.SuperComponent
    return furniture, element_doc, link_transform


def place_from_markers(doc):
    try:
        # No ISelectionFilter: any category is allowed (furniture or one of its nested
        # markers). PickObject's 3-arg overload throws "Value cannot be null, Parameter
        # name: pSelFilter" if passed None for the filter -- Revit does NOT treat a null
        # filter as "allow anything" the way it does for other API surfaces -- so the
        # no-filter 2-arg overload must be used instead, not ObjectType.Element, None, prompt.
        ref = UIDOC.Selection.PickObject(
            ObjectType.Element,
            "Pick any furniture instance or one of its markers, to select which "
            "document to search (Tab to pick one inside a linked model)")
    except OperationCanceledException:
        return
    furniture_example, marker_doc, link_transform = resolve_picked_furniture(doc, ref)
    if furniture_example is None or marker_doc is None:
        NOTIFICATION.messenger("Could not resolve the picked element (broken or unloaded link?).")
        return

    qualified_names = discover_qualified_furniture_family_names(marker_doc)
    if not qualified_names:
        NOTIFICATION.messenger(
            "No furniture family in [{}] carries a {} marker.".format(marker_doc.Title, PARA_MAP_PARAMETER_NAME))
        return

    selected_names = forms.SelectFromList.show(
        qualified_names,
        multiselect=True,
        title="Select Furniture Families To Process",
        button_name="Process Selected")
    if not selected_names:
        return
    furniture_label = " / ".join(selected_names)

    view3d = get_any_3d_view(doc)
    if view3d is None:
        NOTIFICATION.messenger("No 3D view available and none could be created; cannot ray-cast to a host face.")
        return

    start_run_log()
    try:
        symbol_cache = {}
        resolved, unresolved = resolve_marker_targets(
            doc, selected_names, view3d, symbol_cache, marker_doc=marker_doc, link_transform=link_transform)
        marker_doc_label = "[{}] ".format(marker_doc.Title) if link_transform is not None else ""
        for marker, reason in unresolved:
            print("Marker {}{}: {}".format(marker_doc_label, marker.Id, reason))
        if not resolved:
            NOTIFICATION.messenger(
                "Found {} marker(s) across [{}], but none resolved to a placeable outlet.".format(
                    len(unresolved), furniture_label))
            return

        existing_instances_cache = {}  # (family_name, type_name) -> list of DB.FamilyInstance

        def get_existing_instances(family, family_type):
            key = (family.Name, type_name_of(family_type))
            if key not in existing_instances_cache:
                existing_instances_cache[key] = REVIT_FAMILY.get_family_instances_by_family_name_and_type_name(
                    family.Name, type_name_of(family_type), doc=doc, editable_only=True)
            return existing_instances_cache[key]

        to_place = []        # OutletPlacementTarget - no existing outlet nearby
        already_placed = []  # existing instance, no action needed
        conflict_rows = []   # OutletConflictRow - needs a per-row review decision
        for marker, host, face, hit_point, stable_ref, family, family_type in resolved:
            existing_instances = get_existing_instances(family, family_type)
            nearby, distance = find_nearby_instance(hit_point, existing_instances, EXISTING_OUTLET_SEARCH_RADIUS)
            point_tuple = (hit_point.X, hit_point.Y, hit_point.Z)
            type_name = type_name_of(family_type)
            if nearby is None:
                use_stable_ref = stable_ref if family.FamilyPlacementType == DB.FamilyPlacementType.WorkPlaneBased else None
                to_place.append(OutletPlacementTarget(
                    element_int_id(host), point_tuple, family.Name, type_name, use_stable_ref))
            elif distance <= EXISTING_OUTLET_SAME_SPOT_TOLERANCE:
                already_placed.append(nearby)
            else:
                conflict_rows.append(OutletConflictRow(
                    element_int_id(nearby), get_level_name(nearby, doc),
                    family.Name, type_name, distance, point_tuple))

        if not conflict_rows:
            # Nothing to review case by case: place everything right away, same as
            # the direct Place mode.
            res = apply_marker_outlets(to_place, [])
            lines = ["Furniture: [{}]".format(furniture_label), res]
            if already_placed:
                lines.append("{} outlet(s) already sat exactly on their marker, left untouched".format(len(already_placed)))
            if unresolved:
                lines.append("{} marker(s) could not be placed, see output for detail".format(len(unresolved)))
            NOTIFICATION.messenger(main_text="\n".join(lines))
            return

        existing_window = getattr(OutletConflictReviewWindow, "_instance", None)
        if existing_window is not None and not getattr(existing_window, "_form_closed", True):
            NOTIFICATION.messenger("An outlet review window is already open; finish or close it first.")
            try:
                existing_window.Activate()
            except Exception:
                pass
            return

        lines = [
            "{} outlet(s) already sit near a marker; opening the review grid.".format(len(conflict_rows)),
            "{} new outlet(s) will be placed once you Apply.".format(len(to_place)),
        ]
        if already_placed:
            lines.append("{} outlet(s) already sat exactly on their marker, left untouched.".format(len(already_placed)))
        if unresolved:
            lines.append("{} marker(s) could not be placed, see output for detail.".format(len(unresolved)))
        NOTIFICATION.messenger(" ".join(lines))
        OutletConflictReviewWindow(to_place, conflict_rows, furniture_label)
    finally:
        # apply_marker_outlets() re-saves the same file after Apply (which fires
        # later, from a separate ExternalEvent once the review window closes) -- this
        # save just guarantees a log exists even if the run stops before that, e.g.
        # nothing resolved, or the review window opened and was never applied.
        log_path = save_run_log()
        if log_path:
            print("Debug log saved to: {}".format(log_path))


def place_outlets(doc):
    family = REVIT_SELECTION.pick_family(doc, include_2D=False, include_3D=True)
    if not family:
        return
    family_symbol = REVIT_SELECTION.pick_type(family)
    if not family_symbol:
        return

    placement_type = family.FamilyPlacementType
    if placement_type == DB.FamilyPlacementType.WorkPlaneBased:
        picks = pick_faces_on_walls_and_floors()
        if not picks:
            return
        t = DB.Transaction(doc, "Place Electrical Outlet - {}".format(family.Name))
        t.Start()
        try:
            placed, failed = place_face_based(doc, family_symbol, picks)
            t.Commit()
        except Exception:
            t.RollBack()
            raise
    elif placement_type == DB.FamilyPlacementType.OneLevelBasedHosted:
        picks = pick_points_on_walls()
        if not picks:
            return
        t = DB.Transaction(doc, "Place Electrical Outlet - {}".format(family.Name))
        t.Start()
        try:
            placed, failed = place_wall_hosted(doc, family_symbol, picks)
            t.Commit()
        except Exception:
            t.RollBack()
            raise
    else:
        NOTIFICATION.messenger(
            "[{}] is neither a face-based nor a wall-hosted family. "
            "Use a Face Based or Wall Based outlet family with this tool.".format(family.Name))
        return

    lines = ["Placed {} outlet(s) of [{}] - [{}]".format(len(placed), family.Name, type_name_of(family_symbol))]
    if failed:
        lines.append("Failed on {} host(s), see output for detail.".format(len(failed)))
    NOTIFICATION.messenger(main_text="\n".join(lines))


def update_outlet_type(doc):
    family = REVIT_SELECTION.pick_family(doc, include_2D=False, include_3D=True)
    if not family:
        return
    old_type = REVIT_SELECTION.pick_type(family)
    if not old_type:
        return

    instances = REVIT_FAMILY.get_family_instances_by_family_name_and_type_name(
        family.Name, type_name_of(old_type), doc=doc, editable_only=True)
    if not instances:
        NOTIFICATION.messenger(
            "No editable instance of [{}] - [{}] found in the model.".format(family.Name, type_name_of(old_type)))
        return

    new_type = REVIT_SELECTION.pick_type(family)
    if not new_type:
        return
    if new_type.Id == old_type.Id:
        NOTIFICATION.messenger("New type is the same as the current type, nothing to update.")
        return

    confirm = REVIT_FORMS.dialogue(
        main_text="Update Electrical Outlet Type",
        sub_text="Change {} instance(s) of [{}] from [{}] to [{}]?".format(
            len(instances), family.Name, type_name_of(old_type), type_name_of(new_type)),
        options=["Run", "Cancel"],
        icon="warning")
    if confirm != "Run":
        return

    updated = []
    failed = []
    t = DB.Transaction(doc, "Update Electrical Outlet Type - {}".format(family.Name))
    t.Start()
    try:
        for instance in instances:
            try:
                instance.Symbol = new_type
                updated.append(instance.Id)
            except Exception as e:
                ERROR_HANDLE.print_note("Failed to update outlet [{}]: {}".format(instance.Id, e))
                failed.append(instance.Id)
        t.Commit()
    except Exception:
        t.RollBack()
        raise

    lines = ["Updated {} outlet(s) to [{}]".format(len(updated), type_name_of(new_type))]
    if failed:
        lines.append("Failed on {} instance(s), see output for detail.".format(len(failed)))
    NOTIFICATION.messenger(main_text="\n".join(lines))


@LOG.log(__file__, __title__)
@ERROR_HANDLE.try_catch_error()
def main(doc):
    mode = REVIT_FORMS.dialogue(
        main_text="MetroTech Electrical Outlet",
        sub_text="Place new outlet instances, place them from a furniture family's "
                 "nested position marker, or update the type of outlets already in the model.",
        options=["Place", "Place From Marker", "Update Type", "Cancel"])
    if mode == "Place":
        place_outlets(doc)
    elif mode == "Place From Marker":
        place_from_markers(doc)
    elif mode == "Update Type":
        update_outlet_type(doc)


################## main code below #####################
if __name__ == "__main__":
    main(DOC)
