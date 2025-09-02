
__title__ = "ViewBlockDiagram"
__doc__ = "This button does ViewBlockDiagram when left click"


from EnneadTab import ERROR_HANDLE, LOG
import math
import rhinoscriptsyntax as rs
import scriptcontext as sc
import Rhino
try:
    import Eto.Forms as forms
    import Eto.Drawing as drawing
except Exception:
    forms = None
    drawing = None

# Global sampling resolution (number of rays over 360 degrees)
RESOLUTION = 360
SETTINGS_SECTION = "ViewBlockDiagram"
SETTINGS_KEYS = {
    "resolution": "resolution",
    "ray_length": "ray_length",
}

@LOG.log(__file__, __title__)
@ERROR_HANDLE.try_catch_error()
def _select_obstacles():
    # Use no filter to avoid stub errors; we'll accept any and extract geometry later
    ids = rs.GetObjects("Select obstacle objects", preselect=True, select=True)
    return ids or []


def _pick_viewer_point():
    return rs.GetPoint("Pick viewer point (XY plane)")


def _load_settings(default_resolution, default_length):
    # Try Rhino document user text first
    res_val = rs.GetDocumentUserText(SETTINGS_SECTION + ":" + SETTINGS_KEYS["resolution"]) or ""
    len_val = rs.GetDocumentUserText(SETTINGS_SECTION + ":" + SETTINGS_KEYS["ray_length"]) or ""
    try:
        res_loaded = int(res_val) if res_val else default_resolution
    except Exception:
        res_loaded = default_resolution
    try:
        len_loaded = float(len_val) if len_val else default_length
    except Exception:
        len_loaded = default_length

    # Fallback to sticky memory if available
    res_loaded = int(sc.sticky.get(SETTINGS_SECTION + ":" + SETTINGS_KEYS["resolution"], res_loaded))
    len_loaded = float(sc.sticky.get(SETTINGS_SECTION + ":" + SETTINGS_KEYS["ray_length"], len_loaded))
    return res_loaded, len_loaded


def _save_settings(resolution, length):
    key_res = SETTINGS_SECTION + ":" + SETTINGS_KEYS["resolution"]
    key_len = SETTINGS_SECTION + ":" + SETTINGS_KEYS["ray_length"]
    rs.SetDocumentUserText(key_res, str(int(resolution)))
    rs.SetDocumentUserText(key_len, str(float(length)))
    sc.sticky[key_res] = int(resolution)
    sc.sticky[key_len] = float(length)


def _apply_dark_theme(widget):
    if drawing is None:
        return
    try:
        bg = drawing.Color.FromArgb(30, 30, 30)
        fg = drawing.Color.FromArgb(230, 230, 230)
        if hasattr(widget, 'BackgroundColor'):
            widget.BackgroundColor = bg
        if hasattr(widget, 'TextColor'):
            widget.TextColor = fg
        if isinstance(widget, forms.Container):
            for child in widget.Children:
                _apply_dark_theme(child)
    except Exception:
        pass


def _get_options_with_eto(default_resolution, default_length):
    if forms is None:
        return default_resolution, default_length

    class OptionsDialog(forms.Dialog[bool]):
        def __init__(self):
            super(OptionsDialog, self).__init__()
            self.Title = "View Block Diagram Options"
            self.Padding = drawing.Padding(10)
            self.Resizable = False

            loaded_res, loaded_len = _load_settings(default_resolution, default_length)

            self.resolution_updown = forms.NumericUpDown()
            self.resolution_updown.DecimalPlaces = 0
            self.resolution_updown.MinValue = 3
            self.resolution_updown.MaxValue = 4096
            self.resolution_updown.Value = loaded_res

            self.length_updown = forms.NumericUpDown()
            self.length_updown.DecimalPlaces = 1
            self.length_updown.MinValue = 1.0
            self.length_updown.MaxValue = 1e6
            self.length_updown.Value = loaded_len

            layout = forms.DynamicLayout()
            layout.Spacing = drawing.Size(6, 6)
            lbl1 = forms.Label(Text="Resolution (rays)")
            lbl2 = forms.Label(Text="Ray length")
            layout.AddRow(lbl1, self.resolution_updown)
            layout.AddRow(lbl2, self.length_updown)

            ok_button = forms.Button(Text="OK")
            cancel_button = forms.Button(Text="Cancel")
            ok_button.Click += self._on_ok
            cancel_button.Click += self._on_cancel

            layout.AddSeparateRow(None, ok_button, cancel_button, None)
            self.Content = layout

            _apply_dark_theme(self)

        def _on_ok(self, sender, e):
            self.Close(True)

        def _on_cancel(self, sender, e):
            self.Close(False)

    dlg = OptionsDialog()
    rc = dlg.ShowModal(Rhino.UI.RhinoEtoApp.MainWindow)
    if rc:
        res = int(dlg.resolution_updown.Value)
        length = float(dlg.length_updown.Value)
        _save_settings(res, length)
        return res, length
    return None, None


def _build_geometry_list(obstacle_ids):
    geometries = []
    for obj_id in obstacle_ids:
        rh_obj = sc.doc.Objects.Find(obj_id) if sc.doc else None
        if rh_obj is None:
            continue
        geo = rh_obj.Geometry
        if isinstance(geo, Rhino.Geometry.Extrusion):
            brep = geo.ToBrep()
            if brep:
                geometries.append(brep)
            continue
        if isinstance(geo, (Rhino.Geometry.Brep, Rhino.Geometry.Surface, Rhino.Geometry.Mesh)):
            geometries.append(geo)
    return geometries


def _cast_rays(origin, sample_count, ray_length, geometry_list):
    good_flags = []
    end_points = []
    two_pi = math.pi * 2.0
    for i in range(sample_count):
        angle = two_pi * float(i) / float(sample_count)
        direction = Rhino.Geometry.Vector3d(math.cos(angle), math.sin(angle), 0.0)
        direction.Unitize()
        ray = Rhino.Geometry.Ray3d(origin, direction)
        hits = Rhino.Geometry.Intersect.Intersection.RayShoot(geometry_list, ray, 1)
        # Only consider Point3d[] results; any hit -> bad
        count = len(hits) if hits is not None else 0
        is_good = (count == 0)
        good_flags.append(is_good)
        end_points.append(origin + direction * ray_length)
    return good_flags, end_points


def _create_lofts_between_adjacent_good_rays(origin, good_flags, end_points):
    added = []
    count = len(good_flags)
    for i in range(count):
        j = (i + 1) % count
        if not (good_flags[i] and good_flags[j]):
            continue
        crv1 = Rhino.Geometry.Line(origin, end_points[i]).ToNurbsCurve()
        crv2 = Rhino.Geometry.Line(origin, end_points[j]).ToNurbsCurve()
        breps = Rhino.Geometry.Brep.CreateFromLoft([crv1, crv2], Rhino.Geometry.Point3d.Unset, Rhino.Geometry.Point3d.Unset, Rhino.Geometry.LoftType.Normal, False)
        if breps:
            for b in breps:
                obj_id = sc.doc.Objects.AddBrep(b) if sc.doc else None
                if obj_id:
                    added.append(obj_id)
    return added


@LOG.log(__file__, __title__)
@ERROR_HANDLE.try_catch_error()
def view_block_diagram():
    obstacle_ids = _select_obstacles()
    if not obstacle_ids:
        return

    viewer_point = _pick_viewer_point()
    if viewer_point is None:
        return

    # Use global resolution unless overridden by user via ETO form
    default_length = 1000.0
    res, length = _get_options_with_eto(RESOLUTION, default_length)
    if res is None or length is None:
        res = RESOLUTION
        length = default_length

    geos = _build_geometry_list(obstacle_ids)
    if not geos:
        rs.MessageBox("No valid geometry for ray casting.")
        return

    origin = Rhino.Geometry.Point3d(viewer_point.X, viewer_point.Y, viewer_point.Z)
    good_flags, end_points = _cast_rays(origin, res, length, geos)
    added_ids = _create_lofts_between_adjacent_good_rays(origin, good_flags, end_points)

    if sc.doc:
        sc.doc.Views.Redraw()
    # Keep logging simple to avoid API mismatches in linter
    print("Created {} lofts between adjacent good rays".format(len(added_ids)))

    
if __name__ == "__main__":
    view_block_diagram()
