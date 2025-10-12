import traceback
from Autodesk.Revit import DB # pyright: ignore


def check_reference_planes(doc):
    """Check reference planes metrics"""
    try:
        ref_planes_data = {}
        
        # Reference planes
        all_ref_planes = DB.FilteredElementCollector(doc).OfClass(DB.ReferencePlane).ToElements()
        # Only get ref planes whose workset is not read-only (project refs, not family refs)
        ref_planes = []
        for rp in all_ref_planes:
            try:
                workset_param = rp.LookupParameter("Workset")
                if workset_param and not workset_param.IsReadOnly:
                    ref_planes.append(rp)
            except:
                # If we can't check workset, include it (safer approach)
                ref_planes.append(rp)
        
        ref_planes_data["reference_planes"] = len(ref_planes)
        
        # Unnamed reference planes
        unnamed_ref_planes = [rp for rp in ref_planes if 
                             rp.Name == "Reference Plane" or 
                             not rp.Name or 
                             rp.Name.strip() == ""]
        ref_planes_data["reference_planes_no_name"] = len(unnamed_ref_planes)
        
        return ref_planes_data
        
    except Exception as e:
        return {"error": str(traceback.format_exc())}


def check_grids_levels(doc):
    """Check grids and levels pinning status"""
    try:
        grids_levels_data = {}
        
        # Grids
        grids = DB.FilteredElementCollector(doc).OfClass(DB.Grid).ToElements()
        grids_levels_data["total_grids"] = len(grids)
        
        unpinned_grids = [g for g in grids if not g.Pinned]
        grids_levels_data["unpinned_grids"] = len(unpinned_grids)
        grids_levels_data["pinned_grids"] = len(grids) - len(unpinned_grids)
        
        # Levels
        levels = DB.FilteredElementCollector(doc).OfClass(DB.Level).ToElements()
        grids_levels_data["total_levels"] = len(levels)
        
        unpinned_levels = [l for l in levels if not l.Pinned]
        grids_levels_data["unpinned_levels"] = len(unpinned_levels)
        grids_levels_data["pinned_levels"] = len(levels) - len(unpinned_levels)
        
        # Get details of unpinned grids
        unpinned_grid_names = []
        for grid in unpinned_grids:
            try:
                unpinned_grid_names.append(grid.Name)
            except:
                continue
        grids_levels_data["unpinned_grid_names"] = sorted(unpinned_grid_names)
        
        # Get details of unpinned levels
        unpinned_level_names = []
        for level in unpinned_levels:
            try:
                unpinned_level_names.append(level.Name)
            except:
                continue
        grids_levels_data["unpinned_level_names"] = sorted(unpinned_level_names)
        
        return grids_levels_data
        
    except Exception as e:
        return {"error": str(traceback.format_exc())}

