# -*- coding: utf-8 -*-
"""Levels route handler for EnneadTab MCP."""
from pyrevit import routes
from Autodesk.Revit import DB


def register_level_routes(api):
    @api.route("/levels/", methods=["GET"])
    def get_levels(doc, request):
        if not doc:
            return routes.make_response(
                data={"error": "No document open"},
                status_code=400,
            )

        collector = (
            DB.FilteredElementCollector(doc)
            .OfClass(DB.Level)
            .ToElements()
        )

        levels = []
        for level in collector:
            levels.append({
                "id": level.Id.IntegerValue,
                "name": level.Name,
                "elevation": level.Elevation,
            })

        # Sort by elevation ascending
        levels.sort(key=lambda x: x["elevation"])

        return routes.make_response(data={
            "count": len(levels),
            "levels": levels,
        })
