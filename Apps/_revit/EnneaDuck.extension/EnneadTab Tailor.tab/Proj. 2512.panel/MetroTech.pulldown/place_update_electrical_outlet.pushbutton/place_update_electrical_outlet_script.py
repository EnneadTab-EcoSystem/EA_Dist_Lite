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
- Furniture families can carry a nested position marker, in the current model or a
  linked one; this tool finds every marker of that family, fans rays outward to the
  nearest wall/floor (the marker carries position only, no dependable facing
  rotation to aim a single ray), and places or updates the matching outlet in the
  current model
- The outlet family/type you pick for a marker family can be locked in and shared
  with the whole project team, so nobody has to re-pick it on future runs
- An outlet already sitting near a marker is never deleted: a review grid lists
  every conflict (level, family, type, reason) so you can Keep or Move each one,
  with a Zoom button and Previous/Next navigation to inspect it in the model first
- Existing outlet instances of a type can be swapped to a different type in one pass
- Instances owned by another user in a workshared model are skipped, never changed

Usage:
1. Run the button and choose Place, Place From Marker, or Update Type
2. Place: pick a family and type, then click faces/walls until you press Escape
3. Place From Marker: pick one sample position marker, then pick the outlet
   family/type (or reuse/replace a locked-in choice from a previous run).
   Markers with no outlet nearby are placed once you Apply; markers with an outlet
   already nearby open a review grid first (Zoom, Previous/Next, Keep/Move per row)
4. Update Type: pick the family, current type, new type, then confirm"""
__title__ = "Place/Update\nElectrical Outlet"

import math

import proDUCKtion  # pyright: ignore
proDUCKtion.validify()

from Autodesk.Revit import DB  # pyright: ignore
from Autodesk.Revit.UI import IExternalEventHandler, ExternalEvent  # pyright: ignore
from Autodesk.Revit.UI.Selection import ObjectType, ISelectionFilter  # pyright: ignore
from Autodesk.Revit.Exceptions import OperationCanceledException, InvalidOperationException  # pyright: ignore
from System.Collections.Generic import List  # pyright: ignore
from pyrevit.forms import WPFWindow

from EnneadTab import DATA_FILE, ERROR_HANDLE, LOG, NOTIFICATION
from EnneadTab.REVIT import REVIT_APPLICATION, REVIT_SELECTION, REVIT_FORMS, REVIT_FAMILY

from outlet_conflict_row import OutletConflictRow, OutletPlacementTarget, ACTION_OPTIONS

UIDOC = REVIT_APPLICATION.get_uidoc()
DOC = REVIT_APPLICATION.get_doc()
__persistentengine__ = True

# Maps a nested position-marker family's name to the outlet (family name, type name)
# to place at every marker of that name. Checked first, ahead of anything locked in
# via the tool's own UI (below); edit this dict and commit it when a mapping should
# be a permanent, project-wide default for every user, not just remembered on one
# machine. Same convention as furring_constants.TARGET_PANEL_FAMILIES in the Sparc
# (2412) Tailor tools.
MARKER_TO_OUTLET_KEY_MAP = {
    # "EA_OutletPositionMarker": ("EA_Electrical_Outlet", "Duplex - Wall"),
}

# Shared, project-wide storage for outlet choices locked in via the "Lock This
# Outlet Choice?" prompt (see resolve_outlet_type_for_marker_family). Backed by
# EnneadTab.DATA_FILE's DEPOT-backed shared state (DATA_FILE.*(..., is_local=False)),
# the same cloud config store REVIT_PROJ_DATA and temporary_revision use - it syncs
# to every team member, not just the machine that locked it in, keyed per Revit
# document (doc.Title) so different projects/models never collide.
# {marker_family_name: [outlet_family_name, outlet_type_name]}.
SHARED_OUTLET_MAP_KEY_PREFIX = "MetroTechOutletMarkerMap_"

# The marker family carries position only, no dependable facing rotation, so the
# host wall/floor is found with a fan of rays cast outward from the marker point
# rather than trusting one axis of its orientation. Horizontal rays (evenly spaced
# around a full circle) cover walls; a straight-down and straight-up ray cover
# floors, which the horizontal fan alone would never hit.
MARKER_RAYCAST_FAN_COUNT = 16  # horizontal rays in the fan; higher = finer angular coverage

MARKER_RAYCAST_MAX_DISTANCE = 3.0  # feet; how far to ray-cast to find a host face
EXISTING_OUTLET_SEARCH_RADIUS = 1.0  # feet; how close counts as "already at this marker"
EXISTING_OUTLET_SAME_SPOT_TOLERANCE = 0.05  # feet; close enough to skip as a no-op


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


def find_host_face_along_ray(doc, view3d, point, direction):
    """Ray-cast from `point` along `direction` for the nearest wall/floor face.

    Returns:
        tuple (DB.Element host, DB.Face face, DB.XYZ hit_point, str stable_ref), or
        (None, None, None, None) when nothing is hit within MARKER_RAYCAST_MAX_DISTANCE.
        `stable_ref` is the Reference's stable representation, so the exact face can
        be re-resolved later (via DB.Reference.ParseFromStableRepresentation) without
        holding the live Face/Reference object across a modeless dialog's idle time.
    """
    categories = List[DB.BuiltInCategory]([DB.BuiltInCategory.OST_Walls, DB.BuiltInCategory.OST_Floors])
    multi_filter = DB.ElementMulticategoryFilter(categories)
    intersector = DB.ReferenceIntersector(multi_filter, DB.FindReferenceTarget.Face, view3d)
    intersector.FindReferencesInRevitLinks = False
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


def find_nearest_host_face(doc, view3d, point):
    """Cast a fan of rays outward from `point` and return the nearest wall/floor hit.

    The marker only carries a position, not a dependable facing rotation, so the
    direction to the host wall/floor cannot be read off its orientation the way a
    single trusted axis would. Trying every direction in the fan and keeping the
    globally nearest hit finds the host regardless of which way the marker sits.

    Returns:
        tuple (DB.Element host, DB.Face face, DB.XYZ hit_point, str stable_ref), or
        (None, None, None, None) when nothing is hit within MARKER_RAYCAST_MAX_DISTANCE
        in any direction.
    """
    best = None
    best_distance = None
    for direction in build_fan_directions(MARKER_RAYCAST_FAN_COUNT):
        host, face, hit_point, stable_ref = find_host_face_along_ray(doc, view3d, point, direction)
        if host is None:
            continue
        distance = point.DistanceTo(hit_point)
        if best_distance is None or distance < best_distance:
            best = (host, face, hit_point, stable_ref)
            best_distance = distance
    return best if best is not None else (None, None, None, None)


def resolve_marker_targets(doc, marker_family_name, view3d, marker_doc=None, link_transform=None):
    """Find every instance of `marker_family_name`, and fan-cast each to its host face.

    `marker_doc` is searched for marker instances (defaults to `doc`, the current/host
    document); pass the linked document here when the markers live in a link.
    `link_transform` (a link instance's total transform) maps each marker's point from
    link-local space into host-doc space before casting, since the ray-cast and every
    downstream placement always target the CURRENT (host) document's walls/floors --
    never the link's -- regardless of where the marker itself lives.

    Returns:
        tuple (resolved, unresolved):
          resolved   -- list of (marker, host, face, hit_point, stable_ref)
          unresolved -- list of (marker, reason) for markers with no host hit
    """
    marker_doc = marker_doc or doc
    markers = REVIT_FAMILY.get_shared_nested_instances_by_family_name(marker_family_name, doc=marker_doc)
    resolved = []
    unresolved = []
    for marker in markers:
        point, _orientation = REVIT_FAMILY.get_nested_instance_placement(marker, host_transform=link_transform)
        if point is None:
            unresolved.append((marker, "no location available"))
            continue
        host, face, hit_point, stable_ref = find_nearest_host_face(doc, view3d, point)
        if host is None:
            unresolved.append((marker, "no wall/floor within {} ft in any direction".format(
                MARKER_RAYCAST_MAX_DISTANCE)))
            continue
        resolved.append((marker, host, face, hit_point, stable_ref))
    return resolved, unresolved


def shared_outlet_map_key(doc):
    return "{}{}".format(SHARED_OUTLET_MAP_KEY_PREFIX, doc.Title)


def get_shared_outlet_map(doc):
    """Read the project-wide locked-choice map. Depot-backed (see
    SHARED_OUTLET_MAP_KEY_PREFIX); returns {} if depot is unreachable or nothing
    has been locked in yet for this document."""
    return DATA_FILE.get_data(shared_outlet_map_key(doc), is_local=False) or {}


def lock_outlet_choice(doc, marker_family_name, outlet_family_name, outlet_type_name):
    """Write one marker->outlet mapping into the shared, project-wide map.

    Uses DATA_FILE.update_data's read-modify-write so a second person locking a
    different marker family around the same time never clobbers this entry (each
    write re-reads the live shared dict rather than reusing a copy read earlier in
    the run).
    """
    with DATA_FILE.update_data(shared_outlet_map_key(doc), is_local=False) as data:
        data[marker_family_name] = [outlet_family_name, outlet_type_name]


def resolve_outlet_type_for_marker_family(doc, marker_family_name, cache):
    """Resolve which outlet family/type to use for a marker family, once per marker
    family per run (cached in `cache`).

    Priority: MARKER_TO_OUTLET_KEY_MAP (code-level, project-wide, git-tracked) ->
    a choice locked in earlier via this tool's own UI (shared with the whole
    project team through DEPOT-backed cloud storage, see SHARED_OUTLET_MAP_KEY_PREFIX)
    -> an interactive family/type pick, which then offers to lock itself in for
    the rest of the team.
    """
    if marker_family_name in cache:
        return cache[marker_family_name]

    mapped = MARKER_TO_OUTLET_KEY_MAP.get(marker_family_name)
    if mapped:
        outlet_family_name, outlet_type_name = mapped
        family = REVIT_FAMILY.get_family_by_name(outlet_family_name, doc=doc)
        family_type = REVIT_FAMILY.get_family_type_by_name(outlet_family_name, outlet_type_name, doc=doc) if family else None
        if family and family_type:
            cache[marker_family_name] = (family, family_type)
            return cache[marker_family_name]
        NOTIFICATION.messenger(
            "MARKER_TO_OUTLET_KEY_MAP points [{}] at [{}] - [{}], but that family/type "
            "isn't loaded. Pick one instead.".format(marker_family_name, outlet_family_name, outlet_type_name))

    shared_map = get_shared_outlet_map(doc)
    locked = shared_map.get(marker_family_name)
    if locked:
        outlet_family_name, outlet_type_name = locked
        family = REVIT_FAMILY.get_family_by_name(outlet_family_name, doc=doc)
        family_type = REVIT_FAMILY.get_family_type_by_name(outlet_family_name, outlet_type_name, doc=doc) if family else None
        if family and family_type:
            choice = REVIT_FORMS.dialogue(
                main_text="Use Locked Outlet Choice?",
                sub_text="Marker [{}] was locked to outlet [{}] - [{}] for this project "
                         "(shared with the whole team).".format(
                    marker_family_name, outlet_family_name, outlet_type_name),
                options=["Use Locked Choice", "Pick Different", "Cancel"])
            if choice == "Use Locked Choice":
                cache[marker_family_name] = (family, family_type)
                return cache[marker_family_name]
            if choice == "Cancel" or not choice:
                cache[marker_family_name] = (None, None)
                return cache[marker_family_name]
            # "Pick Different" falls through to the interactive pick below.
        else:
            NOTIFICATION.messenger(
                "Locked outlet [{}] - [{}] for marker [{}] is no longer loaded; pick again.".format(
                    outlet_family_name, outlet_type_name, marker_family_name))

    NOTIFICATION.messenger("Pick the outlet family/type to use for marker [{}]".format(marker_family_name))
    family = REVIT_SELECTION.pick_family(doc, include_2D=False, include_3D=True)
    family_type = REVIT_SELECTION.pick_type(family) if family else None
    if not (family and family_type):
        cache[marker_family_name] = (None, None)
        return cache[marker_family_name]

    lock_it = REVIT_FORMS.dialogue(
        main_text="Lock This Outlet Choice?",
        sub_text="Remember [{}] - [{}] for marker [{}] for the whole project team, so "
                 "this tool won't ask again next time (anyone on this project)?".format(
                     family.Name, type_name_of(family_type), marker_family_name),
        options=["Lock It In", "Just This Once"])
    if lock_it == "Lock It In":
        lock_outlet_choice(doc, marker_family_name, family.Name, type_name_of(family_type))
        NOTIFICATION.messenger(
            "Locked for the project: marker [{}] -> outlet [{}] - [{}]. Pick 'Pick "
            "Different' next run to change it.".format(marker_family_name, family.Name, type_name_of(family_type)))

    cache[marker_family_name] = (family, family_type)
    return cache[marker_family_name]


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


def apply_marker_outlets(to_place, conflict_rows, outlet_family_name, outlet_type_name):
    """Place new outlets and apply the reviewed Keep/Move decisions, in one transaction.

    Runs in API context via ExternalEvent. Re-resolves the outlet family/type and
    every element by id here, rather than trusting anything held on the WPF window,
    since none of that is guaranteed still valid after however long the modeless
    review grid stayed open.
    """
    doc = DOC
    family = REVIT_FAMILY.get_family_by_name(outlet_family_name, doc=doc)
    family_type = REVIT_FAMILY.get_family_type_by_name(outlet_family_name, outlet_type_name, doc=doc) if family else None
    if not family or not family_type:
        return "Outlet family/type [{}] - [{}] is no longer loaded; nothing applied.".format(
            outlet_family_name, outlet_type_name)

    placed = 0
    moved = 0
    kept = 0
    failed = []
    t = DB.Transaction(doc, "Place/Update Electrical Outlet From Marker - {}".format(outlet_family_name))
    t.Start()
    try:
        for item in to_place:
            try:
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
                else:
                    failed.append(item.host_id)
            except Exception as e:
                ERROR_HANDLE.print_note("Failed to place outlet on host [{}]: {}".format(item.host_id, e))
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
            except Exception as e:
                ERROR_HANDLE.print_note("Failed to move outlet [{}]: {}".format(row.existing_instance_id, e))
                failed.append(row.existing_instance_id)
        t.Commit()
    except Exception:
        t.RollBack()
        raise

    lines = ["Placed {} | Moved {} | Kept {}".format(placed, moved, kept)]
    if failed:
        lines.append("Failed on {} item(s), see output for detail.".format(len(failed)))
    NOTIFICATION.messenger(main_text="\n".join(lines))
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

    def __init__(self, to_place, conflict_rows, outlet_family_name, outlet_type_name, marker_family_name):
        self.pre_actions()
        WPFWindow.__init__(self, "OutletConflictReview.xaml")
        self.Title = "EnneadTab Outlet Marker Review"
        self._form_closed = False
        self._navigating = False
        self.current_index = -1
        self._to_place = to_place
        self._outlet_family_name = outlet_family_name
        self._outlet_type_name = outlet_type_name
        self._marker_family_name = marker_family_name
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
        self.apply_handler.kwargs = (
            self._to_place, rows, self._outlet_family_name, self._outlet_type_name)
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


def resolve_picked_marker(doc, ref):
    """Resolve a PickObject Reference to the marker it points at, whether picked
    directly in `doc` or drilled (Tab) into a linked model instance.

    Picking through into a link is standard PickObject(ObjectType.Element,...)
    behavior: `ref.ElementId` is then the RevitLinkInstance's id in `doc`, and
    `ref.LinkedElementId` is the marker's id inside the link's own document.

    Returns:
        tuple (DB.Element marker, DB.Document marker_doc, DB.Transform link_transform)
        `link_transform` is None for a marker picked directly in `doc`.
    """
    picked = doc.GetElement(ref.ElementId)
    if isinstance(picked, DB.RevitLinkInstance) and ref.LinkedElementId != DB.ElementId.InvalidElementId:
        link_doc = picked.GetLinkDocument()
        marker = link_doc.GetElement(ref.LinkedElementId) if link_doc else None
        return marker, link_doc, picked.GetTotalTransform()
    return picked, doc, None


def place_from_markers(doc):
    marker_selection_filter = None  # any category: a shared nested marker can be Generic Model or similar
    try:
        ref = UIDOC.Selection.PickObject(
            ObjectType.Element, marker_selection_filter,
            "Pick one sample position marker nested inside a furniture family "
            "(Tab to pick one nested inside a linked model)")
    except OperationCanceledException:
        return
    marker_example, marker_doc, link_transform = resolve_picked_marker(doc, ref)
    if marker_example is None or marker_doc is None:
        NOTIFICATION.messenger("Could not resolve the picked element to a marker (broken or unloaded link?).")
        return
    marker_family_name = REVIT_FAMILY.get_family_name(marker_example)
    if not marker_family_name:
        NOTIFICATION.messenger("Could not read a family name from the picked element.")
        return

    view3d = get_any_3d_view(doc)
    if view3d is None:
        NOTIFICATION.messenger("No 3D view available and none could be created; cannot ray-cast to a host face.")
        return

    resolved, unresolved = resolve_marker_targets(
        doc, marker_family_name, view3d, marker_doc=marker_doc, link_transform=link_transform)
    marker_doc_label = "[{}] ".format(marker_doc.Title) if link_transform is not None else ""
    for marker, reason in unresolved:
        print("Marker {}{}: {}".format(marker_doc_label, marker.Id, reason))
    if not resolved:
        NOTIFICATION.messenger(
            "Found {} marker(s) of [{}], but none resolved to a nearby wall/floor.".format(
                len(unresolved), marker_family_name))
        return

    type_cache = {}
    family, family_type = resolve_outlet_type_for_marker_family(doc, marker_family_name, type_cache)
    if not family or not family_type:
        return

    existing_instances = REVIT_FAMILY.get_family_instances_by_family_name_and_type_name(
        family.Name, type_name_of(family_type), doc=doc, editable_only=True)

    placement_type = family.FamilyPlacementType
    if placement_type not in (DB.FamilyPlacementType.WorkPlaneBased, DB.FamilyPlacementType.OneLevelBasedHosted):
        NOTIFICATION.messenger(
            "[{}] is neither a face-based nor a wall-hosted family. "
            "Use a Face Based or Wall Based outlet family with this tool.".format(family.Name))
        return

    to_place = []        # OutletPlacementTarget - no existing outlet nearby
    already_placed = []  # existing instance, no action needed
    conflict_rows = []   # OutletConflictRow - needs a per-row review decision
    for marker, host, face, hit_point, stable_ref in resolved:
        nearby, distance = find_nearby_instance(hit_point, existing_instances, EXISTING_OUTLET_SEARCH_RADIUS)
        point_tuple = (hit_point.X, hit_point.Y, hit_point.Z)
        if nearby is None:
            use_stable_ref = stable_ref if placement_type == DB.FamilyPlacementType.WorkPlaneBased else None
            to_place.append(OutletPlacementTarget(element_int_id(host), point_tuple, use_stable_ref))
        elif distance <= EXISTING_OUTLET_SAME_SPOT_TOLERANCE:
            already_placed.append(nearby)
        else:
            conflict_rows.append(OutletConflictRow(
                element_int_id(nearby), get_level_name(nearby, doc),
                family.Name, type_name_of(family_type), distance, point_tuple))

    if not conflict_rows:
        # Nothing to review case by case: place everything right away, same as
        # the direct Place mode.
        res = apply_marker_outlets(to_place, [], family.Name, type_name_of(family_type))
        lines = ["Marker family: [{}]".format(marker_family_name), res]
        if already_placed:
            lines.append("{} outlet(s) already sat exactly on their marker, left untouched".format(len(already_placed)))
        if unresolved:
            lines.append("{} marker(s) had no wall/floor within reach, skipped".format(len(unresolved)))
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
        lines.append("{} marker(s) had no wall/floor within reach, skipped.".format(len(unresolved)))
    NOTIFICATION.messenger(" ".join(lines))
    OutletConflictReviewWindow(to_place, conflict_rows, family.Name, type_name_of(family_type), marker_family_name)


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
