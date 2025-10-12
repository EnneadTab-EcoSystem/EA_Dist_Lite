import traceback
from Autodesk.Revit import DB # pyright: ignore


def check_groups(doc):
    """Check groups metrics with usage analysis"""
    try:
        groups_data = {}
        
        # Model groups
        model_groups = DB.FilteredElementCollector(doc).OfClass(DB.Group).ToElements()
        groups_data["model_group_instances"] = len(model_groups)
        
        # Model group types
        model_group_types = DB.FilteredElementCollector(doc).OfClass(DB.GroupType).ToElements()
        groups_data["model_group_types"] = len(model_group_types)
        
        # Detail groups - use category instead of class
        detail_groups = DB.FilteredElementCollector(doc).OfCategory(DB.BuiltInCategory.OST_IOSDetailGroups).WhereElementIsNotElementType().ToElements()
        groups_data["detail_group_instances"] = len(detail_groups)
        
        # Detail group types
        detail_group_types = DB.FilteredElementCollector(doc).OfCategory(DB.BuiltInCategory.OST_IOSDetailGroups).WhereElementIsElementType().ToElements()
        groups_data["detail_group_types"] = len(detail_group_types)
        
        # Advanced group usage analysis
        _analyze_group_usage(model_groups, "model_group", groups_data)
        _analyze_group_usage(detail_groups, "detail_group", groups_data)
        
        return groups_data
        
    except Exception as e:
        return {"error": str(traceback.format_exc())}


def _analyze_group_usage(groups, group_type, groups_data):
    """Analyze group usage patterns"""
    try:
        type_data = {}
        for group in groups:
            type_name = group.Name
            current_count = type_data.get(type_name, 0)
            type_data[type_name] = current_count + 1
        
        # Flag groups used more than 10 times
        threshold = 10
        overused_groups = [type_name for type_name, count in type_data.items() if count > threshold]
        
        groups_data["{}_usage_analysis".format(group_type)] = {
            "total_types": len(type_data),
            "overused_count": len(overused_groups),
            "overused_groups": overused_groups,
            "usage_threshold": threshold,
            "type_usage": type_data
        }
        
    except Exception as e:
        groups_data["{}_usage_analysis_error".format(group_type)] = str(e)

