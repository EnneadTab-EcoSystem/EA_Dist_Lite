
__title__ = "SimplifyBlocks"
__doc__ = "This button does SimplifyBlocks when left click"


from EnneadTab import ERROR_HANDLE, LOG
import rhinoscriptsyntax as rs
import Rhino # pyright: ignore
import scriptcontext as sc
import Eto  # pyright: ignore
import time
import traceback

@LOG.log(__file__, __title__)
@ERROR_HANDLE.try_catch_error()
def simplify_blocks():
    percent = get_reduction_percentage()
    if percent is None:
        return

    # Allow user to select multiple block instances; keep one per unique definition
    selected_ids = rs.GetObjects(message = "Select block instances to simplify (one per definition will remain selected)", 
                                 filter = rs.filter.instance, 
                                 select = True)

    if not selected_ids:
        return

    # Map each definition name to the first encountered instance id for reselection
    definition_name_to_instance = {}
    for instance_id in selected_ids:
        try:
            definition_name = rs.BlockInstanceName(instance_id)
        except Exception:
            # Not a valid block instance; skip
            continue

        if not definition_name:
            continue

        if definition_name not in definition_name_to_instance:
            definition_name_to_instance[definition_name] = instance_id

    # For each unique definition name, simplify meshes in the definition itself
    rs.EnableRedraw(False)
    for def_name in list(definition_name_to_instance.keys()):
        start_ts = time.time()
        print("Simplifying block {}".format(def_name))
        before_mesh, before_faces, after_mesh, after_faces = simplify_definition_by_name(def_name, percent)
        elapsed = time.time() - start_ts
        print("Block {} simplified in {:.3f}s | meshes: {} -> {} | faces: {} -> {}".format(def_name, elapsed, before_mesh, after_mesh, before_faces, after_faces))

    # Update Rhino selection: one instance per unique block definition
    rs.UnselectAllObjects()
    rs.SelectObjects(list(definition_name_to_instance.values()))
    if sc.doc:  # pyright: ignore[reportOptionalMemberAccess]
        sc.doc.Views.Redraw()  # pyright: ignore[reportOptionalMemberAccess]


def simplify_definition_by_name(definition_name, percent):
    """Simplify meshes inside a block definition by its name using ModifyGeometry."""
    if not sc.doc:  # pyright: ignore[reportOptionalMemberAccess]
        return 0, 0, 0, 0

    idef = sc.doc.InstanceDefinitions.Find(definition_name, True)  # pyright: ignore[reportOptionalMemberAccess]
    if not idef:
        return 0, 0, 0, 0

    members_arr = idef.GetObjects()
    if not members_arr:
        return 0, 0, 0, 0
    members = [m for m in members_arr or []]  # pyright: ignore[reportGeneralTypeIssues]

    # Compute baseline counts before modification
    before_mesh_count = 0
    before_face_count = 0
    for m in members:
        g0 = m.Geometry
        if isinstance(g0, Rhino.Geometry.Mesh):
            before_mesh_count += 1
            if g0.Faces:
                before_face_count += g0.Faces.Count

    # Tolerances kept for potential future use; Reduction does not require them
    _tol = sc.doc.ModelAbsoluteTolerance  # pyright: ignore[reportOptionalMemberAccess]
    _ang_tol = sc.doc.ModelAngleToleranceRadians  # pyright: ignore[reportOptionalMemberAccess]

    new_geometries = []
    new_attributes = []
    for member in members:
        geometry = member.Geometry
        if geometry is None:
            continue
        geometry = geometry.Duplicate()

        # Reduce only if geometry is already a valid mesh with faces
        if isinstance(geometry, Rhino.Geometry.Mesh):
            # Work on a duplicated mesh object to avoid in-place state issues
            mesh = geometry.DuplicateMesh() if hasattr(geometry, 'DuplicateMesh') else geometry.Duplicate()
            if mesh and mesh.Faces and mesh.Faces.Count > 4 and mesh.IsValid:
                before_faces = mesh.Faces.Count
                # Parameterized reduction (compatible across Rhino versions)
                target_faces = max(4, int(before_faces * max(0, min(100, percent)) / 100.0))
                try:
                    # Precondition mesh for reduction
                    try:
                        if hasattr(mesh, 'Ngons') and mesh.Ngons is not None:
                            mesh.Ngons.Clear()
                    except Exception:
                        pass
                    try:
                        mesh.Faces.ConvertQuadsToTriangles(True, True)
                    except Exception:
                        pass
                    try:
                        mesh.Weld(Rhino.RhinoMath.ToRadians(180.0))
                    except Exception:
                        pass
                    try:
                        mesh.UnifyNormals()
                    except Exception:
                        pass
                    mesh.Compact()

                    if target_faces < before_faces:
                        # Use stable overload: Reduce(target_count, normalize, accuracy, allow_distortion, threaded)
                        ok = mesh.Reduce(target_faces, True, 8, False, True)  # pyright: ignore[reportGeneralTypeIssues]
                        if (not ok) or (mesh.Faces and mesh.Faces.Count >= before_faces):
                            ok = mesh.Reduce(target_faces, True, 10, False, True)  # pyright: ignore[reportGeneralTypeIssues]
                            if (not ok) or (mesh.Faces and mesh.Faces.Count >= before_faces):
                                aggressive_target = max(4, int(before_faces * 0.3))
                                mesh.Reduce(aggressive_target, True, 10, False, True)  # pyright: ignore[reportGeneralTypeIssues]
                    mesh.Compact()
                except Exception:
                    print (traceback.format_exc())
                geometry = mesh

        new_geometries.append(geometry)
        new_attributes.append(member.Attributes.Duplicate())

    # RhinoCommon expects the definition index (int), not the Guid Id
    _ok = sc.doc.InstanceDefinitions.ModifyGeometry(idef.Index, new_geometries, new_attributes)  # pyright: ignore[reportOptionalMemberAccess]

    # Re-read from definition to confirm persisted result
    idef_after = sc.doc.InstanceDefinitions.Find(definition_name, True)  # pyright: ignore[reportOptionalMemberAccess]
    after_mesh_count = 0
    after_face_count = 0
    if idef_after:
        members_after_arr = idef_after.GetObjects()
        members_after = [m for m in members_after_arr or []]  # pyright: ignore[reportGeneralTypeIssues]
        for m in members_after:
            g1 = m.Geometry
            if isinstance(g1, Rhino.Geometry.Mesh):
                after_mesh_count += 1
                if g1.Faces:
                    after_face_count += g1.Faces.Count

    return before_mesh_count, before_face_count, after_mesh_count, after_face_count


class ReductionDialog(Eto.Forms.Dialog):  # pyright: ignore[reportUnknownVariableType]
    def __init__(self):
        self.Title = "Block Mesh Reduction"
        self.Resizable = False
        self.Padding = Eto.Drawing.Padding(10)
        self.Spacing = Eto.Drawing.Size(6, 6)
        self.result_value = 50.0

        self.slider = Eto.Forms.Slider()
        self.slider.MinValue = 1
        self.slider.MaxValue = 100
        self.slider.Value = 50

        self.value_label = Eto.Forms.Label(Text = "{}%".format(self.slider.Value))
        self.slider.ValueChanged += self.on_value_changed

        ok_btn = Eto.Forms.Button(Text = "OK")
        cancel_btn = Eto.Forms.Button(Text = "Cancel")
        ok_btn.Click += self.on_ok
        cancel_btn.Click += self.on_cancel

        layout = Eto.Forms.DynamicLayout()
        layout.Padding = Eto.Drawing.Padding(5)
        layout.Spacing = Eto.Drawing.Size(6, 6)
        layout.BeginVertical()
        layout.AddRow(Eto.Forms.Label(Text = "Target face percentage"))
        layout.AddRow(self.slider, self.value_label)
        layout.AddRow(None)
        layout.AddRow(None, ok_btn, cancel_btn)
        layout.EndVertical()
        self.Content = layout

    def on_value_changed(self, sender, e):
        self.value_label.Text = "{}%".format(self.slider.Value)

    def on_ok(self, sender, e):
        try:
            self.result_value = float(self.slider.Value)
        except Exception:
            self.result_value = 50.0
        self.Close()

    def on_cancel(self, sender, e):
        self.result_value = None
        self.Close()


def get_reduction_percentage():
    dlg = ReductionDialog()
    dlg.ShowModal(Rhino.UI.RhinoEtoApp.MainWindow)  # pyright: ignore[reportUnknownArgumentType]
    try:
        return float(dlg.result_value) if dlg.result_value is not None else None
    except Exception:
        return None

if __name__ == "__main__":
    simplify_blocks()
