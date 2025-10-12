import traceback
from Autodesk.Revit import DB # pyright: ignore


def check_materials(doc):
    """Check materials count"""
    try:
        materials_data = {}
        materials = DB.FilteredElementCollector(doc).OfClass(DB.Material).ToElements()
        materials_data["materials"] = len(materials)
        
        return materials_data
    except Exception as e:
        return {"error": str(traceback.format_exc())}


def check_line_count(doc):
    """Check detail and model line usage with per-view breakdown"""
    try:
        line_data = {}
        
        # Collect all curve elements
        curve_elements = DB.FilteredElementCollector(doc).OfClass(DB.CurveElement).ToElements()
        
        # Separate detail lines and model lines
        detail_lines = []
        model_lines = []
        
        for ce in curve_elements:
            curve_type = ce.CurveElementType.ToString()
            if curve_type == "DetailCurve":
                detail_lines.append(ce)
            elif curve_type == "ModelCurve":
                model_lines.append(ce)
        
        # Total counts
        line_data["detail_lines_total"] = len(detail_lines)
        line_data["model_lines_total"] = len(model_lines)
        
        # Detail lines per view
        detail_lines_per_view = {}
        for detail_line in detail_lines:
            try:
                # Get the view that owns this detail line
                owner_view_id = detail_line.OwnerViewId
                if owner_view_id and owner_view_id != DB.ElementId.InvalidElementId:
                    view = doc.GetElement(owner_view_id)
                    if view:
                        view_name = view.Name
                        current_count = detail_lines_per_view.get(view_name, 0)
                        detail_lines_per_view[view_name] = current_count + 1
            except Exception as e:
                # Skip if we can't get the view
                continue
        
        line_data["detail_lines_per_view"] = detail_lines_per_view
        
        return line_data
        
    except Exception as e:
        return {"error": str(traceback.format_exc())}

