# -*- coding: utf-8 -*-
"""Element parameters route handler for EnneadTab MCP."""
from pyrevit import routes
from Autodesk.Revit import DB


def _get_param_value(param):
    """Extract the value from a Revit parameter."""
    if not param.HasValue:
        return None

    storage = param.StorageType
    if storage == DB.StorageType.String:
        return param.AsString()
    elif storage == DB.StorageType.Integer:
        return param.AsInteger()
    elif storage == DB.StorageType.Double:
        return param.AsDouble()
    elif storage == DB.StorageType.ElementId:
        return param.AsElementId().IntegerValue
    return None


def register_element_params_routes(api):
    @api.route("/enneadtab/element/<element_id>/parameters/", methods=["GET"])
    def get_element_params(doc, request, element_id):
        if not doc:
            return routes.make_response(
                data={"error": "No document open"},
                status_code=400,
            )

        try:
            eid = DB.ElementId(int(element_id))
        except (ValueError, TypeError):
            return routes.make_response(
                data={"error": "Invalid element_id: {}".format(element_id)},
                status_code=400,
            )

        elem = doc.GetElement(eid)
        if elem is None:
            return routes.make_response(
                data={"error": "Element not found: {}".format(element_id)},
                status_code=404,
            )

        parameters = []
        for param in elem.Parameters:
            param_data = {
                "name": param.Definition.Name,
                "value": _get_param_value(param),
                "display_value": param.AsValueString(),
                "storage_type": str(param.StorageType),
                "is_read_only": param.IsReadOnly,
                "has_value": param.HasValue,
            }

            try:
                param_data["is_shared"] = param.IsShared
            except Exception:
                param_data["is_shared"] = False

            parameters.append(param_data)

        return routes.make_response(data={
            "element_id": int(element_id),
            "element_name": elem.Name if elem.Name else None,
            "category": elem.Category.Name if elem.Category else None,
            "parameter_count": len(parameters),
            "parameters": parameters,
        })
