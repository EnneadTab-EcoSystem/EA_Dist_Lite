#!/usr/bin/python
# -*- coding: utf-8 -*-

__doc__ = """Create or update electrical outlet instances from furniture markers.

No menu, no picking: running the button scans the current model AND every loaded
link for any furniture family that carries a `_para_map` marker, lets you
multi-select which of those discovered families to process, then creates or
corrects every outlet automatically.

Each marker instance names its own outlet family/type and mount height via its
`_para_map` JSON parameter, so markers nested in the same furniture instance can
each place a different outlet at a different height. The outlet instance itself is
always placed at its host level with zero elevation offset -- mount height is
instead written onto the outlet's Placement Height parameter (see
PLACEMENT_HEIGHT_PARAMETER_NAME), and the outlet family's own internal geometry
does the visual raising. The marker's raw position is never used directly either
(markers are modeled above the furniture body on purpose, to stay visible/pickable
-- see the comment above PARA_MAP_TEMPLATE).

Every outlet this tool creates is tagged with the marker that generated it (see
SOURCE_MARKER_TAG_PARAMETER_NAME), so a later run finds it by exact lookup instead
of guessing from position/type -- and can tell the three cases apart: already
correct (left alone), same family but wrong type (retyped in place), or a
completely different family (deleted and replaced). An outlet owned by another
user in a workshared model is left alone either way, and never duplicated.

Every run writes a timestamped debug log to the local dump folder (path printed at
the end) recording what was found, resolved, skipped, and placed -- open it when a
run gets stuck to see exactly what happened. If many markers of the SAME furniture
family in a row fail for the identical reason, that family's remaining markers are
skipped (other selected families are unaffected) instead of grinding through a
doomed setup; a per-marker error (e.g. a hand-edited _para_map typo) never aborts
more than that one marker."""
__title__ = "Place/Update\nElectrical Outlet"

import datetime
import json
import math
import time

import proDUCKtion  # pyright: ignore
proDUCKtion.validify()

from Autodesk.Revit import DB  # pyright: ignore
from System.Collections.Generic import List  # pyright: ignore
import clr  # pyright: ignore
clr.AddReference("System.Windows.Forms")
from System.Windows.Forms import Application  # pyright: ignore
from pyrevit import forms

from EnneadTab import ERROR_HANDLE, FOLDER, LOG, NOTIFICATION
from EnneadTab.REVIT import REVIT_APPLICATION, REVIT_SELECTION, REVIT_FAMILY

from outlet_conflict_row import OutletPlacementTarget

DOC = REVIT_APPLICATION.get_doc()
UIDOC = REVIT_APPLICATION.get_uidoc()
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

# Seconds to pause after each zoom_active_view_to_point call. The zoom only fires
# once every progress_step items (never per item -- see that constant's own
# comments), which on an 800+ item run can be as few as ~8 items apart; without a
# deliberate pause here, that many placements finish faster than the eye can
# register the frame DoEvents() just forced onto screen, so the zoom LOOKS like it
# never happened even though it did. This cost is bounded: at most ~100 pauses per
# run (one per progress_step tick), so total added time is small relative to the run.
ZOOM_PAUSE_SECONDS = 0.2

# Which furniture families carry markers is NEVER hardcoded here: discover_qualified_
# furniture_family_names() finds them live, by scanning for _para_map-carrying
# markers and walking each one up to its host furniture instance's family name (via
# SuperComponent), across the current model AND every loaded link (see
# get_search_scopes). This survives new furniture families getting markers added
# later with zero code changes, and place_from_markers lets the user multi-select a
# subset of the discovered names for a surgical run (e.g. re-running on just one
# furniture type after a model fix) instead of always processing every family.

# Shared fail-fast threshold for BOTH phases of a run:
# - resolve_marker_targets: if this many markers of the SAME furniture family in a
#   row fail with the EXACT SAME reason, that family's remaining markers are skipped.
# - apply_marker_outlets: if this many items in the SAME bucket (to_create/to_replace/
#   to_update/to_retag) in a row raise the EXACT SAME exception during actual
#   placement, that bucket's remaining items are skipped (see check_failure_streak).
# Either way, an identical repeated reason signals a systemic bug or setup problem,
# not a string of unrelated one-off issues, so nothing is gained by continuing --
# fail fast, fix the root cause, rerun. The streak is always scoped to one
# family/bucket, never global, so other families/buckets are unaffected.
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
# meaning and must never be read as the outlet's height. The marker's X/Y are still
# trustworthy (that's real plan position) and are used as-is.
#
# WHY `mount_height` ISN'T BAKED INTO THE INSTANCE'S Z EITHER: the outlet instance is
# placed at its host level with ZERO elevation offset (see PLACEMENT_HEIGHT_PARAMETER_
# NAME below) -- `mount_height` is instead written onto that Placement Height instance
# parameter, and the outlet family's own internal geometry (an offset/extrusion driven
# by that parameter, set up in the Family Editor) does the actual visual raising. The
# ray-cast that finds the host wall/floor uses the level elevation as its target Z, not
# mount_height.
PARA_MAP_TEMPLATE = {
    "family_name": None,
    "type_name": None,
    "mount_height": None,
}

# Written onto every OUTLET this tool creates (never onto the marker -- a marker can
# live inside a read-only link, so it can never be written to; the outlet always
# lives in the CURRENT/host document, which is always writable). Lets a later run
# look an outlet up by exact match instead of guessing from position/type, so it can
# tell "already correct" apart from "same family, wrong type" (retype in place) and
# "different family entirely" (delete and replace) -- see build_marker_tag and
# build_outlets_by_marker_tag.
#
# REQUIRED: this Text instance parameter must exist on every OUTLET family this tool
# targets -- there is no silent fallback. A marker whose target outlet type already
# has an existing instance without this parameter fails resolution up front (see
# check_outlet_type_supports_parameter) with a clear reason, before any ray-casting
# runs for it. A marker whose target type has NO existing instance yet cannot be
# checked that early, so the check happens at creation time instead: if the newly
# placed instance turns out to have no such parameter, apply_marker_outlets deletes
# it again and reports the item failed, rather than leaving an untracked outlet
# behind.
SOURCE_MARKER_TAG_PARAMETER_NAME = "_source_marker_tag"

# REQUIRED, same enforcement as SOURCE_MARKER_TAG_PARAMETER_NAME above. The outlet
# instance itself is placed AT ITS HOST LEVEL with zero elevation offset -- the
# instance's actual Z is never raised to the marker's mount_height. Instead, this
# Length instance parameter is set to that mount_height value, and the outlet
# family's own internal geometry (an offset/extrusion driven by this parameter, set
# up in the Family Editor) is what visually raises the outlet to the right height.
# This keeps the real placement level-hosted and lets Revit schedule/tag the height
# as a normal parameter, instead of it only being implicit in the instance's raw Z.
PLACEMENT_HEIGHT_PARAMETER_NAME = "Placement Height"


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


def build_marker_tag(scope_doc, marker):
    """Build a string identifying `marker` uniquely, even across documents (the host
    model and any number of links), for tagging the OUTLET it generates.

    Never written to the marker itself -- only ever read from it. `scope_doc.Title`
    disambiguates `marker.UniqueId` (a GUID unique within its own document) across
    documents; the outlet-side tag is what actually gets persisted, always in the
    host document, which is always writable.
    """
    return "{}::{}".format(scope_doc.Title, marker.UniqueId)


def get_outlet_source_marker_tag(instance):
    param = instance.LookupParameter(SOURCE_MARKER_TAG_PARAMETER_NAME)
    return param.AsString() if param else None


def _set_required_outlet_param(instance, param_name, value):
    """Write `value` onto `instance`'s `param_name` parameter (a plain .Set, no type
    coercion beyond what the caller passes in).

    Shared by set_outlet_source_marker_tag and set_outlet_placement_height: both
    parameters are REQUIRED on the outlet family -- a missing parameter here is
    treated as a hard setup error by every caller (see
    check_outlet_type_supports_parameter and apply_marker_outlets), not a silent
    fallback. This function only writes and reports whether it could; it never
    decides what to do about a failure.

    Returns:
        bool: True if the value was written, False if the outlet family has no such
        parameter.
    """
    param = instance.LookupParameter(param_name)
    if not param:
        return False
    param.Set(value)
    return True


def set_outlet_source_marker_tag(instance, tag):
    """Write `tag` (see build_marker_tag) onto `instance`'s source-marker-tag
    parameter. See _set_required_outlet_param for the required-parameter contract.
    """
    return _set_required_outlet_param(instance, SOURCE_MARKER_TAG_PARAMETER_NAME, tag)


def get_outlet_placement_height(instance):
    param = instance.LookupParameter(PLACEMENT_HEIGHT_PARAMETER_NAME)
    return param.AsDouble() if param else None


def set_outlet_placement_height(instance, mount_height):
    """Write `mount_height` onto `instance`'s Placement Height parameter -- the
    family's own internal geometry uses this to visually raise the outlet, since the
    instance itself is placed at its host level with zero elevation offset (see
    PLACEMENT_HEIGHT_PARAMETER_NAME). See _set_required_outlet_param for the
    required-parameter contract.
    """
    return _set_required_outlet_param(instance, PLACEMENT_HEIGHT_PARAMETER_NAME, mount_height)


def check_outlet_type_supports_parameter(doc, family_name, type_name, param_name, cache):
    """Return whether an outlet of (family_name, type_name) already placed in `doc`
    has the required `param_name` parameter.

    Returns:
        True/False if an existing instance answered the question definitively, or
        None if no instance of this type exists yet in `doc` -- in that case the
        answer is unknown until the first one is created (apply_marker_outlets
        enforces it there instead; see its to_create handling).

    `cache` is a plain dict the caller owns and reuses across every marker in one
    run, keyed by (family_name, type_name, param_name); only definitive True/False
    answers are cached, never the "unknown" case, since a later marker of the same
    type earlier in the SAME run cannot have created an instance yet either.
    """
    key = (family_name, type_name, param_name)
    if key in cache:
        return cache[key]
    instances = REVIT_FAMILY.get_family_instances_by_family_name_and_type_name(family_name, type_name, doc=doc)
    if not instances:
        return None
    supported = instances[0].LookupParameter(param_name) is not None
    cache[key] = supported
    return supported


def build_outlets_by_marker_tag(doc):
    """One project-wide pass over `doc` (the HOST document -- outlets always live
    there, never in a link), grouping every tagged instance by its
    SOURCE_MARKER_TAG_PARAMETER_NAME value.

    Returns:
        dict {marker_tag (str): DB.FamilyInstance}
    """
    instances = DB.FilteredElementCollector(doc).OfClass(DB.FamilyInstance).WhereElementIsNotElementType().ToElements()
    by_tag = {}
    for instance in instances:
        tag = get_outlet_source_marker_tag(instance)
        if tag:
            by_tag[tag] = instance
    return by_tag


_run_log_lines = []
_run_log_path = None
_run_log_file = None


def start_run_log():
    """Reset the debug log buffer, pick a fresh timestamped file path, and open it
    for LIVE writing -- every debug_log call below writes and flushes immediately, so
    the file on disk can be tailed WHILE the run is still in progress (e.g. in a
    second window, or by this session checking mid-run), not only after it finishes.
    Call once, at the start of one "Place From Marker" run.
    """
    global _run_log_lines, _run_log_path, _run_log_file
    _run_log_lines = []
    timestamp = datetime.datetime.now().strftime("%Y%m%d_%H%M%S")
    _run_log_path = FOLDER.get_local_dump_folder_file("MetroTechOutlet_{}.log".format(timestamp))
    try:
        _run_log_file = open(_run_log_path, "w")
    except Exception as e:
        _run_log_file = None
        ERROR_HANDLE.print_note("Failed to open debug log for live writing: {}".format(e))
    for key in _zoom_diagnostics_logged:
        _zoom_diagnostics_logged[key] = False


def debug_log(message):
    """Append one line to this run's debug log, flush it to disk immediately, and
    echo it via ERROR_HANDLE.print_note.

    Unlike print_note (gated on USER.IS_DEVELOPER), the buffered/written copy is
    never gated: the whole point of this per-run log file is that whoever is testing
    the tool can open it WHILE the run is still going (immediate flush) or afterward,
    and see exactly what happened -- not just a developer watching the pyRevit output
    window live.
    """
    _run_log_lines.append(message)
    if _run_log_file is not None:
        try:
            _run_log_file.write(message + "\n")
            _run_log_file.flush()
        except Exception:
            pass
    try:
        ERROR_HANDLE.print_note(message)
    except Exception:
        pass


def save_run_log():
    """Close this run's live log file handle.

    debug_log already writes and flushes every line to disk immediately, so this is
    no longer what actually persists the content -- it just closes the handle
    cleanly. Kept as the caller-facing "finish the log" step (called from
    place_from_markers's `finally`) and to report the final path. Quietly no-ops if
    start_run_log() was never called or nothing was logged.

    Returns:
        str or None: the file path written, or None if there was nothing to save.
    """
    global _run_log_file
    if not _run_log_path or not _run_log_lines:
        return None
    if _run_log_file is not None:
        try:
            _run_log_file.close()
        except Exception as e:
            ERROR_HANDLE.print_note("Failed to close debug log: {}".format(e))
        _run_log_file = None
    return _run_log_path


def type_name_of(family_type):
    return family_type.LookupParameter("Type Name").AsString()


def get_any_3d_view(doc):
    """Return an existing non-template, non-section-boxed 3D view, or create one.

    A view is required by DB.ReferenceIntersector for the marker-driven raycast; a
    plan/section view cannot be used for it. DB.ReferenceIntersector only finds
    geometry inside the view's active section box, if one is set -- a view like a
    "working" view scoped down to one area of the building would silently make every
    ray-cast outside that area come up with zero hits, indistinguishable from "no wall
    nearby" (this is exactly what an out-of-range probe in find_nearest_host_face
    caught: real, plausible coordinates, correct category visibility, correct phase,
    yet nothing found even at unlimited distance -- a section box is the one thing
    that crops visible geometry independently of all of those). So a section-boxed
    view is skipped entirely rather than risked.

    The created view is NOT deleted after use -- it becomes a permanent addition to
    the project (there's no reliable way to "borrow" a view for a single ray-cast and
    clean it back up mid-transaction). Creating a view is a document change and must
    run inside an open transaction, so this opens its own single-purpose one only
    when the fallback is actually needed.
    """
    views = DB.FilteredElementCollector(doc).OfClass(DB.View3D).WhereElementIsNotElementType().ToElements()
    for view in views:
        if not view.IsTemplate and not view.IsSectionBoxActive:
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


def _log_out_of_range_probe(doc, intersector, point, directions, required_host_type):
    """Diagnostic only -- never affects resolution. Called from find_nearest_host_face
    when the normal fan-cast (bounded by MARKER_RAYCAST_MAX_DISTANCE) finds nothing, to
    re-cast the SAME directions with no distance limit and log the nearest matching
    element actually out there, if any.

    This distinguishes two very different failure modes that otherwise look identical
    ("0 rays hit"): NOTHING found at any distance in any direction (something is
    fundamentally off -- the 3D view's Walls/Floors category visibility or phase
    filter, or the furniture link's placement/shared-coordinates not lining up with
    this document) versus something found just past MARKER_RAYCAST_MAX_DISTANCE (the
    marker really is near a wall/floor, just farther than expected -- a distance-tuning
    problem, not a setup problem).
    """
    nearest = None
    for direction in directions:
        for hit in intersector.Find(point, direction):
            reference = hit.GetReference()
            element = doc.GetElement(reference)
            if required_host_type is not None and not isinstance(element, required_host_type):
                continue
            if nearest is None or hit.Proximity < nearest[0]:
                nearest = (hit.Proximity, element)
    if nearest is None:
        debug_log(
            "  (diagnostic: no matching wall/floor found in ANY direction at ANY distance -- check the 3D "
            "view's category visibility/phase filter for Walls and Floors, and whether the furniture link's "
            "placement (shared coordinates) actually lines up with this document.)")
    else:
        proximity, element = nearest
        debug_log(
            "  (diagnostic: nearest matching element is {} ft away (past the {} ft limit) -- host [{}]. If "
            "this is the intended wall/floor, MARKER_RAYCAST_MAX_DISTANCE may need to be larger.)".format(
                round(proximity, 2), MARKER_RAYCAST_MAX_DISTANCE, element.Id))


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
        _log_out_of_range_probe(doc, intersector, point, directions, required_host_type)
        return None, None, None, None
    host, face, hit_point, stable_ref = best
    debug_log(
        "Fan-cast from ({}, {}, {}): {} of {} rays hit; nearest host [{}] at {} ft".format(
            round(point.X, 2), round(point.Y, 2), round(point.Z, 2),
            hit_count, len(directions), host.Id, round(best_distance, 3)))
    return best


def log_view3d_raycast_diagnostics(doc, view3d):
    """Log once per run whether Walls/Floors are actually visible in `view3d` and what
    phase it's showing.

    DB.ReferenceIntersector only finds geometry that is VISIBLE in the view it was built
    from (build_wall_floor_intersector) -- a category hidden by V/G overrides, or a phase
    filter that hides not-yet-existing/demolished elements, makes every ray-cast in the
    whole run come up empty with no error at all, which looks identical to "the marker
    really isn't near a wall/floor." This is a fact worth ruling out up front rather than
    rediscovering it one fan-cast miss at a time -- and unlike _log_out_of_range_probe,
    it does not depend on the view-bound intersector, so it still tells the truth even
    when the category IS hidden (a case the probe alone cannot distinguish from "nothing
    is really there").
    """
    for bic in (DB.BuiltInCategory.OST_Walls, DB.BuiltInCategory.OST_Floors):
        category = DB.Category.GetCategory(doc, bic)
        try:
            hidden = view3d.GetCategoryHidden(category.Id) if category else "category not found"
        except Exception as e:
            hidden = "could not check ({})".format(e)
        debug_log("View3D [{}] '{}': {} hidden = {}".format(view3d.Id, view3d.Name, bic, hidden))
    phase = doc.GetElement(view3d.get_Parameter(DB.BuiltInParameter.VIEW_PHASE).AsElementId()) \
        if view3d.get_Parameter(DB.BuiltInParameter.VIEW_PHASE) else None
    debug_log("View3D [{}] '{}': phase = {}".format(
        view3d.Id, view3d.Name, phase.Name if phase else "(none)"))
    # A section box crops which geometry is visible in the view independently of
    # category visibility and phase -- get_any_3d_view already skips a section-boxed
    # view when picking one, but this confirms it explicitly in the log rather than
    # leaving it implicit, in case every existing view happened to have one active.
    debug_log("View3D [{}] '{}': section box active = {}".format(
        view3d.Id, view3d.Name, view3d.IsSectionBoxActive))


def to_host_point(point, link_transform):
    """Map `point` from its scope document's own local space into host-doc
    coordinates via `link_transform`, or return it unchanged when link_transform is
    None (the point already belongs to the host doc). Shared by the marker/furniture
    sanity-check log and zoom_active_view_to_point, so both agree on exactly how a
    link-local point becomes a host-space one.
    """
    return link_transform.OfPoint(point) if link_transform is not None else point


_zoom_diagnostics_logged = {"no_match": False, "error": False, "success": False}


def zoom_active_view_to_point(point, margin=10.0):
    """Best-effort: pan/zoom whatever UIView is showing the active view to frame
    `point` (host-doc coordinates), so a long run is visually watchable instead of a
    frozen screen while it works. Called at the same throttled cadence as the
    progress bar's own updates (progress_step), never per item -- zooming/repainting
    on every single marker across an 800+ item run would be a real performance cost,
    working directly against the fail-fast/iterate-fast goal this tool is built for.

    On failure this must never interrupt or fail the run -- but it used to swallow
    EVERY exception with zero logging, which made a silent no-op indistinguishable
    from a working-but-invisible zoom. Each distinct outcome (no matching UIView, an
    exception, or the first confirmed success) is now logged ONCE per run via
    _zoom_diagnostics_logged, so a run where nothing visibly zoomed leaves a clear
    reason in the log instead of just silence.

    RefreshActiveView() alone only REQUESTS a repaint; Revit's UI thread doesn't
    actually paint it until it gets to process its Windows message queue, which a
    tight Python loop never yields to on its own -- without pumping messages here,
    nothing visibly changes on screen until the whole run finishes. Application.
    DoEvents() forces that pump immediately, so the pan/zoom is actually visible
    live instead of a frozen screen that jumps to its final state at the very end.
    """
    try:
        active_view = UIDOC.ActiveView
        active_id = active_view.Id
        matched = False
        for ui_view in UIDOC.GetOpenUIViews():
            if ui_view.ViewId == active_id:
                matched = True
                corner1 = DB.XYZ(point.X - margin, point.Y - margin, point.Z - margin)
                corner2 = DB.XYZ(point.X + margin, point.Y + margin, point.Z + margin)
                ui_view.ZoomAndCenterRectangle(corner1, corner2)
                break
        if matched and not _zoom_diagnostics_logged["success"]:
            debug_log(
                "zoom_active_view_to_point: first zoom succeeded, on active view [{}] '{}' ({}).".format(
                    active_id, active_view.Name, active_view.ViewType))
            _zoom_diagnostics_logged["success"] = True
        if not matched and not _zoom_diagnostics_logged["no_match"]:
            debug_log(
                "zoom_active_view_to_point: active view [{}] '{}' ({}) has no open UIView -- nothing to zoom. "
                "Keep that exact view open and active for the whole run to see it live.".format(
                    active_id, active_view.Name, active_view.ViewType))
            _zoom_diagnostics_logged["no_match"] = True
        UIDOC.RefreshActiveView()
        Application.DoEvents()
        if matched:
            time.sleep(ZOOM_PAUSE_SECONDS)
    except Exception as e:
        if not _zoom_diagnostics_logged["error"]:
            debug_log("zoom_active_view_to_point failed (logged once, run continues): {}".format(e))
            _zoom_diagnostics_logged["error"] = True


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


def _resolve_one_marker(doc, scope_doc, link_transform, furniture, furniture_level, marker, intersector,
                         symbol_cache, tag_support_cache):
    """Resolve one marker to its outlet symbol and host face, or the reason it can't be.

    Isolated into its own function so resolve_marker_targets can wrap a single call in
    try/except: a per-marker error (e.g. a hand-edited _para_map with a non-numeric
    mount_height) must fail that ONE marker, never abort the whole run.

    Returns:
        tuple (reason, host, face, hit_point, stable_ref, family, family_type,
        mount_height, level_name). `reason` is None on success; every other field is
        None when `reason` is set.
    """
    para_map = get_marker_para_map(marker)
    if any(value is not None for value in para_map.values()):
        debug_log("Marker [{}] {}: {}".format(marker.Id, PARA_MAP_PARAMETER_NAME, para_map))

    outlet_family_name = para_map.get("family_name")
    outlet_type_name = para_map.get("type_name")
    mount_height = para_map.get("mount_height")
    if not outlet_family_name or not outlet_type_name or mount_height is None:
        return ("{} needs family_name, type_name, and mount_height all set".format(PARA_MAP_PARAMETER_NAME),
                None, None, None, None, None, None, None, None)

    family, family_type = resolve_outlet_symbol(doc, outlet_family_name, outlet_type_name, symbol_cache)
    if not family or not family_type:
        return ("outlet [{}] - [{}] is not loaded".format(outlet_family_name, outlet_type_name),
                None, None, None, None, None, None, None, None)

    # SOURCE_MARKER_TAG_PARAMETER_NAME and PLACEMENT_HEIGHT_PARAMETER_NAME are both
    # required, no silent fallback. If an outlet of this exact type already exists,
    # check both now and fail fast before any ray-casting; if none exists yet, this
    # can't be known until the first one is created (apply_marker_outlets enforces it
    # there instead).
    for required_param_name in (SOURCE_MARKER_TAG_PARAMETER_NAME, PLACEMENT_HEIGHT_PARAMETER_NAME):
        supported = check_outlet_type_supports_parameter(
            doc, outlet_family_name, outlet_type_name, required_param_name, tag_support_cache)
        if supported is False:
            return ("outlet [{}] - [{}] is missing the required {} parameter -- add it to the family in the "
                     "Family Editor, then rerun".format(outlet_family_name, outlet_type_name, required_param_name),
                     None, None, None, None, None, None, None, None)

    if family.FamilyPlacementType not in (DB.FamilyPlacementType.WorkPlaneBased, DB.FamilyPlacementType.OneLevelBasedHosted):
        return ("outlet [{}] is neither face-based nor wall-hosted".format(outlet_family_name),
                None, None, None, None, None, None, None, None)

    if furniture_level is None:
        return ("host furniture [{}] has no level".format(furniture.Id),
                None, None, None, None, None, None, None, None)

    local_point, _orientation = REVIT_FAMILY.get_nested_instance_placement(marker)
    if local_point is None:
        return ("no location available", None, None, None, None, None, None, None, None)

    # The outlet is placed AT its host level, zero elevation offset -- mount_height is
    # never baked into the instance's real Z. Instead it gets written onto the
    # PLACEMENT_HEIGHT_PARAMETER_NAME parameter (see apply_marker_outlets), and the
    # outlet family's own internal geometry is what visually raises it to that height.
    # So the ray-cast target Z here is just the furniture's level elevation.
    corrected_point = DB.XYZ(local_point.X, local_point.Y, furniture_level.Elevation)
    if link_transform is not None:
        corrected_point = link_transform.OfPoint(corrected_point)
    debug_log(
        "Marker [{}]: furniture [{}] level [{}] (elev {}) -> corrected point {} (mount_height {} goes onto "
        "the {} parameter, not the instance Z)".format(
            marker.Id, furniture.Id, furniture_level.Name, round(furniture_level.Elevation, 2),
            (round(corrected_point.X, 2), round(corrected_point.Y, 2), round(corrected_point.Z, 2)),
            mount_height, PLACEMENT_HEIGHT_PARAMETER_NAME))

    # Sanity check, diagnostic only: the furniture instance's OWN position, mapped
    # through the same link_transform used for the marker. The marker should land a
    # few feet from its own host furniture -- if this distance is huge (tens/hundreds
    # of feet, or a wildly different Z), the bug is in resolving marker/furniture
    # coordinates through the link, not in the wall/floor search that follows.
    furniture_point = get_instance_point(furniture)
    if furniture_point is not None:
        furniture_point_in_host = to_host_point(furniture_point, link_transform)
        debug_log(
            "  (sanity check: furniture [{}] itself is at {} in host coordinates -- {} ft from the marker's "
            "corrected point above; if that's more than a few feet, marker/furniture coordinate resolution "
            "through the link is the bug, not the wall/floor search.)".format(
                furniture.Id,
                (round(furniture_point_in_host.X, 2), round(furniture_point_in_host.Y, 2),
                 round(furniture_point_in_host.Z, 2)),
                round(furniture_point_in_host.DistanceTo(corrected_point), 2)))

    required_host_type = DB.Wall if family.FamilyPlacementType == DB.FamilyPlacementType.OneLevelBasedHosted else None
    host, face, hit_point, stable_ref = find_nearest_host_face(
        doc, intersector, corrected_point, required_host_type=required_host_type)
    if host is None:
        needed = "wall" if required_host_type is not None else "wall/floor"
        return ("no {} within {} ft in any direction".format(needed, MARKER_RAYCAST_MAX_DISTANCE),
                None, None, None, None, None, None, None, None)

    return (None, host, face, hit_point, stable_ref, family, family_type, mount_height, furniture_level.Name)


def resolve_marker_targets(doc, furniture_family_names, view3d, symbol_cache, scopes):
    """Find every instance of `furniture_family_names` across every search scope (the
    host document plus every loaded link -- see get_search_scopes), and within each
    one, every nested marker (build_para_map_markers_by_furniture_id). Each marker's
    own _para_map names the outlet family/type and mount height to place there, so
    this also resolves that outlet symbol and fan-casts the marker's corrected point
    to its host face (see _resolve_one_marker for the per-marker logic).

    A furniture instance can nest more than one marker (each independently naming its
    own outlet/height), so the ray-cast target Z always comes from the FURNITURE
    instance's own level elevation (zero offset) -- never the marker's raw Z. Only
    the marker's X/Y are taken as-is. The outlet's real-world height is never baked
    into its instance Z at all; mount_height is written onto
    PLACEMENT_HEIGHT_PARAMETER_NAME instead (see apply_marker_outlets), and the
    outlet family's own internal geometry does the visual raising.

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
          resolved   -- list of (marker, marker_tag, host, face, hit_point, stable_ref,
                        family, family_type, mount_height, level_name)
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
    tag_support_cache = {}

    resolved = []
    unresolved = []

    total_markers = sum(len(entries) for entries in entries_by_family.values())
    # step > 1 for a large batch: a live repaint on every single marker (e.g. all 800+
    # of them) is wasted UI overhead once the bar is already fine-grained enough to be
    # useful -- one visible tick per ~1% of the run reads just as smoothly.
    progress_step = max(1, total_markers // 100)
    processed = 0
    user_cancelled = False

    with forms.ProgressBar(
            title="Resolving outlet markers... ({value} of {max_value})",
            step=progress_step, cancellable=True) as pb:

        for family_name in furniture_family_names:
            if user_cancelled:
                break
            entries = entries_by_family.get(family_name, [])
            streak_reason = None
            streak_count = 0

            for index, (furniture, furniture_level, marker, scope_doc, link_transform) in enumerate(entries):
                try:
                    reason, host, face, hit_point, stable_ref, family, family_type, mount_height, level_name = \
                        _resolve_one_marker(
                            doc, scope_doc, link_transform, furniture, furniture_level, marker, intersector,
                            symbol_cache, tag_support_cache)
                except Exception as e:
                    reason = "internal error: {}".format(e)
                    host = face = hit_point = stable_ref = family = family_type = mount_height = level_name = None

                processed += 1
                pb.update_progress(processed, total_markers)
                if processed % progress_step == 0:
                    furniture_point = get_instance_point(furniture)
                    if furniture_point is not None:
                        zoom_active_view_to_point(to_host_point(furniture_point, link_transform))

                if reason is None:
                    marker_tag = build_marker_tag(scope_doc, marker)
                    resolved.append(
                        (marker, marker_tag, host, face, hit_point, stable_ref, family, family_type, mount_height,
                         level_name))
                    streak_reason = None
                    streak_count = 0
                else:
                    unresolved.append((marker, reason))
                    if reason == streak_reason:
                        streak_count += 1
                    else:
                        streak_reason = reason
                        streak_count = 1
                    if streak_count >= CONSECUTIVE_UNRESOLVED_ABORT_THRESHOLD:
                        remaining = len(entries) - index - 1
                        debug_log(
                            "Aborting furniture family [{}] early: {} consecutive markers failed with the same "
                            "reason [{}] -- likely a systemic model/family setup issue for this family, not "
                            "independent per-marker problems. Skipping its remaining {} marker(s); other selected "
                            "families are unaffected. Fix the root cause and rerun.".format(
                                family_name, streak_count, reason, remaining))
                        break

                if pb.cancelled:
                    user_cancelled = True
                    debug_log(
                        "User cancelled resolving after {} of {} marker(s); {} family/families not yet reached "
                        "are skipped entirely, and the current family's remaining markers are skipped too.".format(
                            processed, total_markers, len(furniture_family_names)))
                    break

    debug_log("resolve_marker_targets: {} resolved, {} unresolved{}".format(
        len(resolved), len(unresolved), " (cancelled early)" if user_cancelled else ""))
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


def apply_marker_outlets(to_create, to_replace, to_update, to_retag):
    """Create, replace, move/retype, or retag outlets in one transaction.

    Called directly and synchronously from place_from_markers, which is itself
    already running in Revit's API context (the button's own entry point) -- there
    is no modeless review step in this flow, so no ExternalEvent is needed.

    - `to_create`: list of (OutletPlacementTarget, marker_tag) -- nothing exists for
      this marker yet; place it (at its host level, zero elevation offset -- see
      OutletPlacementTarget), tag it, and set its Placement Height.
    - `to_replace`: list of (old_instance_id, OutletPlacementTarget, marker_tag) --
      the tagged/matched existing instance is a DIFFERENT FAMILY than the marker now
      targets; Revit cannot reassign an instance across families (only across types
      within the same family), so the old one is deleted and a new one created,
      tagged, and height-set in its place.
    - `to_update`: list of (instance_id, target_point, new_type_name_or_None,
      marker_tag, mount_height, level_name) -- the existing instance is already the
      correct family. If `new_type_name_or_None` is set, its type differs and gets
      swapped via `Symbol =` (same-family retype, no delete needed); either way it is
      moved to `target_point`, re-tagged, and its Placement Height is (re)set to
      `mount_height` -- this can be the ONLY thing that changed, since mount_height no
      longer affects `target_point` at all (see PLACEMENT_HEIGHT_PARAMETER_NAME).
    - `to_retag`: list of (instance_id, marker_tag, mount_height, level_name) -- a
      legacy, untagged instance that already exactly matches its marker's target
      family/type/position (found by position+type proximity, which never checks
      height); the tag AND Placement Height are (re)written unconditionally, so a
      future run finds it directly instead of falling back to position/type matching
      again, and its height is guaranteed correct rather than assumed.

    `level_name` (the HOST FURNITURE's level, e.g. "4TH FLOOR") is carried purely for
    the per-level summary this function returns -- see level_stats below.
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

    def do_create(item):
        family_type = resolve_symbol(item.family_name, item.type_name)
        if not family_type:
            debug_log("Outlet [{}] - [{}] is no longer loaded, skipping host [{}].".format(
                item.family_name, item.type_name, item.host_id))
            return None
        host = doc.GetElement(DB.ElementId(item.host_id))
        point = DB.XYZ(item.point[0], item.point[1], item.point[2])
        if item.stable_ref:
            reference = DB.Reference.ParseFromStableRepresentation(doc, item.stable_ref)
            # Pass the Reference straight to NewFamilyInstance rather than extracting a
            # DB.Face from it first (host.GetGeometryObjectFromReference(reference)) --
            # that Face's internal .Reference isn't reliably populated for every host
            # face type, which fails with "The Reference of the input face is null"
            # even though the Face DID come from a Reference (see
            # REVIT_FAMILY.place_instance_by_reference's docstring). DB.XYZ.BasisZ as
            # reference_direction is the API equivalent of the Revit UI's "Place on
            # Vertical Face" tool: keeps the instance plumb regardless of face tilt.
            return REVIT_FAMILY.place_instance_by_reference(
                family_type, reference, point, reference_direction=DB.XYZ.BasisZ, doc=doc)
        if isinstance(host, DB.Wall):
            level = doc.GetElement(host.LevelId)
            return REVIT_FAMILY.place_instance_by_wall(family_type, point, host, level=level, doc=doc)
        debug_log(
            "Cannot place outlet [{}] - [{}] on host [{}]: no face reference and host is not a wall "
            "(host type: {}).".format(item.family_name, item.type_name, item.host_id, type(host).__name__))
        return None

    def apply_required_params_or_delete(instance, marker_tag, mount_height, item):
        """Set both required parameters on a NEWLY CREATED `instance`; if the family
        lacks either one, delete `instance` again rather than leave an incompletely
        configured outlet behind (SOURCE_MARKER_TAG_PARAMETER_NAME and
        PLACEMENT_HEIGHT_PARAMETER_NAME are both required, no silent fallback for a
        brand-new placement -- see those constants' comments). Returns True on
        success, False if it deleted the instance.
        """
        tag_ok = set_outlet_source_marker_tag(instance, marker_tag)
        height_ok = set_outlet_placement_height(instance, mount_height)
        if tag_ok and height_ok:
            return True
        missing = [name for ok, name in (
            (tag_ok, SOURCE_MARKER_TAG_PARAMETER_NAME), (height_ok, PLACEMENT_HEIGHT_PARAMETER_NAME)) if not ok]
        debug_log(
            "Outlet family [{}] is missing the required {} parameter(s) -- deleting the outlet just placed "
            "for type [{}] and marking it failed. Add {} to the family, then rerun.".format(
                item.family_name, " and ".join(missing), item.type_name, " and ".join(missing)))
        doc.Delete(instance.Id)
        return False

    # Per-level breakdown for the run summary (see level_summary_lines below), keyed
    # by the HOST FURNITURE's level name -- an outlet at a furniture with no level
    # cannot exist (_resolve_one_marker already fails that marker), so this key is
    # never None in practice, but "(no level)" is the fallback just in case.
    level_stats = {}

    def bump_level_stat(level_name, key):
        stats = level_stats.setdefault(level_name or "(no level)", {
            "created": 0, "replaced": 0, "updated": 0, "retagged": 0, "needs_attention": 0})
        stats[key] += 1

    def check_failure_streak(streak_state, reason, bucket_name, total_in_bucket, index):
        """Update `streak_state` (a mutable [reason, count] pair, one per bucket) with
        one more exception `reason`, and return True if that bucket should stop
        processing its remaining items now.

        Mirrors resolve_marker_targets's per-family fail-fast, applied here to the
        APPLY phase instead: resolve's circuit breaker only ever sees ray-cast/lookup
        failures, since it never calls NewFamilyInstance -- an exception during actual
        placement (e.g. a bad API call, a corrupt host face) is invisible to it and
        was previously caught per-item with no streak-based abort at all, so a
        systemic bug would silently fail on every single item without ever stopping
        early (see the "Reference of the input face is null" incident this was built
        to catch). CONSECUTIVE_UNRESOLVED_ABORT_THRESHOLD identical exception messages
        in a row -> abort just THIS bucket's remaining items; the other three buckets
        are unaffected, since each gets its own streak_state.
        """
        if reason == streak_state[0]:
            streak_state[1] += 1
        else:
            streak_state[0] = reason
            streak_state[1] = 1
        if streak_state[1] >= CONSECUTIVE_UNRESOLVED_ABORT_THRESHOLD:
            remaining = total_in_bucket - index - 1
            debug_log(
                "Aborting '{}' early: {} consecutive item(s) failed with the same error [{}] -- likely a "
                "systemic bug or setup issue, not independent per-item problems. Skipping its remaining {} "
                "item(s); other buckets are unaffected. Fix the root cause and rerun.".format(
                    bucket_name, streak_state[1], reason, remaining))
            return True
        return False

    created = 0
    replaced = 0
    updated = 0
    retagged = 0
    required_param_failed = 0
    failed = []

    total_items = len(to_create) + len(to_replace) + len(to_update) + len(to_retag)
    progress_step = max(1, total_items // 100)
    processed = 0
    user_cancelled = False

    t = DB.Transaction(doc, "Place/Update Electrical Outlet From Marker")
    t.Start()
    try:
        with forms.ProgressBar(
                title="Placing/updating outlets... ({value} of {max_value})",
                step=progress_step, cancellable=True) as pb:

            create_streak = [None, 0]
            if not user_cancelled:
                for index, (item, marker_tag) in enumerate(to_create):
                    if user_cancelled:
                        break
                    try:
                        instance = do_create(item)
                        if instance and apply_required_params_or_delete(instance, marker_tag, item.mount_height, item):
                            created += 1
                            bump_level_stat(item.level_name, "created")
                            debug_log("Placed outlet [{}] - [{}]/[{}] on host [{}] at {} (height {}), tagged.".format(
                                instance.Id, item.family_name, item.type_name, item.host_id, item.point,
                                item.mount_height))
                        else:
                            failed.append(item.host_id)
                            bump_level_stat(item.level_name, "needs_attention")
                    except Exception as e:
                        debug_log("Failed to place outlet on host [{}]: {}".format(item.host_id, e))
                        failed.append(item.host_id)
                        bump_level_stat(item.level_name, "needs_attention")
                        if check_failure_streak(create_streak, str(e), "to_create", len(to_create), index):
                            break
                    processed += 1
                    pb.update_progress(processed, total_items)
                    if processed % progress_step == 0:
                        zoom_active_view_to_point(DB.XYZ(*item.point))
                    if pb.cancelled:
                        user_cancelled = True
                        break

            replace_streak = [None, 0]
            if not user_cancelled:
                for index, (old_instance_id, item, marker_tag) in enumerate(to_replace):
                    if user_cancelled:
                        break
                    try:
                        doc.Delete(DB.ElementId(old_instance_id))
                        instance = do_create(item)
                        if instance and apply_required_params_or_delete(instance, marker_tag, item.mount_height, item):
                            replaced += 1
                            bump_level_stat(item.level_name, "replaced")
                            debug_log("Replaced outlet [{}] with [{}] - [{}]/[{}] at {} (height {}), tagged.".format(
                                old_instance_id, instance.Id, item.family_name, item.type_name, item.point,
                                item.mount_height))
                        else:
                            failed.append(old_instance_id)
                            bump_level_stat(item.level_name, "needs_attention")
                    except Exception as e:
                        debug_log("Failed to replace outlet [{}]: {}".format(old_instance_id, e))
                        failed.append(old_instance_id)
                        bump_level_stat(item.level_name, "needs_attention")
                        if check_failure_streak(replace_streak, str(e), "to_replace", len(to_replace), index):
                            break
                    processed += 1
                    pb.update_progress(processed, total_items)
                    if processed % progress_step == 0:
                        zoom_active_view_to_point(DB.XYZ(*item.point))
                    if pb.cancelled:
                        user_cancelled = True
                        break

            update_streak = [None, 0]
            if not user_cancelled:
                for index, (instance_id, target_point_tuple, new_type_name, marker_tag, mount_height, level_name) \
                        in enumerate(to_update):
                    if user_cancelled:
                        break
                    try:
                        existing = doc.GetElement(DB.ElementId(instance_id))
                        if existing is None:
                            failed.append(instance_id)
                            bump_level_stat(level_name, "needs_attention")
                            continue
                        if new_type_name is not None:
                            family_name = REVIT_FAMILY.get_family_name(existing)
                            new_type = resolve_symbol(family_name, new_type_name)
                            if new_type:
                                existing.Symbol = new_type
                        current_point = get_instance_point(existing)
                        target_point = DB.XYZ(target_point_tuple[0], target_point_tuple[1], target_point_tuple[2])
                        if current_point is not None:
                            DB.ElementTransformUtils.MoveElement(doc, existing.Id, target_point - current_point)
                        # This instance PRE-EXISTED (not created by this run), so a missing
                        # required parameter here does not undo the move/retype that already
                        # succeeded -- deleting someone's existing outlet over a bookkeeping
                        # gap would be far worse than just flagging it loudly.
                        tag_ok = set_outlet_source_marker_tag(existing, marker_tag)
                        height_ok = set_outlet_placement_height(existing, mount_height)
                        updated += 1
                        bump_level_stat(level_name, "updated")
                        if not (tag_ok and height_ok):
                            required_param_failed += 1
                            bump_level_stat(level_name, "needs_attention")
                            missing = [name for ok, name in (
                                (tag_ok, SOURCE_MARKER_TAG_PARAMETER_NAME),
                                (height_ok, PLACEMENT_HEIGHT_PARAMETER_NAME)) if not ok]
                            debug_log(
                                "Outlet [{}]'s family has no required {} parameter(s) -- moved/retyped it, but "
                                "could not fully configure it. Add {} to the family, then rerun.".format(
                                    instance_id, " and ".join(missing), " and ".join(missing)))
                        debug_log("Updated outlet [{}]{} to {} (height {}).".format(
                            instance_id, " (retyped to [{}])".format(new_type_name) if new_type_name else "",
                            target_point_tuple, mount_height))
                    except Exception as e:
                        debug_log("Failed to update outlet [{}]: {}".format(instance_id, e))
                        failed.append(instance_id)
                        bump_level_stat(level_name, "needs_attention")
                        if check_failure_streak(update_streak, str(e), "to_update", len(to_update), index):
                            break
                    processed += 1
                    pb.update_progress(processed, total_items)
                    if processed % progress_step == 0:
                        zoom_active_view_to_point(DB.XYZ(*target_point_tuple))
                    if pb.cancelled:
                        user_cancelled = True
                        break

            retag_streak = [None, 0]
            if not user_cancelled:
                for index, (instance_id, marker_tag, mount_height, level_name) in enumerate(to_retag):
                    if user_cancelled:
                        break
                    existing = None
                    try:
                        existing = doc.GetElement(DB.ElementId(instance_id))
                        if existing is None:
                            failed.append(instance_id)
                            bump_level_stat(level_name, "needs_attention")
                            continue
                        tag_ok = set_outlet_source_marker_tag(existing, marker_tag)
                        height_ok = set_outlet_placement_height(existing, mount_height)
                        if tag_ok and height_ok:
                            retagged += 1
                            bump_level_stat(level_name, "retagged")
                        else:
                            required_param_failed += 1
                            bump_level_stat(level_name, "needs_attention")
                            missing = [name for ok, name in (
                                (tag_ok, SOURCE_MARKER_TAG_PARAMETER_NAME),
                                (height_ok, PLACEMENT_HEIGHT_PARAMETER_NAME)) if not ok]
                            debug_log(
                                "Outlet [{}]'s family has no required {} parameter(s) -- left it as-is (already "
                                "correct position/type), but could not fully configure it. Add {} to the family, "
                                "then rerun.".format(instance_id, " and ".join(missing), " and ".join(missing)))
                    except Exception as e:
                        debug_log("Failed to tag existing outlet [{}]: {}".format(instance_id, e))
                        failed.append(instance_id)
                        bump_level_stat(level_name, "needs_attention")
                        if check_failure_streak(retag_streak, str(e), "to_retag", len(to_retag), index):
                            break
                    processed += 1
                    pb.update_progress(processed, total_items)
                    if processed % progress_step == 0 and existing is not None:
                        existing_point = get_instance_point(existing)
                        if existing_point is not None:
                            zoom_active_view_to_point(existing_point)
                    if pb.cancelled:
                        user_cancelled = True
                        break

            if user_cancelled:
                debug_log(
                    "User cancelled placing/updating after {} of {} item(s); everything applied so far is still "
                    "committed -- nothing is rolled back, the remaining items just weren't reached yet.".format(
                        processed, total_items))

        t.Commit()
    except Exception:
        t.RollBack()
        raise

    lines = ["Total: Placed {} | Replaced {} | Updated {} | Tagged {}".format(created, replaced, updated, retagged)]
    if user_cancelled:
        lines.append("Cancelled by user after {} of {} item(s); already-applied changes were kept.".format(
            processed, total_items))
    if required_param_failed:
        lines.append(
            "{} instance(s) updated/adopted but could not be fully configured (family missing {} and/or {} "
            "parameter).".format(
                required_param_failed, SOURCE_MARKER_TAG_PARAMETER_NAME, PLACEMENT_HEIGHT_PARAMETER_NAME))
    if failed:
        lines.append("Failed on {} item(s), see output for detail.".format(len(failed)))

    if level_stats:
        lines.append("By level:")
        for level_name in sorted(level_stats.keys()):
            s = level_stats[level_name]
            level_line = "  {}: Placed {} | Replaced {} | Updated {} | Tagged {}".format(
                level_name, s["created"], s["replaced"], s["updated"], s["retagged"])
            if s["needs_attention"]:
                level_line += " | Needs attention {}".format(s["needs_attention"])
            lines.append(level_line)

    result = "\n".join(lines)
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
        debug_log("Host document: [{}]".format(doc.Title))
        log_view3d_raycast_diagnostics(doc, view3d)
        symbol_cache = {}
        resolved, unresolved = resolve_marker_targets(doc, selected_names, view3d, symbol_cache, scopes)
        for marker, reason in unresolved:
            print("Marker [{}]: {}".format(marker.Id, reason))
        if not resolved:
            NOTIFICATION.messenger(
                "Found {} marker(s) across [{}], but none resolved to a placeable outlet.".format(
                    len(unresolved), furniture_label))
            return

        outlets_by_marker_tag = build_outlets_by_marker_tag(doc)
        existing_instances_cache = {}  # (family_name, type_name) -> list of DB.FamilyInstance

        def get_existing_instances(family, family_type):
            key = (family.Name, type_name_of(family_type))
            if key not in existing_instances_cache:
                # editable_only is intentionally NOT passed (defaults False): an
                # outlet owned by another workshared user must still be found here so
                # this marker is never treated as empty and given a duplicate right
                # on top of it. Ownership is only checked separately, below, when
                # actually deciding whether to move/retype/replace one.
                existing_instances_cache[key] = REVIT_FAMILY.get_family_instances_by_family_name_and_type_name(
                    family.Name, type_name_of(family_type), doc=doc)
            return existing_instances_cache[key]

        to_create = []        # (OutletPlacementTarget, marker_tag)
        to_replace = []       # (old_instance_id, OutletPlacementTarget, marker_tag)
        to_update = []        # (instance_id, target_point, new_type_name_or_None, marker_tag, mount_height, level_name)
        to_retag = []         # (instance_id, marker_tag, mount_height, level_name)
        already_placed = []   # existing instance, no action needed
        skipped_foreign = []  # existing instance nearby but owned by another user
        for marker, marker_tag, host, face, hit_point, stable_ref, family, family_type, mount_height, level_name \
                in resolved:
            point_tuple = (hit_point.X, hit_point.Y, hit_point.Z)
            type_name = type_name_of(family_type)
            use_stable_ref = stable_ref if family.FamilyPlacementType == DB.FamilyPlacementType.WorkPlaneBased else None
            target = OutletPlacementTarget(
                element_int_id(host), point_tuple, family.Name, type_name, mount_height, level_name, use_stable_ref)

            existing = outlets_by_marker_tag.get(marker_tag)
            if existing is None:
                # No tagged outlet yet for this marker -- fall back to a position+type
                # check so a pre-existing, untagged, already-correct instance (hand
                # placed, or placed by this tool before tagging existed) is adopted
                # (tagged) rather than duplicated.
                candidates = get_existing_instances(family, family_type)
                legacy, _distance = find_nearby_instance(hit_point, candidates, EXISTING_OUTLET_SAME_SPOT_TOLERANCE)
                if legacy is not None:
                    already_placed.append(legacy)
                    to_retag.append((element_int_id(legacy), marker_tag, mount_height, level_name))
                else:
                    to_create.append((target, marker_tag))
                continue

            if not REVIT_SELECTION.is_changable(existing):
                skipped_foreign.append(existing)
                debug_log(
                    "Outlet tagged for marker [{}] is owned by another user; leaving it in place, not "
                    "creating a duplicate or changing it.".format(marker.Id))
                continue

            existing_family_name = REVIT_FAMILY.get_family_name(existing)
            existing_type_name = type_name_of(existing.Symbol)
            existing_point = get_instance_point(existing)
            same_position = (
                existing_point is not None and existing_point.DistanceTo(hit_point) <= EXISTING_OUTLET_SAME_SPOT_TOLERANCE)
            # Height is no longer part of the ray-cast target (see PLACEMENT_HEIGHT_
            # PARAMETER_NAME) -- so same_position alone can no longer tell "nothing to
            # do" apart from "mount_height changed in the marker but the wall/floor
            # target didn't move." Both must match for a true no-op.
            existing_height = get_outlet_placement_height(existing)
            same_height = existing_height is not None and abs(existing_height - mount_height) < 0.001

            if existing_family_name != family.Name:
                to_replace.append((element_int_id(existing), target, marker_tag))
            elif existing_type_name == type_name and same_position and same_height:
                already_placed.append(existing)
            elif existing_type_name == type_name:
                to_update.append((element_int_id(existing), point_tuple, None, marker_tag, mount_height, level_name))
            else:
                to_update.append(
                    (element_int_id(existing), point_tuple, type_name, marker_tag, mount_height, level_name))

        result = apply_marker_outlets(to_create, to_replace, to_update, to_retag)
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


@LOG.log(__file__, __title__)
@ERROR_HANDLE.try_catch_error()
def main(doc):
    place_from_markers(doc)


################## main code below #####################
if __name__ == "__main__":
    main(DOC)
