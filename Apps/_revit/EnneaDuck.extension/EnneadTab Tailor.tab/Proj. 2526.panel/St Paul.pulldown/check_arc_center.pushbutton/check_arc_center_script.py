#!/usr/bin/python
# -*- coding: utf-8 -*-

__doc__ = "Analyze all arc walls in the project, group their centers by XY coordinates, and generate select links for inspection."
__title__ = "Check Arc Center"

import proDUCKtion # pyright: ignore 
proDUCKtion.validify()

from EnneadTab import ERROR_HANDLE, LOG
from EnneadTab.REVIT import REVIT_APPLICATION, REVIT_UNIT
from pyrevit import output
from Autodesk.Revit import DB # pyright: ignore 

UIDOC = REVIT_APPLICATION.get_uidoc()
DOC = REVIT_APPLICATION.get_doc()


@LOG.log(__file__, __title__)
@ERROR_HANDLE.try_catch_error()
def check_arc_center(doc):
    """
    Analyze all arc walls in the project, group their centers by XY coordinates,
    and generate select links for inspection.
    """
    
    # Get all walls in the project
    collector = DB.FilteredElementCollector(doc).OfCategory(DB.BuiltInCategory.OST_Walls).WhereElementIsNotElementType()
    walls = collector.ToElements()
    
    print("Found {} walls in the project".format(len(walls)))
    
    # Dictionary to group arc centers by XY coordinates
    arc_centers_by_xy = {}
    arc_walls = []
    
    # Process each wall
    for wall in walls:
        try:
            # Get the wall's location curve
            if hasattr(wall, 'Location') and wall.Location and hasattr(wall.Location, 'Curve'):
                curve = wall.Location.Curve
                
                # Check if the curve is an arc
                if isinstance(curve, DB.Arc):
                    # Get the arc center
                    center = curve.Center
                    
                    # Round coordinates to avoid floating point precision issues
                    # Using 1mm tolerance for grouping
                    tolerance = REVIT_UNIT.mm_to_internal(1)  # 1mm tolerance
                    x_rounded = round(center.X / tolerance) * tolerance
                    y_rounded = round(center.Y / tolerance) * tolerance
                    z_rounded = round(center.Z / tolerance) * tolerance
                    
                    # Create XY key for grouping
                    xy_key = (x_rounded, y_rounded)
                    
                    # Store wall info
                    wall_info = {
                        'wall': wall,
                        'center': center,
                        'radius': curve.Radius,
                        'start_angle': curve.GetEndParameter(0),
                        'end_angle': curve.GetEndParameter(1),
                        'z': z_rounded
                    }
                    
                    # Group by XY coordinates
                    if xy_key not in arc_centers_by_xy:
                        arc_centers_by_xy[xy_key] = []
                    
                    arc_centers_by_xy[xy_key].append(wall_info)
                    arc_walls.append(wall_info)
                    
        except Exception as e:
            print("Error processing wall {}: {}".format(wall.Id, str(e)))
            continue
    
    print("\nFound {} arc walls in the project".format(len(arc_walls)))
    print("Grouped into {} unique arc center locations".format(len(arc_centers_by_xy)))
    
    # Display results grouped by XY coordinates
    print("\n" + "="*80)
    print("ARC WALL CENTER ANALYSIS")
    print("="*80)
    
    for i, (xy_key, walls_at_center) in enumerate(arc_centers_by_xy.iteritems(), 1):
        x, y = xy_key
        print("\nGroup {}: Center at ({:.2f}, {:.2f}) feet".format(i, x, y))
        print("-" * 60)
        
        print("  Center: ({:.2f}, {:.2f}) feet".format(x, y))
        print("  Number of arc walls at this center: {}".format(len(walls_at_center)))
        
        # Show details for each wall at this center
        for j, wall_info in enumerate(walls_at_center, 1):
            wall = wall_info['wall']
            center = wall_info['center']
            radius = wall_info['radius']
            z = wall_info['z']
            
            # Get wall type name
            wall_type_name = "Unknown"
            try:
                if hasattr(wall, 'WallType') and wall.WallType:
                    wall_type_name = wall.WallType.Name
            except:
                pass
            
            print("    Wall {}: {}".format(j, output.linkify(wall.Id, title="Select Wall")))
            print("      - Wall Type: {}".format(wall_type_name))
            print("      - Radius: {:.2f} feet".format(radius))
            print("      - Z Level: {:.2f} feet".format(z))
            print("      - Center: ({:.2f}, {:.2f}, {:.2f}) feet".format(
                center.X,
                center.Y,
                center.Z
            ))
    
    # Summary statistics
    print("\n" + "="*80)
    print("SUMMARY STATISTICS")
    print("="*80)
    print("Total arc walls found: {}".format(len(arc_walls)))
    print("Unique arc center locations: {}".format(len(arc_centers_by_xy)))
    
    # Count walls per center
    walls_per_center = [len(walls) for walls in arc_centers_by_xy.values()]
    if walls_per_center:
        print("Average walls per center: {:.1f}".format(sum(walls_per_center) / len(walls_per_center)))
        print("Most walls at single center: {}".format(max(walls_per_center)))
        print("Least walls at single center: {}".format(min(walls_per_center)))
    
    # Show centers with multiple walls
    multi_wall_centers = [(xy, walls) for xy, walls in arc_centers_by_xy.items() if len(walls) > 1]
    if multi_wall_centers:
        print("\nCenters with multiple arc walls:")
        for xy_key, walls in multi_wall_centers:
            x, y = xy_key
            print("  Center ({:.2f}, {:.2f}) feet: {} walls".format(x, y, len(walls)))
    
    print("\nAnalysis complete!")


################## main code below #####################
if __name__ == "__main__":
    check_arc_center(DOC)







