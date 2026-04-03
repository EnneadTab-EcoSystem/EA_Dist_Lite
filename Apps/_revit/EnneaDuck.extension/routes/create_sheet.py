# -*- coding: utf-8 -*-
"""Create sheet route handler for EnneadTab MCP."""
import json

from pyrevit import routes
from Autodesk.Revit import DB


def register_create_sheet_routes(api):
    @api.route("/enneadtab/create-sheet/", methods=["POST"])
    def create_sheet(doc, request):
        if not doc:
            return routes.make_response(
                data={"error": "No document open"},
                status_code=400,
            )

        data = json.loads(request.data) if isinstance(request.data, str) else request.data
        sheet_number = data.get("sheet_number")
        sheet_name = data.get("sheet_name")
        title_block_name = data.get("title_block_name")

        if not sheet_number or not sheet_name:
            return routes.make_response(
                data={"error": "sheet_number and sheet_name are required"},
                status_code=400,
            )

        # Find title block family symbol
        tb_id = DB.ElementId.InvalidElementId
        if title_block_name:
            collector = (
                DB.FilteredElementCollector(doc)
                .OfCategory(DB.BuiltInCategory.OST_TitleBlocks)
                .OfClass(DB.FamilySymbol)
                .ToElements()
            )
            for symbol in collector:
                family_name = symbol.Family.Name if symbol.Family else ""
                full_name = "{}: {}".format(family_name, symbol.Name)
                if (symbol.Name == title_block_name
                        or family_name == title_block_name
                        or full_name == title_block_name):
                    tb_id = symbol.Id
                    break

            if tb_id == DB.ElementId.InvalidElementId:
                return routes.make_response(
                    data={"error": "Title block not found: {}".format(title_block_name)},
                    status_code=404,
                )
        else:
            # Use the first available title block
            collector = (
                DB.FilteredElementCollector(doc)
                .OfCategory(DB.BuiltInCategory.OST_TitleBlocks)
                .OfClass(DB.FamilySymbol)
                .FirstElement()
            )
            if collector:
                tb_id = collector.Id

        t = DB.Transaction(doc, "MCP: Create Sheet")
        try:
            t.Start()

            new_sheet = DB.ViewSheet.Create(doc, tb_id)
            new_sheet.SheetNumber = sheet_number
            new_sheet.Name = sheet_name

            t.Commit()
        except Exception as e:
            if t.HasStarted():
                t.RollBack()
            return routes.make_response(
                data={"error": str(e)},
                status_code=500,
            )

        return routes.make_response(data={
            "sheet_id": new_sheet.Id.IntegerValue,
            "sheet_number": sheet_number,
            "sheet_name": sheet_name,
            "success": True,
        })
