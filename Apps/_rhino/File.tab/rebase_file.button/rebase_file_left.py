# -*- coding: utf-8 -*-

__title__ = "RebaseFile"
__doc__ = """Rebase file geometry and views to new origin point with X-axis orientation.

Key Features:
- Interactive base point and X-axis reference point selection
- Automatic object transformation with coordinate system reorientation
- View camera adjustment
- Named view preservation
- Comprehensive coordinate system update
- ETO form interface with clear instructions

Instructions:
- Every object, including those in locked and hidden layers, will be processed
- All views will be processed
- To avoid certain objects being rebased, put "REBASE_IGNORE" in the object's name
- To avoid certain cameras being rebased, put "REBASE_IGNORE" in the camera name"""
__is_popular__ = True

import rhinoscriptsyntax as rs
import Rhino # pyright: ignore
import scriptcontext as sc
import Eto.Forms # pyright: ignore
import Eto.Drawing # pyright: ignore

from EnneadTab import ERROR_HANDLE, LOG, SOUND, NOTIFICATION
from EnneadTab.RHINO import RHINO_UI

IGNORE_OBJECT_KEY_NAME = "REBASE_IGNORE"
FORM_KEY = 'REBASE_FILE_modeless_form'


class RebaseFileDialog(Eto.Forms.Form):
    """Modeless dialog for rebasing file geometry and views to new origin with X-axis orientation."""

    def __init__(self):
        """Initialize dialog UI components and default state."""
        # Eto initials
        self.Title = "Rebase File"
        self.Resizable = True
        self.Padding = Eto.Drawing.Padding(10)
        self.Spacing = Eto.Drawing.Size(6, 6)
        self.Width = 500

        self.base_point = None
        self.x_ref_point = None
        self.Closed += self.OnFormClosed

        # Initialize layout
        layout = Eto.Forms.DynamicLayout()
        layout.Padding = Eto.Drawing.Padding(10)
        layout.Spacing = Eto.Drawing.Size(6, 6)

        # Add message
        layout.AddSeparateRow(None, self.CreateLogoImage())
        layout.BeginVertical()
        layout.AddRow(self.CreateMessageBar())
        layout.AddRow(self.CreateInstructions())
        layout.EndVertical()

        # Add point pickers
        layout.BeginVertical()
        layout.AddRow(self.CreatePointPickers())
        layout.EndVertical()

        # Add buttons
        layout.BeginVertical()
        layout.AddRow(*self.CreateButtons())
        layout.EndVertical()

        # Set content
        self.Content = layout
        RHINO_UI.apply_dark_style(self)

    def CreateLogoImage(self):
        """Create and return the logo image view widget."""
        self.logo = Eto.Forms.ImageView()
        return self.logo

    def CreateMessageBar(self):
        """Create and return the message label shown at the top of the dialog."""
        self.msg = Eto.Forms.Label()
        self.msg.Text = "Rebase file geometry and views to new origin with X-axis orientation"
        return self.msg

    def CreateInstructions(self):
        """Create collapsible instructions section."""
        self.expander = Eto.Forms.Expander()
        self.expander.Header = "Instructions"
        self.expander.Expanded = True
        
        instructions_text = """- Every object, including those in locked and hidden layers, will be processed
- All views will be processed
- To avoid certain objects being rebased, put "REBASE_IGNORE" in the object's name
- To avoid certain cameras being rebased, put "REBASE_IGNORE" in the camera name
        
Step 1: Pick the new base point (new origin location)
Step 2: Pick a reference point to define the new X-axis direction
Step 3: Click "Rebase File" to execute the transformation"""
        
        msg = Eto.Forms.Label()
        msg.Text = instructions_text
        self.expander.Content = msg
        return self.expander

    def CreatePointPickers(self):
        """Create controls for picking base point and X-axis reference point."""
        layout = Eto.Forms.DynamicLayout()
        layout.Padding = Eto.Drawing.Padding(5)
        layout.Spacing = Eto.Drawing.Size(5, 5)

        # Base point picker
        base_label = Eto.Forms.Label(Text="Base Point (New Origin):")
        self.pick_base_btn = Eto.Forms.Button(Text="Pick Base Point")
        self.pick_base_btn.Click += self.btn_pick_base_clicked
        self.base_point_label = Eto.Forms.Label(Text="Not selected")
        self.base_point_label.TextColor = Eto.Drawing.Colors.Gray
        
        layout.AddRow(base_label)
        layout.AddRow(self.pick_base_btn, None)
        layout.AddRow(self.base_point_label)

        # X-axis reference point picker
        x_label = Eto.Forms.Label(Text="X-Axis Reference Point:")
        self.pick_x_btn = Eto.Forms.Button(Text="Pick X-Axis Reference")
        self.pick_x_btn.Click += self.btn_pick_x_ref_clicked
        self.x_point_label = Eto.Forms.Label(Text="Not selected")
        self.x_point_label.TextColor = Eto.Drawing.Colors.Gray
        
        layout.AddRow(x_label)
        layout.AddRow(self.pick_x_btn, None)
        layout.AddRow(self.x_point_label)

        return layout

    def CreateButtons(self):
        """Create and return the dialog action buttons."""
        user_buttons = []

        self.btn_rebase = Eto.Forms.Button()
        self.btn_rebase.Text = "Rebase File"
        self.btn_rebase.Height = 40
        self.btn_rebase.Enabled = False
        self.btn_rebase.Click += self.btn_rebase_clicked
        user_buttons.append(self.btn_rebase)

        self.btn_close = Eto.Forms.Button()
        self.btn_close.Text = "Close"
        self.btn_close.Height = 40
        self.btn_close.Click += self.btn_close_clicked
        user_buttons.append(self.btn_close)

        return user_buttons

    def btn_pick_base_clicked(self, sender, e):
        """Handle base point picking button click."""
        point = rs.GetPoint("Pick the new base point (new origin location)")
        if point:
            self.base_point = point
            self.base_point_label.Text = "Base Point: ({:.2f}, {:.2f}, {:.2f})".format(point[0], point[1], point[2])
            self.base_point_label.TextColor = Eto.Drawing.Colors.Green
            self.UpdateRebaseButtonState()

    def btn_pick_x_ref_clicked(self, sender, e):
        """Handle X-axis reference point picking button click."""
        point = rs.GetPoint("Pick a reference point to define the new X-axis direction")
        if point:
            self.x_ref_point = point
            self.x_point_label.Text = "X-Ref Point: ({:.2f}, {:.2f}, {:.2f})".format(point[0], point[1], point[2])
            self.x_point_label.TextColor = Eto.Drawing.Colors.Green
            self.UpdateRebaseButtonState()

    def UpdateRebaseButtonState(self):
        """Enable rebase button only when both points are selected."""
        self.btn_rebase.Enabled = (self.base_point is not None and self.x_ref_point is not None)

    def btn_rebase_clicked(self, sender, e):
        """Handle rebase button click."""
        if self.base_point is None or self.x_ref_point is None:
            NOTIFICATION.messenger("Please select both base point and X-axis reference point first.")
            return

        try:
            processed_objects = rebase_objects(self.base_point, self.x_ref_point)
            processed_views = rebase_views(self.base_point, self.x_ref_point)
            NOTIFICATION.messenger("Rebase file completed.\n{} views moved and {} objects moved.".format(processed_views, processed_objects))
            SOUND.play_sound()
        except Exception as e:
            NOTIFICATION.messenger("Error during rebase: {}".format(str(e)))

    def btn_close_clicked(self, sender, e):
        """Handle close button click."""
        self.Close()

    def OnFormClosed(self, sender, e):
        """Handle form closed event."""
        if sc.sticky.has_key(FORM_KEY):
            del sc.sticky[FORM_KEY]


@LOG.log(__file__, __title__)
@ERROR_HANDLE.try_catch_error()
def rebase_file():
    """Open the rebase file dialog as a modeless UI in Rhino."""
    rs.EnableRedraw(False)
    if sc.sticky.has_key(FORM_KEY):
        return
    dlg = RebaseFileDialog()
    dlg.Owner = Rhino.UI.RhinoEtoApp.MainWindow
    dlg.Show()
    sc.sticky[FORM_KEY] = dlg

def rebase_objects(base_point, x_ref_point):
    # Define reference points (world origin and X-axis)
    target_origin = [0, 0, 0]
    target_x_axis = [1, 0, 0]  # Point along original X-axis
    
    # Define target points (new base and X-axis direction)
    picked_origin = base_point
    picked_x_axis = x_ref_point
    
    # Create reference and target point arrays for OrientObject
    reference_points = [picked_origin, picked_x_axis]
    target_points = [target_origin, target_x_axis]
    
    # Get all objects and orient them
    objects = rs.AllObjects(select=False)
    processed_count = 0
    if objects:
        for obj in objects:
            obj_name = rs.ObjectName(obj)
            if obj_name and isinstance(obj_name, str) and IGNORE_OBJECT_KEY_NAME in obj_name:
                continue
            rs.OrientObject(obj, reference_points, target_points)
            processed_count += 1
    
    rs.Redraw()
    NOTIFICATION.messenger("Rebased {} objects.".format(processed_count))
    return processed_count

def rebase_views(base_point, x_ref_point):
    # Define reference points (world origin and X-axis)
    target_origin = [0, 0, 0]
    target_x_axis = [1, 0, 0]  # Point along original X-axis
    
    # Define target points (new base and X-axis direction)
    picked_origin = base_point
    picked_x_axis = x_ref_point
    
    # Create reference and target point arrays for OrientObject
    reference_points = [picked_origin, picked_x_axis]
    target_points = [target_origin, target_x_axis]

    all_views = rs.NamedViews()
    processed_count = 0

    for view in sorted(all_views, reverse=True):
        if IGNORE_OBJECT_KEY_NAME in view:
            continue
        print("Reorienting view [{}]".format(view))
        rs.RestoreNamedView(view, view=None, restore_bitmap=False)
        current_cam, current_cam_target = rs.ViewCameraTarget(view=view, camera=None, target=None)

        # Create temporary points for camera and target
        temp_cam_pt = rs.AddPoint(current_cam)
        temp_cam_target_pt = rs.AddPoint(current_cam_target)

        # Orient camera and target using the same reference system
        rs.OrientObject(temp_cam_pt, reference_points, target_points)
        rs.OrientObject(temp_cam_target_pt, reference_points, target_points)
        
        # Get the new positions after orientation
        new_cam = rs.PointCoordinates(temp_cam_pt)
        new_cam_target = rs.PointCoordinates(temp_cam_target_pt)
        
        # Set the new camera and target
        rs.ViewCameraTarget(view=view, camera=new_cam, target=new_cam_target)

        rs.AddNamedView(view, view)  # Override existing view

        # Clean up temporary objects
        rs.DeleteObject(temp_cam_pt)
        rs.DeleteObject(temp_cam_target_pt)
        processed_count += 1

    # Redraw the viewport to reflect changes
    rs.Redraw()
    return processed_count

if __name__ == "__main__":
    rebase_file()
