# -*- coding: utf-8 -*-
"""Elements route handler for EnneadTab MCP."""
import json

from pyrevit import routes
from Autodesk.Revit import DB


MAX_RESULTS = 500


def _find_builtin_category(category_name):
    """Find a BuiltInCategory by matching against member names."""
    for member in dir(DB.BuiltInCategory):
        if member.startswith("OST_"):
            # Match against the name with or without OST_ prefix
            if member == category_name or member == "OST_{}".format(category_name):
                return getattr(DB.BuiltInCategory, member)
            # Also try case-insensitive match
            if member.lower() == category_name.lower():
                return getattr(DB.BuiltInCategory, member)
            if member.lower() == "ost_{}".format(category_name.lower()):
                return getattr(DB.BuiltInCategory, member)
    return None


def register_element_routes(api):
    @api.route("/enneadtab/elements/", methods=["GET"])
    def get_elements(doc, request):
        if not doc:
            return routes.make_response(
                data={"error": "No document open"},
                status_code=400,
            )

        category = request.get("category")
        if not category:
            return routes.make_response(
                data={"error": "category query parameter is required"},
                status_code=400,
            )

        bic = _find_builtin_category(category)
        if bic is None:
            return routes.make_response(
                data={"error": "Unknown category: {}".format(category)},
                status_code=400,
            )

        collector = (
            DB.FilteredElementCollector(doc)
            .OfCategory(bic)
            .WhereElementIsNotElementType()
        )

        # Optional filters
        filters_str = request.get("filters")
        if filters_str:
            try:
                filters = json.loads(filters_str)
            except (ValueError, TypeError):
                filters = {}
        else:
            filters = {}

        elements = []
        count = 0
        for elem in collector:
            if count >= MAX_RESULTS:
                break

            elem_data = {
                "id": elem.Id.IntegerValue,
                "name": elem.Name if elem.Name else None,
                "category": elem.Category.Name if elem.Category else None,
            }

            # Apply parameter filters if provided
            if filters:
                match = True
                for param_name, expected_value in filters.items():
                    param = elem.LookupParameter(param_name)
                    if param is None:
                        match = False
                        break
                    actual = param.AsString() or str(param.AsValueString() or "")
                    if actual != str(expected_value):
                        match = False
                        break
                if not match:
                    continue

            elements.append(elem_data)
            count += 1

        return routes.make_response(data={
            "category": category,
            "count": len(elements),
            "capped": count >= MAX_RESULTS,
            "elements": elements,
        })
