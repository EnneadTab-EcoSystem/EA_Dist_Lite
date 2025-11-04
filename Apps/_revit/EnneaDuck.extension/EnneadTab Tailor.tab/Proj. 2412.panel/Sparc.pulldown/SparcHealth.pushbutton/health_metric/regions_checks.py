import traceback
from Autodesk.Revit import DB # pyright: ignore


def check_filled_regions(doc):
    """Check filled regions count - OPTIMIZED"""
    try:
        filled_regions_data = {}
        
        # BEST PRACTICE: Single collector call
        filled_regions = DB.FilteredElementCollector(doc).OfClass(DB.FilledRegion).ToElements()
        filled_regions_data["filled_regions"] = len(filled_regions)
        
        # OPTIMIZATION: Single-pass iteration for all metrics
        filled_region_types = {}
        filled_regions_per_view = {}
        type_id_cache = {}  # Cache type elements to avoid repeated doc.GetElement calls
        view_id_cache = {}  # Cache view elements to avoid repeated doc.GetElement calls
        
        for fr in filled_regions:
            try:
                # OPTIMIZATION: Batch type name lookup with caching
                type_id = fr.GetTypeId()
                type_id_int = type_id.IntegerValue
                
                if type_id_int not in type_id_cache:
                    fr_type = doc.GetElement(type_id)
                    type_id_cache[type_id_int] = fr_type.Name if fr_type else "Unknown Type"
                
                type_name = type_id_cache[type_id_int]
                filled_region_types[type_name] = filled_region_types.get(type_name, 0) + 1
                
                # OPTIMIZATION: Batch view name lookup with caching
                owner_view_id = fr.OwnerViewId
                if owner_view_id and owner_view_id != DB.ElementId.InvalidElementId:
                    view_id_int = owner_view_id.IntegerValue
                    
                    if view_id_int not in view_id_cache:
                        view = doc.GetElement(owner_view_id)
                        view_id_cache[view_id_int] = view.Name if view else "Unknown View"
                    
                    view_name = view_id_cache[view_id_int]
                    filled_regions_per_view[view_name] = filled_regions_per_view.get(view_name, 0) + 1
            except:
                continue
        
        # MAINTAIN BACKWARD COMPATIBILITY: Keep original keys
        filled_regions_data["filled_regions_by_type"] = filled_region_types
        filled_regions_data["filled_regions_per_view"] = filled_regions_per_view
        
        # ENHANCEMENT: Add top views with most filled regions (helps identify problem views)
        if filled_regions_per_view:
            sorted_views = sorted(filled_regions_per_view.items(), key=lambda x: x[1], reverse=True)[:10]
            filled_regions_data["top_filled_region_views"] = [{"view": v, "count": c} for v, c in sorted_views]
        
        return filled_regions_data
        
    except Exception as e:
        return {"error": str(traceback.format_exc())}

