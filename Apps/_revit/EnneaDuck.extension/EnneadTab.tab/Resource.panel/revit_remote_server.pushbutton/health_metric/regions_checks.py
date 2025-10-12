import traceback
from Autodesk.Revit import DB # pyright: ignore


def check_filled_regions(doc):
    """Check filled regions count"""
    try:
        filled_regions_data = {}
        
        # Get all filled regions
        filled_regions = DB.FilteredElementCollector(doc).OfClass(DB.FilledRegion).ToElements()
        filled_regions_data["filled_regions"] = len(filled_regions)
        
        # Filled regions by type
        filled_region_types = {}
        for fr in filled_regions:
            try:
                fr_type = doc.GetElement(fr.GetTypeId())
                if fr_type:
                    type_name = fr_type.Name
                    current_count = filled_region_types.get(type_name, 0)
                    filled_region_types[type_name] = current_count + 1
            except:
                continue
        
        filled_regions_data["filled_regions_by_type"] = filled_region_types
        
        # Filled regions per view
        filled_regions_per_view = {}
        for fr in filled_regions:
            try:
                owner_view_id = fr.OwnerViewId
                if owner_view_id and owner_view_id != DB.ElementId.InvalidElementId:
                    view = doc.GetElement(owner_view_id)
                    if view:
                        view_name = view.Name
                        current_count = filled_regions_per_view.get(view_name, 0)
                        filled_regions_per_view[view_name] = current_count + 1
            except:
                continue
        
        filled_regions_data["filled_regions_per_view"] = filled_regions_per_view
        
        return filled_regions_data
        
    except Exception as e:
        return {"error": str(traceback.format_exc())}

