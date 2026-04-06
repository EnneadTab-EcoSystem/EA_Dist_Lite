# -*- coding: utf-8 -*-
"""Place family instance route handler for EnneadTab MCP."""
import json

from pyrevit import routes
from Autodesk.Revit import DB


def _find_family_symbol(doc, family_name, type_name):
    """Find a FamilySymbol by family name and type name."""
    collector = (
        DB.FilteredElementCollector(doc)
        .OfClass(DB.FamilySymbol)
        .ToElements()
    )
    for symbol in collector:
        fam = symbol.Family
        if fam is None:
            continue
        if fam.Name == family_name and symbol.Name == type_name:
            return symbol
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


def register_place_family_routes(api):
    @api.route("/place-family/", methods=["POST"])
    def place_family(doc, request):
        if not doc:
            return routes.make_response(
                data={"error": "No document open"},
                status_code=400,
            )

        data = json.loads(request.data) if isinstance(request.data, str) else request.data
        family_name = data.get("family_name")
        type_name = data.get("type_name")
        x = data.get("x", 0)
        y = data.get("y", 0)
        z = data.get("z", 0)
        level_name = data.get("level_name")

        if not family_name or not type_name:
            return routes.make_response(
                data={"error": "family_name and type_name are required"},
                status_code=400,
            )

        symbol = _find_family_symbol(doc, family_name, type_name)
        if symbol is None:
            return routes.make_response(
                data={
                    "error": "FamilySymbol not found: {} : {}".format(
                        family_name, type_name
                    )
                },
                status_code=404,
            )

        # Resolve level
        level = None
        if level_name:
            level = _find_level(doc, level_name)
            if level is None:
                return routes.make_response(
                    data={"error": "Level not found: {}".format(level_name)},
                    status_code=404,
                )
        else:
            # Use the first available level
            level = (
                DB.FilteredElementCollector(doc)
                .OfClass(DB.Level)
                .FirstElement()
            )

        location = DB.XYZ(float(x), float(y), float(z))

        t = DB.Transaction(doc, "MCP: Place Family")
        try:
            t.Start()

            # Activate the symbol if not already active
            if not symbol.IsActive:
                symbol.Activate()
                doc.Regenerate()

            instance = doc.Create.NewFamilyInstance(
                location,
                symbol,
                level,
                DB.Structure.StructuralType.NonStructural,
            )

            t.Commit()
        except Exception as e:
            if t.HasStarted():
                t.RollBack()
            return routes.make_response(
                data={"error": str(e)},
                status_code=500,
            )

        return routes.make_response(data={
            "instance_id": instance.Id.IntegerValue,
            "family_name": family_name,
            "type_name": type_name,
            "location": {"x": x, "y": y, "z": z},
            "level": level.Name if level else None,
            "success": True,
        })
