
__title__ = "UniformTransformGeos"
__doc__ = "Apply the same rotation and/or uniform scale to blocks or geometries. Helpful when reorienting or resizing many instances, such as changing direction or size of cars on a street."



import rhinoscriptsyntax as rs
import Rhino # pyright: ignore
import Eto # pyright: ignore

from EnneadTab import DATA_FILE, LOG, ERROR_HANDLE
from EnneadTab.RHINO import RHINO_OBJ_DATA


class UniformTransformDialog(Eto.Forms.Dialog[bool]):
    def __init__(self, default_angle, default_scale):
        self.Title = "EnneadTab Uniformly Transform"
        self.Padding = Eto.Drawing.Padding(10)
        self.Resizable = False
        self.MinimumSize = Eto.Drawing.Size(360, 0)

        self.cancelled = True
        self.angle = float(default_angle)
        self.scale = float(default_scale)

        hint = Eto.Forms.Label(
            Text="Rotation is around each block insert point or object center.\n"
            "Scale is uniform XYZ from the same point. Type any number in the fields below."
        )

        self.angle_box = Eto.Forms.TextBox(Text=str(default_angle))
        self.scale_box = Eto.Forms.TextBox(Text=str(default_scale))

        self.error_label = Eto.Forms.Label(Text="")
        self.error_label.TextColor = Eto.Drawing.Colors.Red

        ok_button = Eto.Forms.Button(Text="OK")
        ok_button.Click += self.on_ok_click

        cancel_button = Eto.Forms.Button(Text="Cancel")
        cancel_button.Click += self.on_cancel_click

        layout = Eto.Forms.DynamicLayout()
        layout.Padding = Eto.Drawing.Padding(5)
        layout.Spacing = Eto.Drawing.Size(5, 5)
        layout.AddRow(hint)
        layout.AddSeparateRow(
            Eto.Forms.Label(Text="Rotation (degrees):"),
            self.angle_box,
        )
        layout.AddSeparateRow(
            Eto.Forms.Label(Text="Uniform scale factor (1 = no change):"),
            self.scale_box,
        )
        layout.AddRow(self.error_label)
        layout.AddSeparateRow(None, ok_button, cancel_button)

        self.Content = layout

    def _parse_inputs(self):
        try:
            angle = float(self.angle_box.Text.strip())
            scale = float(self.scale_box.Text.strip())
        except:
            self.error_label.Text = "Enter valid numbers (e.g. 180 and 1.25)."
            return None

        if scale == 0:
            self.error_label.Text = "Scale factor cannot be zero."
            return None

        self.error_label.Text = ""
        return angle, scale

    def on_ok_click(self, sender, e):
        parsed = self._parse_inputs()
        if parsed is None:
            return
        self.angle, self.scale = parsed
        self.cancelled = False
        self.Close(True)

    def on_cancel_click(self, sender, e):
        self.Close(False)


def _prompt_transform_values(default_angle, default_scale):
    dlg = UniformTransformDialog(default_angle, default_scale)
    dlg.ShowModal(Rhino.UI.RhinoEtoApp.MainWindow)
    if dlg.cancelled:
        return None
    return dlg.angle, dlg.scale


@LOG.log(__file__, __title__)
@ERROR_HANDLE.try_catch_error()
def uniform_transform_geos():
    ids = rs.GetObjects("Select block instances or objs to transform", preselect=True)

    if not ids:
        return

    default_angle = DATA_FILE.get_sticky("uniform_transform_angle", 180)
    default_scale = DATA_FILE.get_sticky("uniform_transform_scale", 1.0)

    res = _prompt_transform_values(default_angle, default_scale)
    if res is None:
        return

    ang, scale = res

    DATA_FILE.set_sticky("uniform_transform_angle", ang)
    DATA_FILE.set_sticky("uniform_transform_scale", scale)

    vec = rs.VectorCreate([0, 0, 1], [0, 0, 0])

    rs.EnableRedraw(False)

    for id in ids:
        if rs.IsBlockInstance(id):
            pt = rs.BlockInstanceInsertPoint(id)
        else:
            pt = RHINO_OBJ_DATA.get_center(id)

        if ang != 0:
            rs.RotateObject(id, pt, ang, vec)

        if scale != 1.0:
            rs.ScaleObject(id, pt, [scale, scale, scale], False)


if __name__ == "__main__":
    uniform_transform_geos()
