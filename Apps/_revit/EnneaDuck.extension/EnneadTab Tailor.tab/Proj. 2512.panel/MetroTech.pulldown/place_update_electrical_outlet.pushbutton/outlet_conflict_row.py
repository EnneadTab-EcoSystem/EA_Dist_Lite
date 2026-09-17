"""Row model for the outlet-conflict review grid.

Plain data only (ints, strings, floats/tuples) - see CLAUDE.md's "Modeless
WPF DataGrid forms" checklist: never store a Revit API element on a row
object the DataGrid selects, since WPF's selection machinery can call
GetHashCode/ToString/property-enumeration on it outside the API context.
The window re-fetches by id inside an ExternalEvent handler at apply time.
"""

ACTION_OPTIONS = ["Keep", "Move"]


class OutletConflictRow(object):
    def __init__(self, existing_instance_id, level_name, family_name, type_name,
                 distance, target_point):
        self.existing_instance_id = existing_instance_id  # int
        self.level_name = level_name or "?"
        self.family_name = family_name
        self.type_name = type_name
        self.distance = distance
        self.reason = "{:.2f} ft from marker position".format(distance)
        self.target_point = target_point  # (x, y, z) plain floats, never a DB.XYZ
        self.action = "Keep"

    def __repr__(self):
        # Plain string only, so WPF's ToString on the selected item can never
        # touch the API (same rule as FamilyRenameRow).
        return "OutletConflictRow({} / {} - {})".format(
            self.level_name, self.family_name, self.type_name)


class OutletPlacementTarget(object):
    """A resolved marker with no existing outlet nearby: safe to place outright.

    `stable_ref` (a string from DB.Reference.ConvertToStableRepresentation) is set
    for face-based placement and re-parsed back into a live DB.Reference inside the
    apply handler; it is None for wall-hosted (non-face) placement, where only the
    host wall id and point are needed.
    """
    def __init__(self, host_id, point, stable_ref=None):
        self.host_id = host_id  # int
        self.point = point  # (x, y, z) plain floats
        self.stable_ref = stable_ref  # str or None
