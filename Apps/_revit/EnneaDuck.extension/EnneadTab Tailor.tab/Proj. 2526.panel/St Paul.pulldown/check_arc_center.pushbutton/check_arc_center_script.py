#!/usr/bin/python
# -*- coding: utf-8 -*-

__doc__ = "Analyze all arc walls in the project, group their centers by XY coordinates, and generate select links for inspection."
__title__ = "Check Arc Center"

import proDUCKtion # pyright: ignore 
proDUCKtion.validify()

from EnneadTab import ERROR_HANDLE, LOG
from EnneadTab.REVIT import REVIT_APPLICATION, REVIT_UNIT
from pyrevit import script
from Autodesk.Revit import DB # pyright: ignore 

UIDOC = REVIT_APPLICATION.get_uidoc()
DOC = REVIT_APPLICATION.get_doc()


def get_wall_type_name(wall):
    """Get wall type name with fallback options."""
    try:
        if hasattr(wall, 'WallType') and wall.WallType:
            # Use LookupParameter to get the actual type name
            wall_type_name = wall.WallType.LookupParameter("Type Name").AsString()
            if not wall_type_name or wall_type_name.strip() == "":
                # Fallback to Name property if Type Name parameter is empty
                wall_type_name = wall.WallType.Name
            return wall_type_name
    except:
        pass
    return "Unknown"


def find_existing_group(x, y, groups, tolerance):
    """Find if a center (x,y) belongs to an existing group within tolerance."""
    for group_center in groups.keys():
        gx, gy = group_center
        distance = ((x - gx) ** 2 + (y - gy) ** 2) ** 0.5
        if distance <= tolerance:
            return group_center
    return None


def is_suspicious_center(x, y, origin_point, suspicious_tolerance, grouping_tolerance):
    """Check if a center is suspiciously close to (50,50) but not exactly there."""
    distance_to_origin = ((x - origin_point[0]) ** 2 + (y - origin_point[1]) ** 2) ** 0.5
    return distance_to_origin <= suspicious_tolerance and distance_to_origin > grouping_tolerance


def process_arc_walls(walls, origin_point, suspicious_tolerance, grouping_tolerance):
    """Process all walls and extract arc wall information."""
    arc_centers_by_xy = {}
    arc_walls = []
    suspicious_walls = []
    
    for wall in walls:
        try:
            # Get the wall's location curve
            if hasattr(wall, 'Location') and wall.Location and hasattr(wall.Location, 'Curve'):
                curve = wall.Location.Curve
                
                # Check if the curve is an arc
                if isinstance(curve, DB.Arc):
                    # Get the arc center
                    center = curve.Center
                    x, y = center.X, center.Y
                    
                    # Store wall info
                    wall_info = {
                        'wall': wall,
                        'center': center,
                        'radius': curve.Radius,
                        'start_angle': curve.GetEndParameter(0),
                        'end_angle': curve.GetEndParameter(1),
                        'z': center.Z,
                        'is_suspicious': is_suspicious_center(x, y, origin_point, suspicious_tolerance, grouping_tolerance)
                    }
                    
                    # Check if this is a suspicious wall
                    if wall_info['is_suspicious']:
                        suspicious_walls.append(wall_info)
                    
                    # Find existing group or create new one
                    existing_group = find_existing_group(x, y, arc_centers_by_xy, grouping_tolerance)
                    
                    if existing_group:
                        # Add to existing group
                        arc_centers_by_xy[existing_group].append(wall_info)
                    else:
                        # Create new group with the actual coordinates
                        xy_key = (x, y)
                        arc_centers_by_xy[xy_key] = [wall_info]
                    
                    arc_walls.append(wall_info)
                    
        except Exception as e:
            print("Error processing wall {}: {}".format(wall.Id, str(e)))
            continue
    
    return arc_centers_by_xy, arc_walls, suspicious_walls


def display_suspicious_walls(suspicious_walls, origin_point, output):
    """Display suspicious walls section."""
    if suspicious_walls:
        output.print_md("## ⚠️ SUSPICIOUS ARC WALLS")
        output.print_md("**Centers close to (50,50) but not exactly there**")
        output.print_md("> These walls may have incorrect centers and should be investigated:")
        
        for i, wall_info in enumerate(suspicious_walls, 1):
            wall = wall_info['wall']
            center = wall_info['center']
            radius = wall_info['radius']
            
            # Calculate distance to origin
            distance_to_origin = ((center.X - origin_point[0]) ** 2 + (center.Y - origin_point[1]) ** 2) ** 0.5
            distance_feet = REVIT_UNIT.internal_to_unit(distance_to_origin, "feet")
            
            wall_type_name = get_wall_type_name(wall)
            
            print("  {}. Wall {}: {}".format(i, wall.Id, output.linkify(wall.Id, title="Select Suspicious Wall")))
            print("     - Distance from (50,50): {:.2f} feet".format(distance_feet))
            print("     - Actual Center: ({:.3f}, {:.3f}, {:.3f}) feet".format(
                center.X, center.Y, center.Z))
            print("     - Wall Type: {}".format(wall_type_name))
            print("     - Radius: {:.2f} feet".format(radius))
            print()
    else:
        output.print_md("### ✅ No Suspicious Walls Found")
        output.print_md("**No arc walls found near (50,50) origin**")


def get_group_priority(xy_key, walls_at_center):
    """Calculate priority for group sorting."""
    # Unpack xy_key but we don't need the actual values for priority calculation
    _x, _y = xy_key
    has_suspicious = any(wall_info['is_suspicious'] for wall_info in walls_at_center)
    wall_count = len(walls_at_center)
    
    if has_suspicious:
        return (0, -wall_count)  # Suspicious groups first, then by wall count (descending)
    else:
        return (1, -wall_count)  # Regular groups second, then by wall count (descending)


def display_arc_wall_analysis(arc_centers_by_xy, output):
    """Display the main arc wall analysis grouped by center location."""
    output.print_md("# 📍 ARC WALL CENTER ANALYSIS")
    output.print_md("**Grouped by Center Location**")
    
    # Use iteritems() for IronPython 2.7 compatibility, items() for CPython
    try:
        items_iter = arc_centers_by_xy.iteritems()
    except AttributeError:
        items_iter = arc_centers_by_xy.items()
    
    # Sort groups by priority
    sorted_groups = sorted(items_iter, key=lambda item: get_group_priority(item[0], item[1]))
    
    for i, (xy_key, walls_at_center) in enumerate(sorted_groups, 1):
        x, y = xy_key
        has_suspicious = any(wall_info['is_suspicious'] for wall_info in walls_at_center)
        
        # Determine group status
        if has_suspicious:
            status_icon = "⚠️"
            status_text = "SUSPICIOUS"
            status_color = "red"
        else:
            status_icon = "📍"
            status_text = "NORMAL"
            status_color = "green"
        
        # Add spacing before each group (except the first one)
        if i > 1:
            output.print_md("---")
        
        # Use markdown formatting for better headers
        output.print_md("### Group {}: {} Center at ({:.3f}, {:.3f}) feet".format(i, status_icon, x, y))
        output.print_md("**Status:** <span style='color:{}'>**{}**</span>".format(status_color, status_text))
        
        print("  Center: ({:.3f}, {:.3f}) feet".format(x, y))
        print("  Number of arc walls at this center: {}".format(len(walls_at_center)))
        
        # Calculate group statistics
        radii = [wall_info['radius'] for wall_info in walls_at_center]
        z_levels = [wall_info['z'] for wall_info in walls_at_center]
        
        print("  Radius range: {:.2f} - {:.2f} feet".format(min(radii), max(radii)))
        print("  Z level range: {:.2f} - {:.2f} feet".format(min(z_levels), max(z_levels)))
        print()
        
        # Show details for each wall at this center
        for j, wall_info in enumerate(walls_at_center, 1):
            wall = wall_info['wall']
            center = wall_info['center']
            radius = wall_info['radius']
            z = wall_info['z']
            is_suspicious = wall_info['is_suspicious']
            
            wall_type_name = get_wall_type_name(wall)
            
            # Add warning indicator for suspicious walls
            warning_indicator = " ⚠️" if is_suspicious else ""
            
            print("    Wall {}: {}{}".format(j, output.linkify(wall.Id, title="Select Wall"), warning_indicator))
            print("      - Wall Type: {}".format(wall_type_name))
            print("      - Radius: {:.2f} feet".format(radius))
            print("      - Z Level: {:.2f} feet".format(z))
            print("      - Center: ({:.3f}, {:.3f}, {:.3f}) feet".format(
                center.X,
                center.Y,
                center.Z
            ))


def display_summary_statistics(arc_walls, arc_centers_by_xy, suspicious_walls, grouping_tolerance, suspicious_tolerance, output):
    """Display summary statistics and recommendations."""
    output.print_md("## 📊 SUMMARY STATISTICS")
    print("Total arc walls found: {}".format(len(arc_walls)))
    print("Unique arc center locations: {}".format(len(arc_centers_by_xy)))
    print("Suspicious walls (near 50,50): {}".format(len(suspicious_walls)))
    
    # Count walls per center
    walls_per_center = [len(walls) for walls in arc_centers_by_xy.values()]
    if walls_per_center:
        print("Average walls per center: {:.1f}".format(float(sum(walls_per_center)) / len(walls_per_center)))
        print("Most walls at single center: {}".format(max(walls_per_center)))
        print("Least walls at single center: {}".format(min(walls_per_center)))
    
    # Show centers with multiple walls
    multi_wall_centers = [(xy, walls) for xy, walls in arc_centers_by_xy.items() if len(walls) > 1]
    if multi_wall_centers:
        print("\nCenters with multiple arc walls:")
        for xy_key, walls in multi_wall_centers:
            x, y = xy_key
            has_suspicious = any(wall_info['is_suspicious'] for wall_info in walls)
            status_indicator = " ⚠️" if has_suspicious else ""
            print("  Center ({:.3f}, {:.3f}) feet: {} walls{}".format(x, y, len(walls), status_indicator))
    
    # Show tolerance information
    output.print_md("#### Tolerance Settings")
    output.print_md("- **Grouping tolerance:** {:.3f} feet".format(REVIT_UNIT.internal_to_unit(grouping_tolerance, "feet")))
    output.print_md("- **Suspicious detection tolerance:** {:.1f} feet".format(REVIT_UNIT.internal_to_unit(suspicious_tolerance, "feet")))
    
    if suspicious_walls:
        output.print_md("### ⚠️ RECOMMENDATION")
        output.print_md("**Investigate the {} suspicious walls listed above.**".format(len(suspicious_walls)))
        output.print_md("> These walls may have incorrect center points and should be reviewed.")
    else:
        output.print_md("### ✅ ANALYSIS COMPLETE")
        output.print_md("**No suspicious arc walls detected.** All centers appear to be properly positioned.")
    
    output.print_md("---")
    output.print_md("*Analysis complete!*")


@LOG.log(__file__, __title__)
@ERROR_HANDLE.try_catch_error()
def check_arc_center(doc):
    """
    Analyze all arc walls in the project, group their centers by XY coordinates,
    and generate select links for inspection.
    """
    # Get output object for creating links
    output = script.get_output()
    
    # Get all walls in the project
    collector = DB.FilteredElementCollector(doc).OfCategory(DB.BuiltInCategory.OST_Walls).WhereElementIsNotElementType()
    walls = collector.ToElements()
    
    print("Found {} walls in the project".format(len(walls)))
    
    # Define tolerance settings (in feet)
    grouping_tolerance = REVIT_UNIT.unit_to_internal(0.02, "feet")  # 0.02 feet (about 1/4 inch) tolerance for grouping
    suspicious_tolerance = REVIT_UNIT.unit_to_internal(10.0, "feet")  # 10 feet tolerance for suspicious detection
    origin_point = (50.0, 50.0)  # Default Revit origin
    
    # Process all walls and extract arc wall information
    arc_centers_by_xy, arc_walls, suspicious_walls = process_arc_walls(
        walls, origin_point, suspicious_tolerance, grouping_tolerance)
    
    print("\nFound {} arc walls in the project".format(len(arc_walls)))
    print("Grouped into {} unique arc center locations".format(len(arc_centers_by_xy)))
    
    # Display suspicious walls section
    display_suspicious_walls(suspicious_walls, origin_point, output)
    
    # Add spacing between main sections
    output.print_md("")
    output.print_md("---")
    output.print_md("")
    
    # Display main analysis
    display_arc_wall_analysis(arc_centers_by_xy, output)
    
    # Add spacing before summary section
    output.print_md("")
    output.print_md("---")
    output.print_md("")
    
    # Display summary statistics and recommendations
    display_summary_statistics(arc_walls, arc_centers_by_xy, suspicious_walls, 
                              grouping_tolerance, suspicious_tolerance, output)


################## main code below #####################
if __name__ == "__main__":
    check_arc_center(DOC)







