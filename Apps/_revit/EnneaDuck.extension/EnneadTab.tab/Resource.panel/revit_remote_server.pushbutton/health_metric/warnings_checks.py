import traceback
from Autodesk.Revit import DB # pyright: ignore


def check_warnings(doc):
    """Check warnings metrics with advanced analysis"""
    try:
        warnings_data = {}
        
        # Warnings
        all_warnings = doc.GetWarnings()
        warnings_data["warning_count"] = len(all_warnings)
        
        # Critical warnings
        CRITICAL_WARNINGS = [
            "6e1efefe-c8e0-483d-8482-150b9f1da21a",  # Elements have duplicate "Number" values
            "b4176cef-6086-45a8-a066-c3fd424c9412",  # There are identical instances in the same place
            "4f0bba25-e17f-480a-a763-d97d184be18a",  # Room Tag is outside of its Room
            "505d84a1-67e4-4987-8287-21ad1792ffe9",  # One element is completely inside another
            "8695a52f-2a88-4ca2-bedc-3676d5857af6",  # Highlighted floors overlap
            "ce3275c6-1c51-402e-8de3-df3a3d566f5c",  # Room is not in a properly enclosed region
            "83d4a67c-818c-4291-adaf-f2d33064fea8",  # Multiple Rooms are in the same enclosed region
            "e4d98f16-24ac-4cbe-9d83-80245cf41f0a",  # Area is not in a properly enclosed region
            "f657364a-e0b7-46aa-8c17-edd8e59683b9",  # Multiple Areas are in the same enclosed region
        ]
        
        critical_warnings = [w for w in all_warnings if w.GetFailureDefinitionId().Guid in CRITICAL_WARNINGS]
        warnings_data["critical_warning_count"] = len(critical_warnings)
        
        # Advanced warning analysis
        warning_category = {}
        user_personal_log = {}
        user_editor_log = {}
        failed_elements = []
        
        for warning in all_warnings:
            warning_text = warning.GetDescriptionText()
            
            # Update warning category count
            current_count = warning_category.get(warning_text, 0)
            warning_category[warning_text] = current_count + 1
            
            # Collect failing elements
            failed_elements.extend(list(warning.GetFailingElements()))
            
            # Process creator and last editor information
            try:
                failing_elements = warning.GetFailingElements()
                for element_id in failing_elements:
                    info = DB.WorksharingUtils.GetWorksharingTooltipInfo(doc, element_id)
                    if info:
                        creator = info.Creator
                        last_editor = info.LastChangedBy
                        
                        # Track creator warnings
                        if creator:
                            if creator not in user_personal_log:
                                user_personal_log[creator] = {}
                            current_log = user_personal_log[creator]
                            current_log[warning_text] = current_log.get(warning_text, 0) + 1
                        
                        # Track last editor warnings
                        if last_editor:
                            if last_editor not in user_editor_log:
                                user_editor_log[last_editor] = {}
                            current_log = user_editor_log[last_editor]
                            current_log[warning_text] = current_log.get(warning_text, 0) + 1
            except:
                pass  # Skip if worksharing info not available
        
        # Store advanced warning analysis
        warnings_data["warning_categories"] = warning_category
        warnings_data["warning_count_per_user"] = _get_user_element_counts(doc, failed_elements)
        warnings_data["warning_details_per_creator"] = user_personal_log
        warnings_data["warning_details_per_last_editor"] = user_editor_log
        
        return warnings_data
        
    except Exception as e:
        return {"error": str(traceback.format_exc())}


def _get_user_element_counts(doc, elements):
    """Get element counts per user (creator and last editor)"""
    try:
        creator_data = {}
        last_editor_data = {}
        for element in elements:
            try:
                info = DB.WorksharingUtils.GetWorksharingTooltipInfo(
                    doc, element.Id)
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
            "by_creator": creator_data,
            "by_last_editor": last_editor_data
        }
    except:
        return {}

