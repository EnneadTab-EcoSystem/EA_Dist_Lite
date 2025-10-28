import traceback
from Autodesk.Revit import DB # pyright: ignore


def check_critical_elements(doc):
    """Check critical elements metrics"""
    try:
        critical_elements_data = {}
        
        # Total elements
        all_elements = DB.FilteredElementCollector(doc).WhereElementIsNotElementType().ToElements()
        critical_elements_data["total_elements"] = len(all_elements)
        
        # Purgeable elements (2024+ feature)
        try:
            purgeable_elements = DB.FilteredElementCollector(doc).WhereElementIsNotElementType().WherePasses(
                DB.FilteredElementCollector(doc).OfClass(DB.Element).WherePasses(
                    DB.FilteredElementCollector(doc).OfClass(DB.ElementType)
                )
            ).ToElements()
            critical_elements_data["purgeable_elements"] = len(purgeable_elements)
        except:
            critical_elements_data["purgeable_elements"] = 0
        
        # Warnings with detailed element information
        all_warnings = doc.GetWarnings()
        critical_elements_data["warning_count"] = len(all_warnings)
        
        # Collect detailed warning information
        warning_details = []
        warning_creators = {}
        warning_last_editors = {}
        
        for warning in all_warnings:
            try:
                warning_info = {
                    "description": warning.GetDescriptionText(),
                    "severity": str(warning.GetSeverity()),
                    "element_ids": [],
                    "elements_info": []
                }
                
                # Get element IDs involved in the warning
                element_ids = warning.GetFailingElements()
                if element_ids:
                    for elem_id in element_ids:
                        try:
                            warning_info["element_ids"].append(elem_id.IntegerValue)
                            
                            # Get element and its creator/last editor
                            element = doc.GetElement(elem_id)
                            if element:
                                elem_info = {
                                    "id": elem_id.IntegerValue,
                                    "category": element.Category.Name if element.Category else "Unknown",
                                    "creator": "Unknown",
                                    "last_editor": "Unknown"
                                }
                                
                                # Get worksharing info
                                try:
                                    info = DB.WorksharingUtils.GetWorksharingTooltipInfo(doc, elem_id)
                                    if info:
                                        if info.Creator:
                                            elem_info["creator"] = info.Creator
                                            count = warning_creators.get(info.Creator, 0)
                                            warning_creators[info.Creator] = count + 1
                                        if info.LastChangedBy:
                                            elem_info["last_editor"] = info.LastChangedBy
                                            count = warning_last_editors.get(info.LastChangedBy, 0)
                                            warning_last_editors[info.LastChangedBy] = count + 1
                                except:
                                    pass  # Skip if worksharing info not available
                                
                                warning_info["elements_info"].append(elem_info)
                        except:
                            continue
                
                warning_details.append(warning_info)
            except Exception as e:
                # Skip warnings that fail to process
                continue
        
        critical_elements_data["warning_details"] = warning_details[:100]  # Limit to 100 warnings for performance
        critical_elements_data["warning_creators"] = warning_creators
        critical_elements_data["warning_last_editors"] = warning_last_editors
        
        # Critical warnings
        critical_warnings = [w for w in all_warnings if w.GetSeverity() == DB.FailureSeverity.Error]
        critical_elements_data["critical_warning_count"] = len(critical_warnings)
        
        # Critical warning details
        critical_warning_details = []
        for warning in critical_warnings[:50]:  # Limit to 50 critical warnings
            try:
                critical_info = {
                    "description": warning.GetDescriptionText(),
                    "element_ids": [e.IntegerValue for e in warning.GetFailingElements()]
                }
                critical_warning_details.append(critical_info)
            except:
                continue
        
        critical_elements_data["critical_warning_details"] = critical_warning_details
        
        return critical_elements_data
        
    except Exception as e:
        return {"error": str(traceback.format_exc())}


def check_rooms(doc):
    """Check rooms metrics - OPTIMIZED"""
    try:
        rooms_data = {}
        
        # BEST PRACTICE: Use OfCategory with WhereElementIsNotElementType
        rooms = DB.FilteredElementCollector(doc)\
            .OfCategory(DB.BuiltInCategory.OST_Rooms)\
            .WhereElementIsNotElementType()\
            .ToElements()
        rooms_data["total_rooms"] = len(rooms)
        
        # OPTIMIZATION: Single-pass collection for multiple conditions
        unplaced_rooms = []
        unbounded_rooms = []
        unplaced_room_details = []
        unbounded_room_details = []
        
        for room in rooms:
            try:
                # Check if room is unplaced (Location is None)
                if room.Location is None:
                    unplaced_rooms.append(room)
                    # ENHANCEMENT: Collect details about unplaced rooms
                    try:
                        room_info = {
                            "id": room.Id.IntegerValue,
                            "name": room.get_Parameter(DB.BuiltInParameter.ROOM_NAME).AsString() if room.get_Parameter(DB.BuiltInParameter.ROOM_NAME) else "<No Name>",
                            "number": room.get_Parameter(DB.BuiltInParameter.ROOM_NUMBER).AsString() if room.get_Parameter(DB.BuiltInParameter.ROOM_NUMBER) else "<No Number>",
                            "level": room.Level.Name if room.Level else "<No Level>"
                        }
                        unplaced_room_details.append(room_info)
                    except:
                        pass
                
                # Check if room is unbounded (Area == 0)
                # BEST PRACTICE: Check Area property (more reliable than parameter)
                try:
                    if room.Area == 0 or room.Area < 0.01:  # Account for floating point precision
                        unbounded_rooms.append(room)
                        # ENHANCEMENT: Collect details about unbounded rooms
                        try:
                            room_info = {
                                "id": room.Id.IntegerValue,
                                "name": room.get_Parameter(DB.BuiltInParameter.ROOM_NAME).AsString() if room.get_Parameter(DB.BuiltInParameter.ROOM_NAME) else "<No Name>",
                                "number": room.get_Parameter(DB.BuiltInParameter.ROOM_NUMBER).AsString() if room.get_Parameter(DB.BuiltInParameter.ROOM_NUMBER) else "<No Number>",
                                "level": room.Level.Name if room.Level else "<No Level>",
                                "area": room.Area
                            }
                            unbounded_room_details.append(room_info)
                        except:
                            pass
                except:
                    pass
            except:
                continue
        
        # MAINTAIN BACKWARD COMPATIBILITY: Keep original keys with counts
        rooms_data["unplaced_rooms"] = len(unplaced_rooms)
        rooms_data["unbounded_rooms"] = len(unbounded_rooms)
        
        # ENHANCEMENT: Add detailed room info (optional fields, backward compatible)
        rooms_data["unplaced_room_details"] = unplaced_room_details
        rooms_data["unbounded_room_details"] = unbounded_room_details
        
        # ENHANCEMENT: Calculate room health metrics
        if len(rooms) > 0:
            rooms_data["unplaced_percentage"] = (len(unplaced_rooms) / float(len(rooms))) * 100
            rooms_data["unbounded_percentage"] = (len(unbounded_rooms) / float(len(rooms))) * 100
        else:
            rooms_data["unplaced_percentage"] = 0
            rooms_data["unbounded_percentage"] = 0
        
        return rooms_data
        
    except Exception as e:
        return {"error": str(traceback.format_exc())}

