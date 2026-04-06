# -*- coding: utf-8 -*-
"""Families route handler for EnneadTab MCP."""
from pyrevit import routes
from Autodesk.Revit import DB


def register_family_routes(api):
    @api.route("/families/", methods=["GET"])
    def get_families(doc, request):
        if not doc:
            return routes.make_response(
                data={"error": "No document open"},
                status_code=400,
            )

        category_filter = request.get("category")

        collector = (
            DB.FilteredElementCollector(doc)
            .OfClass(DB.Family)
            .ToElements()
        )

        families = []
        for family in collector:
            # Apply optional category filter
            if category_filter:
                fam_cat = family.FamilyCategory
                if fam_cat is None:
                    continue
                if fam_cat.Name != category_filter:
                    continue

            # Collect type names
            type_names = []
            for type_id in family.GetFamilySymbolIds():
                symbol = doc.GetElement(type_id)
                if symbol:
                    type_names.append(symbol.Name)

            families.append({
                "id": family.Id.IntegerValue,
                "name": family.Name,
                "category": family.FamilyCategory.Name if family.FamilyCategory else None,
                "is_in_place": family.IsInPlace,
                "type_count": len(type_names),
                "type_names": type_names,
            })

        return routes.make_response(data={
            "count": len(families),
            "families": families,
        })
