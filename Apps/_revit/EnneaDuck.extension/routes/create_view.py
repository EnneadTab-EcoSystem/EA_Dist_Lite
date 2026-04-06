# -*- coding: utf-8 -*-
"""Create view route handler for EnneadTab MCP."""
import json

from pyrevit import routes
from Autodesk.Revit import DB


VIEW_TYPE_MAP = {
    "FloorPlan": DB.ViewFamily.FloorPlan,
    "CeilingPlan": DB.ViewFamily.CeilingPlan,
    "Section": DB.ViewFamily.Section,
    "ThreeD": DB.ViewFamily.ThreeDimensional,
    "Elevation": DB.ViewFamily.Elevation,
}


def _find_view_family_type(doc, view_family):
    """Find a ViewFamilyType matching the requested ViewFamily."""
    collector = (
        DB.FilteredElementCollector(doc)
        .OfClass(DB.ViewFamilyType)
        .ToElements()
    )
    for vft in collector:
        if vft.ViewFamily == view_family:
            return vft
    return None


def _find_level(doc, level_name):
    """Find a level by name."""
    collector = (
        DB.FilteredElementCollector(doc)
        .OfClass(DB.Level)
        .ToElements()
    )
    for level in collector:
        if level.Name == level_name:
            return level
    return None


def register_create_view_routes(api):
    @api.route("/create-view/", methods=["POST"])
    def create_view(doc, request):
        if not doc:
            return routes.make_response(
                data={"error": "No document open"},
                status_code=400,
            )

        data = json.loads(request.data) if isinstance(request.data, str) else request.data
        view_type = data.get("view_type")
        level_name = data.get("level_name")
        view_name = data.get("name")

        if not view_type:
            return routes.make_response(
                data={"error": "view_type is required"},
                status_code=400,
            )

        if view_type not in VIEW_TYPE_MAP:
            return routes.make_response(
                data={
                    "error": "Unsupported view_type: {}. Supported: {}".format(
                        view_type, ", ".join(VIEW_TYPE_MAP.keys())
                    )
                },
                status_code=400,
            )

        view_family = VIEW_TYPE_MAP[view_type]
        vft = _find_view_family_type(doc, view_family)
        if vft is None:
            return routes.make_response(
                data={"error": "No ViewFamilyType found for: {}".format(view_type)},
                status_code=404,
            )

        # Resolve level for plan-based views
        level = None
        needs_level = view_type in ("FloorPlan", "CeilingPlan")
        if needs_level:
            if level_name:
                level = _find_level(doc, level_name)
                if level is None:
                    return routes.make_response(
                        data={"error": "Level not found: {}".format(level_name)},
                        status_code=404,
                    )
            else:
                # Use the first available level
                first_level = (
                    DB.FilteredElementCollector(doc)
                    .OfClass(DB.Level)
                    .FirstElement()
                )
                if first_level is None:
                    return routes.make_response(
                        data={"error": "No levels found in model"},
                        status_code=400,
                    )
                level = first_level

        t = DB.Transaction(doc, "MCP: Create View")
        try:
            t.Start()

            if view_type in ("FloorPlan", "CeilingPlan"):
                new_view = DB.ViewPlan.Create(doc, vft.Id, level.Id)
            elif view_type == "Section":
                # Create a default section box
                transform = DB.Transform.Identity
                transform.Origin = DB.XYZ(0, 0, 0)
                transform.BasisX = DB.XYZ(1, 0, 0)
                transform.BasisY = DB.XYZ(0, 0, 1)
                transform.BasisZ = DB.XYZ(0, -1, 0)
                section_box = DB.BoundingBoxXYZ()
                section_box.Transform = transform
                section_box.Min = DB.XYZ(-10, -10, 0)
                section_box.Max = DB.XYZ(10, 10, 10)
                new_view = DB.ViewSection.CreateSection(doc, vft.Id, section_box)
            elif view_type == "ThreeD":
                new_view = DB.View3D.CreateIsometric(doc, vft.Id)
            elif view_type == "Elevation":
                # Create an elevation marker and get the first view
                marker = DB.ElevationMarker.CreateElevationMarker(
                    doc, vft.Id, DB.XYZ(0, 0, 0), 100
                )
                new_view = marker.CreateElevation(doc, doc.ActiveView.Id, 0)
            else:
                t.RollBack()
                return routes.make_response(
                    data={"error": "Unhandled view_type: {}".format(view_type)},
                    status_code=400,
                )

            if view_name:
                new_view.Name = view_name

            t.Commit()
        except Exception as e:
            if t.HasStarted():
                t.RollBack()
            return routes.make_response(
                data={"error": str(e)},
                status_code=500,
            )

        return routes.make_response(data={
            "view_id": new_view.Id.IntegerValue,
            "view_name": new_view.Name,
            "view_type": view_type,
            "success": True,
        })
