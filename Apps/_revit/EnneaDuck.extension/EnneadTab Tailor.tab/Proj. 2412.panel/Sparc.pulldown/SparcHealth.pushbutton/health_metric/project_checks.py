import traceback
from Autodesk.Revit import DB # pyright: ignore
from datetime import datetime


def check_project_info(doc):
    """Collect basic project information"""
    try:
        project_info = {}
        
        # Get project information
        project_data = doc.ProjectInformation
        if project_data:
            project_info["project_name"] = project_data.Name or "Unknown"
            project_info["project_number"] = project_data.Number or "Unknown"
            project_info["client_name"] = project_data.ClientName or "Unknown"
            project_info["project_phases"] = _get_project_phases(doc)
        else:
            project_info["project_name"] = "Unknown"
            project_info["project_number"] = "Unknown"
            project_info["client_name"] = "Unknown"
            project_info["project_phases"] = []
        
        # Check if workshared
        project_info["is_workshared"] = doc.IsWorkshared
        if doc.IsWorkshared:
            project_info["worksets"] = _get_worksets_info(doc)
        else:
            project_info["worksets"] = "Not Workshared"
        
        # Document title
        project_info["document_title"] = doc.Title
        
        # Check if EnneadTab is available (always False for standalone)
        project_info["is_EnneadTab_Available"] = False
        
        # Add timestamp
        project_info["timestamp"] = datetime.now().isoformat()
        
        return project_info
        
    except Exception as e:
        return {"error": str(traceback.format_exc())}


def _get_project_phases(doc):
    """Get project phases information"""
    try:
        phases = []
        phase_collector = DB.FilteredElementCollector(doc).OfClass(DB.Phase)
        for phase in phase_collector:
            phases.append(phase.Name)
        return phases
    except:
        return []


def _get_worksets_info(doc):
    """Get comprehensive worksets information - limited to user worksets only"""
    try:
        # Use FilteredWorksetCollector instead of GetWorksetIds
        all_worksets = DB.FilteredWorksetCollector(doc).ToWorksets()
        
        # Filter to user worksets only
        user_worksets = [ws for ws in all_worksets if ws.Kind == DB.WorksetKind.UserWorkset]
        
        worksets_data = {
            "total_worksets": len(user_worksets),
            "user_worksets": len(user_worksets),
            "workset_names": [],
            "workset_details": [],
            "workset_ownership": {},
            "workset_element_counts": {},
            "workset_element_ownership": {}
        }
        
        # Only process user worksets
        for workset in user_worksets:
            worksets_data["workset_names"].append(workset.Name)
            
            # Get workset details
            workset_detail = {
                "name": workset.Name,
                "kind": str(workset.Kind),
                "id": workset.Id.IntegerValue,
                "is_open": workset.IsOpen,
                "is_editable": workset.IsEditable,
                "owner": workset.Owner if hasattr(workset, 'Owner') else "Unknown",
                "creator": "Unknown",
                "last_editor": "Unknown"
            }
            
            # Try to get creator and last editor for the workset
            try:
                # Get elements in the workset to derive ownership info
                elements_in_workset = DB.FilteredElementCollector(doc).WherePasses(
                    DB.ElementWorksetFilter(workset.Id)
                ).ToElements()
                
                if elements_in_workset:
                    # Collect ownership info from elements in this workset
                    creators = {}
                    last_editors = {}
                    current_owners = {}
                    
                    for element in elements_in_workset[:100]:  # Sample first 100 elements for performance
                        try:
                            info = DB.WorksharingUtils.GetWorksharingTooltipInfo(doc, element.Id)
                            if info:
                                creator = info.Creator
                                last_editor = info.LastChangedBy
                                owner = info.Owner
                                
                                if creator:
                                    creators[creator] = creators.get(creator, 0) + 1
                                if last_editor:
                                    last_editors[last_editor] = last_editors.get(last_editor, 0) + 1
                                if owner:
                                    current_owners[owner] = current_owners.get(owner, 0) + 1
                        except:
                            continue
                    
                    # Store ownership statistics for this workset
                    worksets_data["workset_element_ownership"][workset.Name] = {
                        "creators": creators,
                        "last_editors": last_editors,
                        "current_owners": current_owners
                    }
                    
                    # Set the most common creator/editor as workset's primary creator/editor
                    if creators:
                        workset_detail["creator"] = max(creators.items(), key=lambda x: x[1])[0]
                        workset_detail["creator_count"] = creators[workset_detail["creator"]]
                    if last_editors:
                        workset_detail["last_editor"] = max(last_editors.items(), key=lambda x: x[1])[0]
                        workset_detail["last_editor_count"] = last_editors[workset_detail["last_editor"]]
                    
                worksets_data["workset_element_counts"][workset.Name] = len(elements_in_workset)
                
            except Exception as e:
                worksets_data["workset_element_counts"][workset.Name] = 0
                worksets_data["workset_element_ownership"][workset.Name] = {
                    "error": str(traceback.format_exc())
                }
            
            worksets_data["workset_details"].append(workset_detail)
                
        return worksets_data
    except Exception as e:
        return {"error": str(traceback.format_exc())}

