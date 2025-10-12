import traceback
from Autodesk.Revit import DB # pyright: ignore


def check_templates_filters(doc):
    """Check templates and filters metrics"""
    try:
        templates_data = {}
        
        # View templates
        all_views = DB.FilteredElementCollector(doc).OfClass(DB.View).ToElements()
        all_true_views = [v for v in all_views if v.IsTemplate == False]
        all_templates = [v for v in all_views if v.IsTemplate == True]
        
        templates_data["view_templates"] = len(all_templates)
        
        # Check for unused view templates
        usage = {}
        for view in all_true_views:
            template = doc.GetElement(view.ViewTemplateId)
            if not template:
                continue
            key = template.Name
            count = usage.get(key, 0)
            usage[key] = count + 1
        
        used_template_names = set(usage.keys())
        unused_templates = [x for x in all_templates if x.Name not in used_template_names]
        templates_data["unused_view_templates"] = len(unused_templates)
        
        # Collect detailed view template information with creator and last editor
        template_details = []
        for template in all_templates:
            try:
                template_info = {
                    "name": template.Name,
                    "id": template.Id.IntegerValue,
                    "view_type": str(template.ViewType) if hasattr(template, 'ViewType') else "Unknown",
                    "is_used": template.Name in used_template_names,
                    "usage_count": usage.get(template.Name, 0),
                    "creator": "Unknown",
                    "last_editor": "Unknown"
                }
                
                # Get creator and last editor from WorksharingUtils
                try:
                    info = DB.WorksharingUtils.GetWorksharingTooltipInfo(doc, template.Id)
                    if info:
                        if info.Creator:
                            template_info["creator"] = info.Creator
                        if info.LastChangedBy:
                            template_info["last_editor"] = info.LastChangedBy
                except:
                    pass  # Skip if worksharing info not available
                
                template_details.append(template_info)
            except Exception as e:
                # Skip templates that fail
                continue
        
        templates_data["view_template_details"] = template_details
        
        # Add creator and last editor statistics
        templates_data["view_template_creators"] = _analyze_template_creators(doc, all_templates)
        templates_data["unused_view_template_details"] = [
            {
                "name": t.Name,
                "id": t.Id.IntegerValue,
                "view_type": str(t.ViewType) if hasattr(t, 'ViewType') else "Unknown"
            }
            for t in unused_templates
        ]
        
        # Filters
        filters = DB.FilteredElementCollector(doc).OfClass(DB.ParameterFilterElement).ToElements()
        templates_data["filters"] = len(filters)
        
        # Unused filters - check if filters are used in views
        used_filters = set()
        for view in all_true_views:
            try:
                # Only check views that support filters
                if hasattr(view, 'GetFilters'):
                    filter_ids = view.GetFilters()
                    if filter_ids:
                        for filter_id in filter_ids:
                            try:
                                # Defensive access to IntegerValue
                                if hasattr(filter_id, 'IntegerValue'):
                                    used_filters.add(filter_id.IntegerValue)
                                else:
                                    # Fallback: convert to int if possible
                                    used_filters.add(int(filter_id))
                            except:
                                continue
            except Exception as e:
                # Skip views that don't support filters
                continue
        
        # Safely get unused filters
        unused_filters = []
        for f in filters:
            try:
                filter_int_id = f.Id.IntegerValue if hasattr(f.Id, 'IntegerValue') else int(f.Id)
                if filter_int_id not in used_filters:
                    unused_filters.append(f)
            except:
                continue
        templates_data["unused_filters"] = len(unused_filters)
        
        return templates_data
        
    except Exception as e:
        return {"error": str(traceback.format_exc())}


def _analyze_template_creators(doc, templates):
    """Analyze view template creators and last editors"""
    try:
        creator_data = {}
        last_editor_data = {}
        for template in templates:
            try:
                info = DB.WorksharingUtils.GetWorksharingTooltipInfo(
                    doc, template.Id)
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

