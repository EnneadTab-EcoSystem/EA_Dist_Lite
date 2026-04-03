# -*- coding: utf-8 -*-
"""View image export route handler for EnneadTab MCP."""
import os
import tempfile

from pyrevit import routes, revit
from Autodesk.Revit import DB

try:
    from System.IO import File
except ImportError:
    File = None


def register_view_image_routes(api):
    @api.route("/enneadtab/view-image/", methods=["GET"])
    def get_view_image(doc, request):
        if not doc:
            return routes.make_response(
                data={"error": "No document open"},
                status_code=400,
            )

        view_name = request.get("name")

        if view_name:
            # Find view by name
            collector = (
                DB.FilteredElementCollector(doc)
                .OfClass(DB.View)
                .ToElements()
            )
            target_view = None
            for v in collector:
                if not v.IsTemplate and v.Name == view_name:
                    target_view = v
                    break

            if target_view is None:
                return routes.make_response(
                    data={"error": "View not found: {}".format(view_name)},
                    status_code=404,
                )
        else:
            # Use the active view
            uidoc = revit.uidoc
            if uidoc is None:
                return routes.make_response(
                    data={"error": "No active UI document"},
                    status_code=400,
                )
            target_view = uidoc.ActiveView

        # Create temp directory for export
        temp_dir = tempfile.mkdtemp(prefix="enneadtab_mcp_")
        file_name = "view_export"

        opts = DB.ImageExportOptions()
        opts.ExportRange = DB.ExportRange.SetOfViews
        opts.SetViewsAndSheets([target_view.Id])
        opts.HLRandWFViewsFileType = DB.ImageFileType.PNG
        opts.ShadowViewsFileType = DB.ImageFileType.PNG
        opts.ImageResolution = DB.ImageResolution.DPI_150
        opts.ZoomType = DB.ZoomFitType.FitToPage
        opts.PixelSize = 1920
        opts.FilePath = os.path.join(temp_dir, file_name)

        try:
            doc.ExportImage(opts)
        except Exception as e:
            return routes.make_response(
                data={"error": "Image export failed: {}".format(str(e))},
                status_code=500,
            )

        # Find the exported file (Revit may append suffix)
        exported_file = None
        for f in os.listdir(temp_dir):
            if f.endswith(".png"):
                exported_file = os.path.join(temp_dir, f)
                break

        if exported_file is None:
            return routes.make_response(
                data={"error": "Export produced no PNG file"},
                status_code=500,
            )

        # Read the file bytes
        with open(exported_file, "rb") as fh:
            image_bytes = fh.read()

        # Clean up temp files
        try:
            os.remove(exported_file)
            os.rmdir(temp_dir)
        except Exception:
            pass

        import base64
        encoded = base64.b64encode(image_bytes).decode("ascii")

        return routes.make_response(data={
            "view_name": target_view.Name,
            "view_id": target_view.Id.IntegerValue,
            "image_base64": encoded,
            "format": "png",
        })
