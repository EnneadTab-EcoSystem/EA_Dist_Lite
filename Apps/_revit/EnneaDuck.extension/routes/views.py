# -*- coding: utf-8 -*-
"""Views route handler for EnneadTab MCP."""
from pyrevit import routes
from Autodesk.Revit import DB


def register_view_routes(api):
    @api.route("/views/", methods=["GET"])
    def get_views(doc, request):
        if not doc:
            return routes.make_response(
                data={"error": "No document open"},
                status_code=400,
            )

        collector = (
            DB.FilteredElementCollector(doc)
            .OfClass(DB.View)
            .ToElements()
        )

        grouped = {}
        total = 0
        for view in collector:
            # Skip view templates
            if view.IsTemplate:
                continue

            view_type = str(view.ViewType)
            if view_type not in grouped:
                grouped[view_type] = []

            grouped[view_type].append({
                "id": view.Id.IntegerValue,
                "name": view.Name,
                "view_type": view_type,
                "scale": view.Scale if hasattr(view, "Scale") else None,
            })
            total += 1

        return routes.make_response(data={
            "count": total,
            "view_types": list(grouped.keys()),
            "views_by_type": grouped,
        })
