import traceback
from Autodesk.Revit import DB # pyright: ignore


def check_families(doc):
    """Check families metrics with advanced analysis"""
    try:
        families_data = {}
        
        # All families
        families = DB.FilteredElementCollector(doc).OfClass(DB.Family).ToElements()
        families_data["total_families"] = len(families)
        
        # In-place families
        in_place_families = [f for f in families if f.IsInPlace]
        families_data["in_place_families"] = len(in_place_families)
        
        # Non-parametric families
        non_parametric_families = [f for f in families if not f.IsParametric]
        families_data["non_parametric_families"] = len(non_parametric_families)
        
        # Generic models
        generic_models = DB.FilteredElementCollector(doc).OfClass(DB.FamilySymbol).ToElements()
        generic_models = [gm for gm in generic_models if gm.Category and "Generic Model" in gm.Category.Name]
        families_data["generic_models_types"] = len(generic_models)
        
        # Detail components
        detail_components = DB.FilteredElementCollector(doc).OfClass(DB.FamilySymbol).ToElements()
        detail_components = [dc for dc in detail_components if dc.Category and "Detail Component" in dc.Category.Name]
        families_data["detail_components"] = len(detail_components)
        
        # Find unused families
        unused_families_info = _find_unused_families(doc, families)
        families_data["unused_families_count"] = unused_families_info["count"]
        families_data["unused_families_names"] = unused_families_info["names"]
        
        # Advanced family analysis
        families_data["in_place_families_creators"] = _analyze_family_creators(doc, in_place_families)
        families_data["non_parametric_families_creators"] = _analyze_family_creators(doc, non_parametric_families)
        
        return families_data
        
    except Exception as e:
        return {"error": str(traceback.format_exc())}


def _analyze_family_creators(doc, families):
    """Analyze family creators and last editors"""
    try:
        creator_data = {}
        last_editor_data = {}
        for family in families:
            try:
                info = DB.WorksharingUtils.GetWorksharingTooltipInfo(
                    doc, family.Id)
                if info:
                    creator = info.Creator
                    last_editor = info.LastChangedBy
                    
                    if creator:
                        count = creator_data.get(creator, 0)
                        creator_data[creator] = count + 1
                    
                    if last_editor:
                        count = last_editor_data.get(last_editor, 0)
                        last_editor_data[last_editor] = count + 1
            except:
                pass  # Skip if worksharing info not available
        
        return {
            "creators": creator_data,
            "last_editors": last_editor_data
        }
        
    except Exception as e:
        return {"error": str(traceback.format_exc())}


def _find_unused_families(doc, families):
    """Find families that have no instances placed in the project"""
    try:
        # Get all family instances in the project
        all_family_instances = DB.FilteredElementCollector(doc).OfClass(DB.FamilyInstance).ToElements()
        
        # Create a set of family IDs that are actually used
        used_family_ids = set()
        for instance in all_family_instances:
            try:
                # Get the symbol (type) of this instance
                symbol = instance.Symbol
                if symbol:
                    # Get the family from the symbol
                    family = symbol.Family
                    if family:
                        used_family_ids.add(family.Id.IntegerValue)
            except:
                continue
        
        # Find unused families
        unused_families = []
        for family in families:
            if family.Id.IntegerValue not in used_family_ids:
                # Skip in-place families as they're special cases
                if not family.IsInPlace:
                    unused_families.append(family.Name)
        
        return {
            "count": len(unused_families),
            "names": sorted(unused_families)
        }
        
    except Exception as e:
        return {
            "count": 0,
            "names": [],
            "error": str(traceback.format_exc())
        }

