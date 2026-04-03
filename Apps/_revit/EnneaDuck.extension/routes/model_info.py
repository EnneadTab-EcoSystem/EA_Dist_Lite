# -*- coding: utf-8 -*-
"""Model info route handler for EnneadTab MCP."""
from pyrevit import routes, revit
from Autodesk.Revit import DB


def register_model_info_routes(api):
    @api.route("/enneadtab/model-info/", methods=["GET"])
    def get_model_info(doc, request):
        if not doc:
            return routes.make_response(
                data={"error": "No document open"},
                status_code=400,
            )

        info = doc.ProjectInformation
        result = {
            "name": doc.Title,
            "path": doc.PathName,
            "number": info.Number if info else None,
            "client": info.ClientName if info else None,
            "address": info.Address if info else None,
            "building_type": info.BuildingType if info else None,
        }

        # Phases
        phases = DB.FilteredElementCollector(doc).OfClass(DB.Phase).ToElements()
        phase_list = []
        for phase in phases:
            phase_list.append({
                "id": phase.Id.IntegerValue,
                "name": phase.Name,
            })
        result["phase_count"] = len(phase_list)
        result["phases"] = phase_list

        # Units
        try:
            units = doc.GetUnits()
            length_spec = DB.SpecTypeId.Length
            format_opts = units.GetFormatOptions(length_spec)
            unit_symbol = str(format_opts.GetUnitTypeId())
            result["units"] = unit_symbol
        except Exception:
            try:
                # Older Revit API fallback
                units = doc.GetUnits()
                format_opts = units.GetFormatOptions(DB.UnitType.UT_Length)
                result["units"] = str(format_opts.DisplayUnits)
            except Exception:
                result["units"] = "unknown"

        return routes.make_response(data=result)
