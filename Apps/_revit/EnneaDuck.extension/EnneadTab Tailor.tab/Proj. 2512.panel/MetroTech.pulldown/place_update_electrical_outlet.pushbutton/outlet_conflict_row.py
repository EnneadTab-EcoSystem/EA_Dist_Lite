"""Plain-data row model for place_update_electrical_outlet_script.py.

Plain data only (ints, strings, floats/tuples) - never a live Revit API element,
since this crosses the resolve/apply boundary inside apply_marker_outlets and is
re-fetched by id there rather than trusted to still be valid.
"""


class OutletPlacementTarget(object):
    """A resolved marker with no existing outlet nearby: safe to place outright.

    `family_name`/`type_name` name the outlet to place here, read from the marker's
    own _para_map (see place_update_electrical_outlet_script.PARA_MAP_TEMPLATE) --
    different markers of the same marker family can each name a different outlet.

    `stable_ref` (a string from DB.Reference.ConvertToStableRepresentation) is set
    for face-based placement and re-parsed back into a live DB.Reference inside the
    apply handler; it is None for wall-hosted (non-face) placement, where only the
    host wall id and point are needed.
    """
    def __init__(self, host_id, point, family_name, type_name, stable_ref=None):
        self.host_id = host_id  # int
        self.point = point  # (x, y, z) plain floats
        self.family_name = family_name
        self.type_name = type_name
        self.stable_ref = stable_ref  # str or None
