# -*- coding: utf-8 -*-
"""Levels route handler for EnneadTab MCP."""
from pyrevit import routes
from Autodesk.Revit import DB

from EnneadTab.REVIT import REVIT_APPLICATION


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
                "id": REVIT_APPLICATION.get_element_id_value(level.Id),
                "name": level.Name,
                "elevation": level.Elevation,
            })

        # Sort by elevation ascending
        levels.sort(key=lambda x: x["elevation"])

        return routes.make_response(data={
            "count": len(levels),
            "levels": levels,
        })
