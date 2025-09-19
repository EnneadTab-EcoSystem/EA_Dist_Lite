
# -*- coding: utf-8 -*-

__title__ = "ViewBlockDiagram"
__doc__ = """Generate view block diagrams by casting rays from a viewer point to identify unobstructed view areas.

This tool creates 3D surfaces representing the visible areas from a specified viewer point, 
taking into account obstacles that block the view rays. Perfect for:
- Site analysis and view studies
- Building massing and urban planning
- Landscape design and sightline analysis
- Solar access and shadow studies

The process involves:
1. Configuring ray casting parameters (resolution and ray length)
2. Selecting obstacle objects that block the view
3. Picking a viewer point location
4. Automatic generation of view block surfaces

The tool automatically groups consecutive unobstructed rays and creates 
bounded surfaces using arcs and radius lines for accurate representation."""


from EnneadTab import ERROR_HANDLE, LOG, DATA_FILE
from EnneadTab.RHINO import RHINO_UI
import math
import os
import rhinoscriptsyntax as rs
import scriptcontext as sc
import Rhino
import System
import Eto.Forms
import Eto.Drawing

SETTINGS_SECTION = "ViewBlockDiagram"





# Default settings dictionary
DEFAULT_SETTINGS = {
    "resolution": 1000,
    "ray_length": 1000.0
}

def _get_settings():
    """Get current settings with defaults"""
    settings = DATA_FILE.get_data(SETTINGS_SECTION, is_local=True) or {}
    return {
        "resolution": int(settings.get("resolution", DEFAULT_SETTINGS["resolution"])),
        "ray_length": float(settings.get("ray_length", DEFAULT_SETTINGS["ray_length"]))
    }

def _save_settings(settings_dict):
    """Save settings to DATA_FILE"""
    DATA_FILE.set_data(settings_dict, SETTINGS_SECTION, is_local=True)








class OptionsDialog(Eto.Forms.Dialog[bool]):
        def __init__(self):
            super(OptionsDialog, self).__init__()
            self.Title = "View Block Diagram"
            self.Padding = Eto.Drawing.Padding(5)
            self.Resizable = True
            self.Width = 600

            settings = _get_settings()
            loaded_res = settings["resolution"]
            loaded_len = settings["ray_length"]
            
            # Initialize selections as empty
            self.selected_obstacles = []
            self.selected_viewer_point = None
            
            # Create labels
            self.obstacle_label = Eto.Forms.Label(Text="No obstacles selected")
            self.viewer_point_label = Eto.Forms.Label(Text="No viewer point selected")

            self.resolution_updown = Eto.Forms.NumericUpDown()
            self.resolution_updown.DecimalPlaces = 0
            self.resolution_updown.MinValue = 3
            self.resolution_updown.MaxValue = 4096
            self.resolution_updown.Value = loaded_res
            self.resolution_updown.Width = 120
            self.resolution_updown.Height = 25

            self.length_updown = Eto.Forms.NumericUpDown()
            self.length_updown.DecimalPlaces = 1
            self.length_updown.MinValue = 1.0
            self.length_updown.MaxValue = 1e6
            self.length_updown.Value = loaded_len
            self.length_updown.Width = 120
            self.length_updown.Height = 25

            # Add obstacle selection button and label
            self.select_obstacles_button = Eto.Forms.Button(Text="Pick Input Obstacles")
            self.select_obstacles_button.Click += self._on_select_obstacles
            self.select_obstacles_button.Width = 150

            # Add viewer point selection button and label
            self.select_viewer_point_button = Eto.Forms.Button(Text="Pick Viewer Point")
            self.select_viewer_point_button.Click += self._on_select_viewer_point
            self.select_viewer_point_button.Width = 150

            # Create main layout with better spacing
            layout = Eto.Forms.DynamicLayout()
            layout.Spacing = Eto.Drawing.Size(10, 10)
            
            # Add branding section with logo
            logo_label = Eto.Forms.ImageView()
            logo_label.Size = Eto.Drawing.Size(200, 30)
            self.logo = logo_label  # RHINO_UI expects this attribute
            layout.AddRow(logo_label)
            layout.AddSeparateRow()
            
            # Add main instruction
            layout.AddRow(Eto.Forms.Label(Text="Configure settings and pick obstacles and viewer point to generate view block diagram.", Font=Eto.Drawing.Font("Arial", 10)))
            layout.AddSeparateRow()
            
            # Step 1: Configure Settings
            layout.AddRow(Eto.Forms.Label(Text="Step 1: Configure Settings", Font=Eto.Drawing.Font("Arial", 11, Eto.Drawing.FontStyle.Bold)))
            layout.AddRow(Eto.Forms.Label(Text="Adjust ray casting parameters:"))
            
            # Create a table layout for the settings to ensure proper alignment
            settings_layout = Eto.Forms.TableLayout()
            settings_layout.Spacing = Eto.Drawing.Size(15, 8)
            settings_layout.Rows.Add(Eto.Forms.TableRow(
                Eto.Forms.Label(Text="Resolution (rays):", Width=150),
                self.resolution_updown
            ))
            settings_layout.Rows.Add(Eto.Forms.TableRow(
                Eto.Forms.Label(Text="Ray length:", Width=150),
                self.length_updown
            ))
            layout.AddRow(settings_layout)
            layout.AddSeparateRow()
            
            # Step 2: Obstacle Selection
            layout.AddRow(Eto.Forms.Label(Text="Step 2: Pick Input Obstacles", Font=Eto.Drawing.Font("Arial", 11, Eto.Drawing.FontStyle.Bold)))
            layout.AddRow(Eto.Forms.Label(Text="Select objects that will block the view rays."))
            layout.AddRow(self.obstacle_label)
            layout.AddRow(self.select_obstacles_button)
            layout.AddSeparateRow()
            
            # Step 3: Viewer Point Selection
            layout.AddRow(Eto.Forms.Label(Text="Step 3: Pick Viewer Point", Font=Eto.Drawing.Font("Arial", 11, Eto.Drawing.FontStyle.Bold)))
            layout.AddRow(Eto.Forms.Label(Text="Select the point where the viewer will be located."))
            layout.AddRow(self.viewer_point_label)
            layout.AddRow(self.select_viewer_point_button)
            layout.AddSeparateRow()

            # Add cancel button
            cancel_button = Eto.Forms.Button(Text="Cancel")
            cancel_button.Click += self._on_cancel
            cancel_button.Width = 80

            layout.AddSeparateRow(None, cancel_button, None)
            self.Content = layout

            RHINO_UI.apply_dark_style(self)

        def _select_obstacles(self):
            """Select obstacle objects"""
            # Use no filter to avoid stub errors; we'll accept any and extract geometry later
            ids = rs.GetObjects("Select obstacle objects", preselect=True, select=True)
            return ids or []

        def _pick_viewer_point(self):
            """Pick viewer point with dynamic ray preview"""
            geos = _build_geometry_list(self.selected_obstacles)
            get_dot_pt_instance = GetViewerPoint(geos, int(self.resolution_updown.Value), float(self.length_updown.Value))
            get_dot_pt_instance.Get()
            return get_dot_pt_instance.Point()

        def _on_select_obstacles(self, sender, e):
            # Temporarily close dialog for object selection
            self.Close(False)
            try:
                obstacles = self._select_obstacles()
                if obstacles:
                    self.selected_obstacles = obstacles
                    # Reopen dialog with updated obstacle count
                    self._reopen_dialog()
                else:
                    # Reopen dialog without changes
                    self._reopen_dialog()
            except Exception:
                # Reopen dialog on error
                self._reopen_dialog()

        def _on_select_viewer_point(self, sender, e):
            if not self.selected_obstacles:
                rs.MessageBox("Please select at least one obstacle object.")
                return
            # Temporarily close dialog for point selection
            self.Close(False)
            try:
                viewer_point = self._pick_viewer_point()
                if viewer_point:
                    self.selected_viewer_point = viewer_point
                    # Auto-start processing after viewer point is selected
                    self._auto_process()
                else:
                    # Reopen dialog without changes
                    self._reopen_dialog()
            except Exception:
                # Reopen dialog on error
                self._reopen_dialog()

        def _auto_process(self):
            """Automatically process the ray casting after all inputs are collected"""
            if not self.selected_obstacles or not self.selected_viewer_point:
                return
                
            # Save current settings
            current_settings = {
                "resolution": int(self.resolution_updown.Value),
                "ray_length": float(self.length_updown.Value)
            }
            _save_settings(current_settings)
                
            # Close the dialog and start processing
            self.Close(True)
            
            # Process the ray casting
            try:
                geos = _build_geometry_list(self.selected_obstacles)
                if not geos:
                    rs.MessageBox("No valid geometry for ray casting.")
                    return

                origin = Rhino.Geometry.Point3d(self.selected_viewer_point.X, self.selected_viewer_point.Y, self.selected_viewer_point.Z)
                good_flags, end_points = _cast_rays(origin, int(self.resolution_updown.Value), float(self.length_updown.Value), geos)
                added_ids = _create_arc_surfaces_from_groups(origin, good_flags, end_points)

                if sc.doc:
                    sc.doc.Views.Redraw()
                print("Created {} arc surfaces from ray groups".format(len(added_ids)))
                
            except Exception as e:
                rs.MessageBox("Error during processing: {}".format(str(e)))



        def _on_cancel(self, sender, e):
            self.Close(False)
            
        def _reopen_dialog(self):
            """Reopen the dialog with current values"""
            # Create a new dialog instance with current values
            new_dlg = OptionsDialog()
            new_dlg.selected_obstacles = self.selected_obstacles
            if self.selected_obstacles:
                new_dlg.obstacle_label.Text = "{} obstacles selected".format(len(self.selected_obstacles))
            else:
                new_dlg.obstacle_label.Text = "No obstacles selected"
            new_dlg.resolution_updown.Value = self.resolution_updown.Value
            new_dlg.length_updown.Value = self.length_updown.Value
            
            # Show the new dialog
            new_dlg.ShowModal(Rhino.UI.RhinoEtoApp.MainWindow)




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


def _create_arc_surfaces_from_groups(origin, good_flags, end_points):
    """Create surfaces using boundary arc and first/last lines of each group"""
    added = []
    count = len(good_flags)
    
    # Find groups of consecutive good rays
    groups = []
    current_group = []
    
    for i in range(count):
        if good_flags[i]:
            current_group.append(i)
        else:
            if len(current_group) >= 2:  # Need at least 2 rays to form a surface
                groups.append(current_group)
            current_group = []
    
    # Handle the case where good rays wrap around the end
    if len(current_group) >= 2:
        if current_group and good_flags[0]:  # Check if first ray is also good
            # Merge with first group if it exists
            if groups and good_flags[0]:
                groups[0] = current_group + groups[0]
            else:
                groups.append(current_group)
        else:
            groups.append(current_group)
    
    # Create surfaces for each group
    for group in groups:
        if len(group) < 3:  # Need at least 3 rays to create a proper arc
            continue
            
        # Use first, middle, and last ray of the group for 3-point arc
        first_idx = group[0]
        middle_idx = group[len(group) // 2]  # Middle ray of the group
        last_idx = group[-1]
        
        # Create first and last radius lines from origin to end points
        first_line = Rhino.Geometry.Line(origin, end_points[first_idx]).ToNurbsCurve()
        last_line = Rhino.Geometry.Line(origin, end_points[last_idx]).ToNurbsCurve()
        
        # Create 3-point arc using first, middle, and last points
        boundary_arc = Rhino.Geometry.Arc(
            end_points[first_idx],      # Start point
            end_points[middle_idx],     # Point on arc (middle ray)
            end_points[last_idx]        # End point
        ).ToNurbsCurve()
        
                # create boundary surface by the first last and arc

        # Create boundary curves list: first radius line, boundary arc, last radius line
        boundary_curves = [first_line, boundary_arc, last_line]
        
        # Join the boundary curves into a single closed curve
        tolerance = sc.doc.ModelAbsoluteTolerance
        joined_curves = Rhino.Geometry.Curve.JoinCurves(boundary_curves, tolerance)
        
        if joined_curves and len(joined_curves) > 0:
            # Use the first joined curve to create planar surface
            closed_boundary = joined_curves[0]
            
            # Create a planar surface from the joined boundary curve
            brep = Rhino.Geometry.Brep.CreatePlanarBreps(closed_boundary, tolerance)
            if brep:
                for b in brep:
                    obj_id = sc.doc.Objects.AddBrep(b) if sc.doc else None
                    if obj_id:
                        added.append(obj_id)
        else:
            print("Failed to join boundary curves")
                    

    
    return added

class GetViewerPoint (Rhino.Input.Custom.GetPoint):

    def __init__(self, boundary_shapes, sample_count, ray_length):
        self.boundary_shapes = boundary_shapes
        self.sample_count = int(sample_count/10)# use smaller count to make preview very fast
        self.ray_length = ray_length
        
    def OnDynamicDraw(self, e):
        current_point = e.CurrentPoint
        good_flags, end_points = _cast_rays(current_point, self.sample_count, self.ray_length, self.boundary_shapes)

        # Draw rays for good (unobstructed) directions
        for i, is_good in enumerate(good_flags):
            if is_good:
                try:
                    # Use the pre-calculated endpoint from _cast_rays
                    end_point = end_points[i]
                    
                    # Draw the ray line from current point to endpoint
                    e.Display.DrawLine(current_point, end_point, System.Drawing.Color.White, 10)
                except Exception as ex:
                    print("Error drawing ray line: {}".format(str(ex)))


        e.Display.DrawDot(current_point, "Viewer")
   
@LOG.log(__file__, __title__)
@ERROR_HANDLE.try_catch_error()
def view_block_diagram():
    # Show the ETO dialog - processing happens automatically when complete
    dlg = OptionsDialog()
    dlg.ShowModal(Rhino.UI.RhinoEtoApp.MainWindow)

    
if __name__ == "__main__":
    view_block_diagram()
