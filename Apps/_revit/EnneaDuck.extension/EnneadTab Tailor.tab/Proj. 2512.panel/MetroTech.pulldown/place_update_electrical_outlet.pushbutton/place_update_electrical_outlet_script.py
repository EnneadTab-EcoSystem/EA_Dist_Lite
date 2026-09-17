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
- No furniture family name is ever hardcoded, and nothing needs to be picked: this
  automatically scans the current model AND every loaded link for any furniture
  family that carries a `_para_map` marker, then lets you multi-select which of
  those discovered families to process, so you can run surgically on just one
  furniture type after a model fix instead of always reprocessing everything
- Within each selected furniture instance, every nested marker fans rays outward from
  its corrected point to the nearest wall/floor (the marker carries position only, no
  dependable facing rotation to aim a single ray), and creates or repositions the
  matching outlet in the current model automatically -- no per-conflict review step
- Each marker instance names its own outlet family/type and mount height via its
  `_para_map` JSON parameter, so markers nested in the same furniture instance can
  each place a different outlet at a different height; the outlet's Z always comes
  from its host furniture instance's level plus that mount height, never the
  marker's raw position (markers are modeled above the furniture body on purpose, to
  stay visible/pickable -- see the comment above PARA_MAP_TEMPLATE)
- Every "Place From Marker" run writes a timestamped debug log to the local dump
  folder (path printed at the end of the run) recording what was found, resolved,
  skipped, and placed -- open it when a run gets stuck to see exactly what happened.
  If many markers of the SAME furniture family in a row fail for the identical
  reason, that family's remaining markers are skipped (other selected families are
  unaffected) instead of grinding through a doomed setup; a per-marker error (e.g. a
  hand-edited _para_map typo) never aborts more than that one marker
- An outlet that already exists exactly on a marker's target point is left untouched;
  one that exists nearby but off-target is moved there automatically (never
  retyped -- it was only found because it already matched the target family/type);
  one owned by another user in a workshared model is left alone either way, and
  never duplicated
- Existing outlet instances of a type can be swapped to a different type in one pass

Usage:
1. Run the button and choose Place, Place From Marker, or Update Type
2. Place: pick a family and type, then click faces/walls until you press Escape
3. Place From Marker: multi-select which discovered furniture families to process
   (found automatically across the current model and every loaded link -- nothing to
   pick first). Each nested marker's own `_para_map` names the outlet family/type and
   mount height; outlets are created or repositioned automatically, with a summary
   and a debug log path reported at the end
4. Update Type: pick the family, current type, new type, then confirm"""
__title__ = "Place/Update\nElectrical Outlet"

import datetime
import json
import math

import proDUCKtion  # pyright: ignore
proDUCKtion.validify()

from Autodesk.Revit import DB  # pyright: ignore
from Autodesk.Revit.UI.Selection import ObjectType, ISelectionFilter  # pyright: ignore
from Autodesk.Revit.Exceptions import OperationCanceledException  # pyright: ignore
from System.Collections.Generic import List  # pyright: ignore
from pyrevit import forms

from EnneadTab import ERROR_HANDLE, FOLDER, LOG, NOTIFICATION
from EnneadTab.REVIT import REVIT_APPLICATION, REVIT_SELECTION, REVIT_FORMS, REVIT_FAMILY

from outlet_conflict_row import OutletPlacementTarget

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
# SuperComponent), across the current model AND every loaded link (see
# get_search_scopes). This survives new furniture families getting markers added
# later with zero code changes, and place_from_markers lets the user multi-select a
# subset of the discovered names for a surgical run (e.g. re-running on just one
# furniture type after a model fix) instead of always processing every family.

# If this many markers of the SAME furniture family in a row fail with the EXACT SAME
# reason, resolve_marker_targets stops processing THAT family's remaining markers
# early instead of grinding through all of them: an identical repeated reason (e.g.
# "host furniture has no level") signals a systemic modeling/setup problem for that
# family, not a string of unrelated one-off marker issues, so nothing is gained by
# continuing -- fail fast, fix the root cause, rerun. Other selected furniture
# families are unaffected (the streak is scoped per family, not global).
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
    else:
        debug_log(
            "Marker [{}]'s {} parsed as valid JSON but is not an object ({}: {!r}), ignoring.".format(
                marker.Id, PARA_MAP_PARAMETER_NAME, type(parsed).__name__, parsed))
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
    "Place From Marker" run. Call once, at the start of that run.
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

    Quietly no-ops if start_run_log() was never called or nothing was logged.

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
    """Return an existing non-template 3D view, or create one.

    A view is required by DB.ReferenceIntersector for the marker-driven raycast; a
    plan/section view cannot be used for it. The created view is NOT deleted after
    use -- it becomes a permanent addition to the project (there's no reliable way to
    "borrow" a view for a single ray-cast and clean it back up mid-transaction).
    Creating a view is a document change and must run inside an open transaction, so
    this opens its own single-purpose one only when the fallback is actually needed.
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
    t = DB.Transaction(doc, "Create 3D View For Outlet Ray-Cast")
    t.Start()
    try:
        view3d = DB.View3D.CreateIsometric(doc, view_family_type.Id)
        t.Commit()
        return view3d
    except Exception:
        t.RollBack()
        raise


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
    rebuilt per ray. Reusing one instance here is a straight ~18x cut to
    intersector-construction overhead versus rebuilding it per ray
    (MARKER_RAYCAST_FAN_COUNT + 2 rays per marker).
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


def find_nearest_host_face(doc, intersector, point, required_host_type=None):
    """Cast a fan of rays outward from `point` and return the nearest wall/floor hit.

    The marker only carries a position, not a dependable facing rotation, so the
    direction to the host wall/floor cannot be read off its orientation the way a
    single trusted axis would. Trying every direction in the fan and keeping the
    globally nearest hit finds the host regardless of which way the marker sits.

    `intersector` is built once per run by build_wall_floor_intersector and passed
    through here -- see that function's docstring for why it must not be rebuilt per
    ray or per marker.

    `required_host_type`, if given (e.g. DB.Wall), restricts which hits count: a hit
    on a host that is NOT an instance of this type is ignored even if it is the
    nearest ray overall. This matters for a wall-hosted (OneLevelBasedHosted) outlet,
    whose family API can only host on a wall -- without this filter, a floor that
    happens to be marginally closer than the nearest wall would win the fan-cast, and
    placement would then silently fail downstream with no host type to attach to.

    Returns:
        tuple (DB.Element host, DB.Face face, DB.XYZ hit_point, str stable_ref), or
        (None, None, None, None) when nothing matching is hit within
        MARKER_RAYCAST_MAX_DISTANCE in any direction.
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
        if required_host_type is not None and not isinstance(host, required_host_type):
            continue
        distance = point.DistanceTo(hit_point)
        if best_distance is None or distance < best_distance:
            best = (host, face, hit_point, stable_ref)
            best_distance = distance
    if best is None:
        debug_log(
            "Fan-cast from ({}, {}, {}): 0 of {} rays hit a{} within {} ft".format(
                round(point.X, 2), round(point.Y, 2), round(point.Z, 2), len(directions),
                " matching" if required_host_type is not None else " wall/floor",
                MARKER_RAYCAST_MAX_DISTANCE))
        return None, None, None, None
    host, face, hit_point, stable_ref = best
    debug_log(
        "Fan-cast from ({}, {}, {}): {} of {} rays hit; nearest host [{}] at {} ft".format(
            round(point.X, 2), round(point.Y, 2), round(point.Z, 2),
            hit_count, len(directions), host.Id, round(best_distance, 3)))
    return best


def get_search_scopes(doc):
    """Return every (search_doc, link_transform) scope to search for furniture/markers:
    the host document itself (link_transform=None), plus one entry per loaded,
    resolvable RevitLinkInstance PLACEMENT in the host document -- not one per unique
    linked file, since the same link file placed more than once (e.g. a repeated
    site/context link) needs its own transform applied to each placement separately.
    An unloaded link (GetLinkDocument() returns None) is skipped.
    """
    scopes = [(doc, None)]
    link_instances = DB.FilteredElementCollector(doc).OfClass(DB.RevitLinkInstance).WhereElementIsNotElementType().ToElements()
    for link_instance in link_instances:
        link_doc = link_instance.GetLinkDocument()
        if link_doc is None:
            continue
        scopes.append((link_doc, link_instance.GetTotalTransform()))
    return scopes


def discover_qualified_furniture_family_names(doc):
    """Scan `doc` for every family instance carrying a _para_map parameter (a marker,
    by convention), walk each one up to its host furniture instance via
    SuperComponent, and return the distinct furniture family names found.

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
        # Walk all the way to the TOP-level host: a marker nested more than one
        # FamilyInstance level deep (furniture -> sub-assembly -> marker) must still
        # report the true top-level furniture family, not an intermediate one.
        while getattr(furniture, "SuperComponent", None) is not None:
            furniture = furniture.SuperComponent
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


def build_para_map_markers_by_furniture_id(doc):
    """One project-wide pass over `doc`: group every _para_map-carrying instance by
    its top-level host furniture instance's ElementId (walking SuperComponent all the
    way up, same as discover_qualified_furniture_family_names).

    Returns:
        dict {furniture_id (int): [marker, ...]}

    Deliberately a project-wide collector + SuperComponent walk-up, NOT
    host_instance.GetDependentElements() per furniture instance. This matches the
    library's own established pattern for Shared nested families --
    REVIT_FAMILY.get_shared_nested_instances_by_family_name's docstring explicitly
    says a Shared nested family "registers as its own first-class element... found
    directly with a project-wide collector INSTEAD OF walking every host's
    dependents." A marker needs to be independently selectable/editable in the model
    (to hand-edit its _para_map, see that parameter's own comment above), which is
    exactly what marking a nested family Shared is for -- so this file never assumes
    GetDependentElements reliably surfaces it, and does one full-document scan per
    search scope instead (cheap relative to the ray-casting this run already does).
    """
    instances = DB.FilteredElementCollector(doc).OfClass(DB.FamilyInstance).WhereElementIsNotElementType().ToElements()
    by_furniture_id = {}
    for instance in instances:
        if instance.LookupParameter(PARA_MAP_PARAMETER_NAME) is None:
            continue
        top = instance
        while getattr(top, "SuperComponent", None) is not None:
            top = top.SuperComponent
        if top.Id == instance.Id:
            continue  # not nested inside anything -- not a marker under this convention
        by_furniture_id.setdefault(element_int_id(top), []).append(instance)
    return by_furniture_id


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


def _resolve_one_marker(doc, scope_doc, link_transform, furniture, furniture_level, marker, intersector, symbol_cache):
    """Resolve one marker to its outlet symbol and host face, or the reason it can't be.

    Isolated into its own function so resolve_marker_targets can wrap a single call in
    try/except: a per-marker error (e.g. a hand-edited _para_map with a non-numeric
    mount_height) must fail that ONE marker, never abort the whole run.

    Returns:
        tuple (reason, host, face, hit_point, stable_ref, family, family_type).
        `reason` is None on success; every Revit-object field is None when `reason`
        is set.
    """
    para_map = get_marker_para_map(marker)
    if any(value is not None for value in para_map.values()):
        debug_log("Marker [{}] {}: {}".format(marker.Id, PARA_MAP_PARAMETER_NAME, para_map))

    outlet_family_name = para_map.get("family_name")
    outlet_type_name = para_map.get("type_name")
    mount_height = para_map.get("mount_height")
    if not outlet_family_name or not outlet_type_name or mount_height is None:
        return ("{} needs family_name, type_name, and mount_height all set".format(PARA_MAP_PARAMETER_NAME),
                None, None, None, None, None, None)

    family, family_type = resolve_outlet_symbol(doc, outlet_family_name, outlet_type_name, symbol_cache)
    if not family or not family_type:
        return ("outlet [{}] - [{}] is not loaded".format(outlet_family_name, outlet_type_name),
                None, None, None, None, None, None)

    if family.FamilyPlacementType not in (DB.FamilyPlacementType.WorkPlaneBased, DB.FamilyPlacementType.OneLevelBasedHosted):
        return ("outlet [{}] is neither face-based nor wall-hosted".format(outlet_family_name),
                None, None, None, None, None, None)

    if furniture_level is None:
        return ("host furniture [{}] has no level".format(furniture.Id),
                None, None, None, None, None, None)

    local_point, _orientation = REVIT_FAMILY.get_nested_instance_placement(marker)
    if local_point is None:
        return ("no location available", None, None, None, None, None, None)

    corrected_point = DB.XYZ(local_point.X, local_point.Y, furniture_level.Elevation + mount_height)
    if link_transform is not None:
        corrected_point = link_transform.OfPoint(corrected_point)
    debug_log(
        "Marker [{}]: furniture [{}] level [{}] (elev {}) + mount_height {} -> corrected point {}".format(
            marker.Id, furniture.Id, furniture_level.Name, round(furniture_level.Elevation, 2),
            mount_height, (round(corrected_point.X, 2), round(corrected_point.Y, 2), round(corrected_point.Z, 2))))

    required_host_type = DB.Wall if family.FamilyPlacementType == DB.FamilyPlacementType.OneLevelBasedHosted else None
    host, face, hit_point, stable_ref = find_nearest_host_face(
        doc, intersector, corrected_point, required_host_type=required_host_type)
    if host is None:
        needed = "wall" if required_host_type is not None else "wall/floor"
        return ("no {} within {} ft in any direction".format(needed, MARKER_RAYCAST_MAX_DISTANCE),
                None, None, None, None, None, None)

    return (None, host, face, hit_point, stable_ref, family, family_type)


def resolve_marker_targets(doc, furniture_family_names, view3d, symbol_cache, scopes):
    """Find every instance of `furniture_family_names` across every search scope (the
    host document plus every loaded link -- see get_search_scopes), and within each
    one, every nested marker (build_para_map_markers_by_furniture_id). Each marker's own _para_map
    names the outlet family/type and mount height to place there, so this also
    resolves that outlet symbol and fan-casts the marker's corrected point to its
    host face (see _resolve_one_marker for the per-marker logic).

    A furniture instance can nest more than one marker (each independently naming its
    own outlet/height), so the outlet's final Z always comes from the FURNITURE
    instance's own level plus that marker's _para_map mount_height -- never the
    marker's raw Z and never the ray-cast hit's Z. Only the marker's X/Y are taken
    as-is. That corrected point is what the fan is cast FROM, not a value applied
    after the cast.

    `scopes` is a list of (search_doc, link_transform) pairs from get_search_scopes;
    the corrected point is built in each entry's own `search_doc` local space (X/Y
    raw, Z corrected) and only mapped into host-doc space via `link_transform` when
    it is not None, since the ray-cast and every downstream placement always target
    the CURRENT (host) document's walls/floors -- never a link's.
    `symbol_cache` is a plain dict the caller owns, passed straight through to
    resolve_outlet_symbol so repeated (family_name, type_name) pairs are only looked
    up once for the whole run.

    Fails fast, scoped PER FURNITURE FAMILY: if CONSECUTIVE_UNRESOLVED_ABORT_THRESHOLD
    markers of the SAME selected furniture family in a row hit the exact same
    unresolved reason, that family's remaining markers are skipped -- a repeated
    identical reason is a systemic setup problem for that family, not independent
    one-off marker issues, so continuing wastes time without finding anything new.
    Other selected families are entirely unaffected (each gets its own fresh streak).

    Returns:
        tuple (resolved, unresolved):
          resolved   -- list of (marker, host, face, hit_point, stable_ref, family, family_type)
          unresolved -- list of (marker, reason) for markers that can't be placed
    """
    entries_by_family = {}
    for family_name in furniture_family_names:
        entries_by_family[family_name] = []

    for scope_doc, link_transform in scopes:
        furniture_instances = get_furniture_instances(scope_doc, furniture_family_names)
        markers_by_furniture_id = build_para_map_markers_by_furniture_id(scope_doc)
        debug_log("Found {} furniture instance(s) of {} in [{}]".format(
            len(furniture_instances), furniture_family_names, scope_doc.Title))
        for furniture in furniture_instances:
            furniture_level = get_instance_level(scope_doc, furniture)
            markers = markers_by_furniture_id.get(element_int_id(furniture), [])
            furniture_family_name = REVIT_FAMILY.get_family_name(furniture)
            debug_log("Furniture [{}] ({}) in [{}]: {} marker(s), level [{}]".format(
                furniture.Id, furniture_family_name, scope_doc.Title, len(markers),
                furniture_level.Name if furniture_level else "NONE"))
            entries_by_family.setdefault(furniture_family_name, [])
            for marker in markers:
                entries_by_family[furniture_family_name].append(
                    (furniture, furniture_level, marker, scope_doc, link_transform))

    intersector = build_wall_floor_intersector(view3d)

    resolved = []
    unresolved = []

    for family_name in furniture_family_names:
        entries = entries_by_family.get(family_name, [])
        streak_reason = None
        streak_count = 0

        for index, (furniture, furniture_level, marker, scope_doc, link_transform) in enumerate(entries):
            try:
                reason, host, face, hit_point, stable_ref, family, family_type = _resolve_one_marker(
                    doc, scope_doc, link_transform, furniture, furniture_level, marker, intersector, symbol_cache)
            except Exception as e:
                reason = "internal error: {}".format(e)
                host = face = hit_point = stable_ref = family = family_type = None

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
                remaining = len(entries) - index - 1
                debug_log(
                    "Aborting furniture family [{}] early: {} consecutive markers failed with the same reason "
                    "[{}] -- likely a systemic model/family setup issue for this family, not independent "
                    "per-marker problems. Skipping its remaining {} marker(s); other selected families are "
                    "unaffected. Fix the root cause and rerun.".format(family_name, streak_count, reason, remaining))
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


def apply_marker_outlets(to_create, to_update):
    """Create missing outlets and reposition already-correct-type outlets that sit
    near a marker but not exactly on it, in one transaction.

    Called directly and synchronously from place_from_markers, which is itself
    already running in Revit's API context (the button's own entry point) -- there is
    no modeless review step in this flow, so no ExternalEvent is needed.

    `to_create` items each name their own outlet family/type (read from their
    marker's _para_map -- different markers can name different outlets), resolved
    here by name. `to_update` items are (existing_instance_id, target_point) pairs:
    the existing instance is ALREADY the correct family/type -- that is how it was
    found, see get_existing_instances in place_from_markers -- so only a move is ever
    needed here, never a retype.
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

    created = 0
    moved = 0
    failed = []
    t = DB.Transaction(doc, "Place/Update Electrical Outlet From Marker")
    t.Start()
    try:
        for item in to_create:
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
                    debug_log(
                        "Cannot place outlet [{}] - [{}] on host [{}]: no face reference and host is not a "
                        "wall (host type: {}).".format(
                            item.family_name, item.type_name, item.host_id, type(host).__name__))
                if instance:
                    created += 1
                    debug_log("Placed outlet [{}] - [{}]/[{}] on host [{}] at {}".format(
                        instance.Id, item.family_name, item.type_name, item.host_id, item.point))
                else:
                    failed.append(item.host_id)
            except Exception as e:
                debug_log("Failed to place outlet on host [{}]: {}".format(item.host_id, e))
                failed.append(item.host_id)

        for existing_instance_id, target_point_tuple in to_update:
            try:
                existing = doc.GetElement(DB.ElementId(existing_instance_id))
                if existing is None:
                    failed.append(existing_instance_id)
                    continue
                current_point = get_instance_point(existing)
                target_point = DB.XYZ(target_point_tuple[0], target_point_tuple[1], target_point_tuple[2])
                DB.ElementTransformUtils.MoveElement(doc, existing.Id, target_point - current_point)
                moved += 1
                debug_log("Moved outlet [{}] to {}".format(existing_instance_id, target_point_tuple))
            except Exception as e:
                debug_log("Failed to move outlet [{}]: {}".format(existing_instance_id, e))
                failed.append(existing_instance_id)
        t.Commit()
    except Exception:
        t.RollBack()
        raise

    lines = ["Placed {} | Moved {}".format(created, moved)]
    if failed:
        lines.append("Failed on {} item(s), see output for detail.".format(len(failed)))
    result = " | ".join(lines)
    debug_log(result)
    return result


def place_from_markers(doc):
    scopes = get_search_scopes(doc)

    qualified_names = set()
    for scope_doc, _link_transform in scopes:
        qualified_names.update(discover_qualified_furniture_family_names(scope_doc))
    qualified_names = sorted(qualified_names)
    if not qualified_names:
        NOTIFICATION.messenger(
            "No furniture family in this model or its links carries a {} marker.".format(PARA_MAP_PARAMETER_NAME))
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
        resolved, unresolved = resolve_marker_targets(doc, selected_names, view3d, symbol_cache, scopes)
        for marker, reason in unresolved:
            print("Marker [{}]: {}".format(marker.Id, reason))
        if not resolved:
            NOTIFICATION.messenger(
                "Found {} marker(s) across [{}], but none resolved to a placeable outlet.".format(
                    len(unresolved), furniture_label))
            return

        existing_instances_cache = {}  # (family_name, type_name) -> list of DB.FamilyInstance

        def get_existing_instances(family, family_type):
            key = (family.Name, type_name_of(family_type))
            if key not in existing_instances_cache:
                # editable_only is intentionally NOT passed (defaults False): an
                # outlet owned by another workshared user must still be found here so
                # this marker is never treated as empty and given a duplicate right
                # on top of it. Ownership is only checked separately, below, when
                # actually deciding whether to move one.
                existing_instances_cache[key] = REVIT_FAMILY.get_family_instances_by_family_name_and_type_name(
                    family.Name, type_name_of(family_type), doc=doc)
            return existing_instances_cache[key]

        to_create = []        # OutletPlacementTarget - no existing outlet nearby
        to_update = []        # (existing_instance_id, target_point) - move to target
        already_placed = []   # existing instance, no action needed
        skipped_foreign = []  # existing instance nearby but owned by another user
        for marker, host, face, hit_point, stable_ref, family, family_type in resolved:
            existing_instances = get_existing_instances(family, family_type)
            nearby, distance = find_nearby_instance(hit_point, existing_instances, EXISTING_OUTLET_SEARCH_RADIUS)
            point_tuple = (hit_point.X, hit_point.Y, hit_point.Z)
            type_name = type_name_of(family_type)
            if nearby is None:
                use_stable_ref = stable_ref if family.FamilyPlacementType == DB.FamilyPlacementType.WorkPlaneBased else None
                to_create.append(OutletPlacementTarget(
                    element_int_id(host), point_tuple, family.Name, type_name, use_stable_ref))
            elif distance <= EXISTING_OUTLET_SAME_SPOT_TOLERANCE:
                already_placed.append(nearby)
            elif REVIT_SELECTION.is_changable(nearby):
                to_update.append((element_int_id(nearby), point_tuple))
            else:
                skipped_foreign.append(nearby)
                debug_log(
                    "Outlet near marker [{}] is owned by another user; leaving it in place, not "
                    "creating a duplicate.".format(marker.Id))

        result = apply_marker_outlets(to_create, to_update)
        lines = ["Furniture: [{}]".format(furniture_label), result]
        if already_placed:
            lines.append("{} outlet(s) already sat exactly on their marker, left untouched".format(len(already_placed)))
        if skipped_foreign:
            lines.append(
                "{} outlet(s) near a marker are owned by another user, left untouched".format(len(skipped_foreign)))
        if unresolved:
            lines.append("{} marker(s) could not be placed, see output for detail".format(len(unresolved)))
        NOTIFICATION.messenger(main_text="\n".join(lines))
    finally:
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
