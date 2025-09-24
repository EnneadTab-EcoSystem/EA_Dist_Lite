#!/usr/bin/python
# -*- coding: utf-8 -*-

__doc__ = "Create an exploded axon by displacing elements of a selected category per level grouping in a 3D view."
__title__ = "Explode Axon"

import proDUCKtion # pyright: ignore 
proDUCKtion.validify()

from EnneadTab import ERROR_HANDLE, LOG, NOTIFICATION, DATA_CONVERSION, ENVIRONMENT
from EnneadTab.REVIT import REVIT_APPLICATION, REVIT_VIEW
from Autodesk.Revit import DB # pyright: ignore
from pyrevit import forms # pyright: ignore 

UIDOC = REVIT_APPLICATION.get_uidoc()
DOC = REVIT_APPLICATION.get_doc()

AXON_VIEW_NAME = "EXPLODED AXON DIAGRAM"

@LOG.log(__file__, __title__)
@ERROR_HANDLE.try_catch_error()
def explode_axon(doc):
    """Create exploded axon diagram by displacing elements of a chosen category based on their level height."""
    
    # Show start notification
    NOTIFICATION.messenger("Starting Level-Based Explode Axon operation...")
    
    # Prompt for target category to process
    target_category_ids, target_category_label = pick_target_category_ids(doc)

    # Prompt for per-level displacement step (in feet)
    step_feet = pick_displacement_step_feet()

    # Get or create 3D view
    view = get_or_create_3d_view(doc, AXON_VIEW_NAME)
    
    # Create level-based displacement for filtered elements
    success_count = create_level_based_displacement(doc, view, target_category_ids, step_feet)
    
    # Switch to the view using REVIT_VIEW module
    REVIT_VIEW.set_active_view_by_name(AXON_VIEW_NAME, doc)
    
    # Show completion notification
    completion_message = "Created exploded axon for [{}] with {} elements displaced.".format(target_category_label, success_count)
    NOTIFICATION.messenger(completion_message)
    print(completion_message)


def get_or_create_3d_view(doc, view_name):
    """Get existing 3D view or create a new one using REVIT_VIEW module."""
    # Try to find existing view using REVIT_VIEW module
    view = REVIT_VIEW.get_view_by_name(view_name, doc)
    if view:
        print("Found existing view: {}".format(view_name))
        return view
    
    # Start transaction for view creation/renaming
    t = DB.Transaction(doc, "Create/Modify 3D View")
    t.Start()
    
    try:
        # Create new 3D view if not found
        view_family_type = REVIT_VIEW.get_default_view_type("3d", doc)
        if view_family_type:
            view = DB.View3D.CreateIsometric(doc, view_family_type.Id)
            view.Name = view_name
            
            # Set Views_$Group to ENVIRONMENT.PLUGIN_NAME
            try:
                group_param = view.LookupParameter("Views_$Group")
                if group_param and not group_param.IsReadOnly:
                    group_param.Set(ENVIRONMENT.PLUGIN_NAME)
                    print("Set Views_$Group to: {}".format(ENVIRONMENT.PLUGIN_NAME))
            except Exception as e:
                print("Warning: Could not set Views_$Group: {}".format(str(e)))
            
            # Set Views_$Series to "ExplodeAxon"
            try:
                series_param = view.LookupParameter("Views_$Series")
                if series_param and not series_param.IsReadOnly:
                    series_param.Set("ExplodeAxon")
                    print("Set Views_$Series to: ExplodeAxon")
            except Exception as e:
                print("Warning: Could not set Views_$Series: {}".format(str(e)))
            
            print("Created new 3D view: {}".format(view_name))
            t.Commit()
            return view
        
        t.RollBack()
        raise Exception("Could not create a new 3D view. Please ensure you have appropriate permissions and view templates available.")
        
    except Exception as e:
        t.RollBack()
        raise Exception("Failed to create or modify 3D view: {}".format(str(e)))




def create_level_based_displacement(doc, view, target_category_ids=None, step_feet=20.0):
    """Create level-based displacement where filtered elements move up based on their level grouping.

    target_category_ids: Optional[Set[DB.ElementId]] of categories to include. If None, include all displaceable elements.
    step_feet: number of feet to move up per level group (default 10ft).
    """
    success_count = 0
    
    # Get all levels in the project
    levels = get_all_levels(doc)
    if not levels:
        print("No levels found in the project")
        return 0
    
    # Sort levels by elevation (lowest to highest)
    sorted_levels = sorted(levels, key=lambda x: x.Elevation)
    
    # Find the base level (lowest level)
    base_level = sorted_levels[0]
    base_elevation = base_level.Elevation
    print("Base level: {} (Elevation: {} ft)".format(base_level.Name, base_elevation))
    
    # Start transaction for displacement creation
    t = DB.Transaction(doc, "Explode Axon - Level Grouping Displacement")
    t.Start()
    
    try:
        # Remove any existing displacements first
        remove_all_existing_displacements(doc, view)
        
        # Process each level (skip base level)
        for i, level in enumerate(sorted_levels[1:], 1):  # Start from index 1 to skip base level
            # Get elements on this level filtered by target categories
            level_elements = get_all_elements_on_level(doc, level, target_category_ids)
            
            if not level_elements:
                print("Level {}: No elements found".format(level.Name))
                continue
                
            # Calculate displacement based on level grouping (level index * step)
            displacement_height = i * float(step_feet)
            displacement_vector = DB.XYZ(0, 0, displacement_height)
            
            print("Level {} (Group {}): Displacing {} elements by {} ft".format(
                level.Name, i, len(level_elements), displacement_height))
            
            # Create displacement for elements in this level
            level_success = create_view_displacement(doc, view, level_elements, displacement_vector)
            success_count += level_success
        
        # Configure view settings to ensure displacement is visible
        configure_view_for_displacement(doc, view)
        
        t.Commit()
        print("Successfully created level-grouping displacement for {} elements".format(success_count))
        
    except Exception as e:
        t.RollBack()
        print("Transaction failed: {}".format(str(e)))
        NOTIFICATION.messenger("Failed to create level-grouping exploded axon diagram: {}".format(str(e)))
        return 0
    
    return success_count


def create_view_displacement(doc, view, elements, displacement_vector):
    """Create view-specific displacement using DisplacementElement.Create() without moving actual elements."""
    success_count = 0
    
    # Start transaction for displacement creation
    t = DB.Transaction(doc, "Explode Axon - View Displacement")
    t.Start()
    
    try:
        # Convert elements to ElementId collection
        element_ids = [element.Id for element in elements]
        element_id_collection = DATA_CONVERSION.list_to_system_list(element_ids)
        
        # Remove any existing displacements for these elements
        remove_existing_displacements(doc, view, element_ids)
        
        # Create new displacement using the correct API
        # According to Revit API docs: DisplacementElement.Create(document, elementsToDisplace, displacement, ownerDBView, parentDisplacementElement)
        displacement_element = DB.DisplacementElement.Create(
            doc, 
            element_id_collection, 
            displacement_vector, 
            view, 
            None  # No parent displacement element
        )
        
        if displacement_element:
            success_count = len(element_ids)
            print("Successfully created displacement for {} elements".format(success_count))
        else:
            print("Failed to create displacement element")
        
        # Configure view settings to ensure displacement is visible
        configure_view_for_displacement(doc, view)
        
        t.Commit()
        
    except Exception as e:
        t.RollBack()
        print("Transaction failed: {}".format(str(e)))
        NOTIFICATION.messenger("Failed to create exploded axon diagram: {}".format(str(e)))
        return 0
    
    return success_count


def configure_view_for_displacement(doc, view):
    """Configure view settings to ensure displacement is visible."""
    try:
        # Set view to show displaced elements
        if hasattr(view, 'DisplacementEnabled'):
            view.DisplacementEnabled = True
        
        # Set view to show all elements
        if hasattr(view, 'ShowDisplacement'):
            view.ShowDisplacement = True
        
        # Ensure view is not in temporary hide/isolate mode
        if view.IsTemporaryViewPropertiesModeEnabled():
            view.DisableTemporaryViewMode(DB.TemporaryViewMode.TemporaryHideIsolate)
        
        # Set view scale to show more detail
        if hasattr(view, 'Scale'):
            if view.Scale > 100:  # If scale is too small, make it larger
                view.Scale = 50
        
        # CRITICAL: Make annotation categories visible (required for displacement to work)
        # According to Autodesk article, annotation categories must be visible for displacement
        enable_annotation_categories(doc, view)
        
        print("View configured for displacement visibility")
        
    except Exception as e:
        print("Warning: Could not configure view settings: {}".format(str(e)))


def enable_annotation_categories(doc, view):
    """Enable annotation categories in the view - required for displacement to work."""
    try:
        # Get all categories in the document
        categories = doc.Settings.Categories
        
        # Filter categories by CategoryType.Annotation
        annotation_categories = []
        for category in categories:
            try:
                if category.CategoryType == DB.CategoryType.Annotation:
                    annotation_categories.append(category)
            except Exception:
                # Skip categories that don't have a valid CategoryType
                continue
        
        print("Found {} annotation categories to enable".format(len(annotation_categories)))
        
        # Enable each annotation category
        enabled_count = 0
        for category in annotation_categories:
            try:
                # Make sure the category is visible in the view
                if view.GetCategoryHidden(category.Id):
                    view.SetCategoryHidden(category.Id, False)
                    enabled_count += 1
            except Exception as e:
                # Some categories might not be controllable in this view, skip them
                continue
        
        print("Enabled {} annotation categories for displacement".format(enabled_count))
        
    except Exception as e:
        print("Warning: Could not enable annotation categories: {}".format(str(e)))


def get_all_levels(doc):
    """Get all levels in the project."""
    try:
        collector = DB.FilteredElementCollector(doc)
        levels = collector.OfClass(DB.Level).WhereElementIsNotElementType()
        return list(levels)
    except Exception as e:
        print("Error getting levels: {}".format(str(e)))
        return []


def get_all_elements_on_level(doc, level, target_category_ids=None):
    """Get elements on a specific level using ElementLevelFilter and optional category filtering."""
    try:
        # Create a level filter
        level_filter = DB.ElementLevelFilter(level.Id)
        
        # Get all elements that can be displaced (exclude system families, views, etc.)
        collector = DB.FilteredElementCollector(doc)
        
        # Apply level filter and get all elements
        elements = collector.WherePasses(level_filter).WhereElementIsNotElementType()
        
        # Filter out elements that shouldn't be displaced and by category if provided
        displaceable_elements = []
        for element in elements:
            # Skip certain element types that shouldn't be displaced
            if should_skip_element_for_displacement(element):
                continue
            # Apply category filter if provided
            if target_category_ids is not None:
                try:
                    if not hasattr(element, 'Category') or element.Category is None:
                        continue
                    if element.Category.Id not in target_category_ids:
                        continue
                except Exception:
                    continue
            displaceable_elements.append(element)
        
        print("Level {}: Found {} displaceable elements out of {} total elements".format(
            level.Name, len(displaceable_elements), len(list(elements))))
        
        return displaceable_elements
        
    except Exception as e:
        print("Error getting elements on level {}: {}".format(level.Name, str(e)))
        return []


def should_skip_element_for_displacement(element):
    """Check if an element should be skipped for displacement."""
    try:
        # Skip views, sheets, and other non-model elements
        if isinstance(element, (DB.View, DB.ViewSheet, DB.ViewSchedule, DB.Viewport)):
            return True
        
        # Skip levels, grids, reference planes
        if isinstance(element, (DB.Level, DB.Grid, DB.ReferencePlane)):
            return True
        
        # Skip system families that are typically structural
        if hasattr(element, 'Category') and element.Category:
            category_name = element.Category.Name.lower()
            skip_categories = [
                'levels', 'grids', 'reference planes', 'reference lines',
                'views', 'sheets', 'schedules', 'viewports',
                'revision clouds', 'revision tags', 'text notes',
                'detail items', 'generic annotations'
            ]
            if any(skip_cat in category_name for skip_cat in skip_categories):
                return True
        
        # Skip elements that are pinned
        if hasattr(element, 'Pinned') and element.Pinned:
            return True
        
        # Skip elements that are part of groups
        if hasattr(element, 'GroupId') and element.GroupId and element.GroupId.IntegerValue != -1:
            return True
        
        # Skip elements that are hosted on other elements
        if hasattr(element, 'Host') and element.Host:
            return True
        
        # Skip elements that are view-specific
        if hasattr(element, 'ViewSpecific') and element.ViewSpecific:
            return True
        
        # Skip elements from linked files
        if hasattr(element, 'Document') and element.Document:
            try:
                element_doc_title = getattr(element.Document, 'Title', None)
                current_doc_title = getattr(DOC, 'Title', None)
                if element_doc_title and current_doc_title and element_doc_title != current_doc_title:
                    return True
            except:
                pass
        
        # Element can be displaced
        return False
        
    except Exception as e:
        print("Error checking if element should be skipped: {}".format(str(e)))
        return True  # Skip if there's an error


def group_elements_by_level(doc, elements, levels):
    """Group elements by their associated level."""
    elements_by_level = {level: [] for level in levels}
    
    for element in elements:
        try:
            # Get the level parameter
            level_param = element.get_Parameter(DB.BuiltInParameter.FAMILY_LEVEL_PARAM)
            if level_param:
                level_id = level_param.AsElementId()
                if level_id.IntegerValue != -1:
                    level = doc.GetElement(level_id)
                    if level in elements_by_level:
                        elements_by_level[level].append(element)
                        continue
            
            # Fallback: try to get level from location
            if hasattr(element, 'LevelId') and element.LevelId:
                level = doc.GetElement(element.LevelId)
                if level in elements_by_level:
                    elements_by_level[level].append(element)
                    continue
            
            # If no level found, assign to base level (lowest level)
            base_level = min(levels, key=lambda x: x.Elevation)
            elements_by_level[base_level].append(element)
            
        except Exception as e:
            print("Error grouping element by level: {}".format(str(e)))
            # Assign to base level as fallback
            base_level = min(levels, key=lambda x: x.Elevation)
            elements_by_level[base_level].append(element)
    
    return elements_by_level


def remove_all_existing_displacements(doc, view):
    """Remove all existing displacement elements in the view."""
    try:
        collector = DB.FilteredElementCollector(doc, view.Id)
        displacement_elements = collector.OfClass(DB.DisplacementElement).WhereElementIsNotElementType()
        
        for displacement_element in displacement_elements:
            try:
                doc.Delete(displacement_element.Id)
            except Exception as e:
                print("Failed to remove displacement element: {}".format(str(e)))
                
        print("Removed all existing displacement elements")
        
    except Exception as e:
        print("Error removing all displacements: {}".format(str(e)))


def create_displacement_for_elements(doc, view, elements, displacement_vector):
    """Create displacement for a group of elements."""
    try:
        # Convert elements to ElementId collection
        element_ids = [element.Id for element in elements]
        element_id_collection = DATA_CONVERSION.list_to_system_list(element_ids)
        
        # Create displacement using the correct API
        displacement_element = DB.DisplacementElement.Create(
            doc, 
            element_id_collection, 
            displacement_vector, 
            view, 
            None  # No parent displacement element
        )
        
        if displacement_element:
            print("Successfully created displacement for {} elements".format(len(element_ids)))
            return len(element_ids)
        else:
            print("Failed to create displacement element")
            return 0
            
    except Exception as e:
        print("Error creating displacement for elements: {}".format(str(e)))
        return 0


def check_element_movability(element):
    """Check if an element can be displaced and return reason if it cannot."""
    try:
        # Check if element is pinned
        if element.Pinned:
            return "Element is pinned"
        
        # Check if element is part of a group
        if element.GroupId and element.GroupId.IntegerValue != -1:
            return "Element is part of a group"
        
        # Check if element is hosted
        if hasattr(element, 'Host') and element.Host:
            return "Element is hosted on another element"
        
        # Check if element is view-specific
        if hasattr(element, 'ViewSpecific') and element.ViewSpecific:
            return "Element is view-specific"
        
        # Check if element is a system family (walls, floors, etc.)
        if hasattr(element, 'Category') and element.Category:
            category_name = element.Category.Name.lower()
            if any(system_type in category_name for system_type in ['walls', 'floors', 'ceilings', 'roofs', 'stairs']):
                return "Element is a system family"
        
        # Check if element is from a linked file
        if hasattr(element, 'Document') and element.Document:
            try:
                element_doc_title = getattr(element.Document, 'Title', None)
                current_doc_title = getattr(DOC, 'Title', None)
                if element_doc_title and current_doc_title and element_doc_title != current_doc_title:
                    return "Element is from linked file"
            except:
                pass
        
        # Check if element has constraints
        if hasattr(element, 'Constraints') and element.Constraints:
            return "Element has constraints"
        
        # Element can be displaced
        return None
        
    except Exception as e:
        return "Error checking element: {}".format(str(e))


def remove_existing_displacements(doc, view, element_ids):
    """Remove existing displacement elements for the given elements."""
    try:
        # Get all displacement elements in the view
        collector = DB.FilteredElementCollector(doc, view.Id)
        displacement_elements = collector.OfClass(DB.DisplacementElement).WhereElementIsNotElementType()
        
        for displacement_element in displacement_elements:
            # Check if this displacement contains any of our target elements
            displaced_elements = displacement_element.GetDisplacedElementIds()
            if any(element_id in displaced_elements for element_id in element_ids):
                try:
                    doc.Delete(displacement_element.Id)
                    print("Removed existing displacement for elements")
                except Exception as e:
                    print("Failed to remove existing displacement: {}".format(str(e)))
                    
    except Exception as e:
        print("Error removing existing displacements: {}".format(str(e)))


def pick_target_category_ids(doc):
    """Ask user which categories to process and return a set of category ElementIds and a label."""
    # Combined options and BuiltInCategory mapping
    category_options = {
        "Mass": [DB.BuiltInCategory.OST_Mass],
        "Furniture": [DB.BuiltInCategory.OST_Furniture, DB.BuiltInCategory.OST_FurnitureSystems],
        "Generic Models": [DB.BuiltInCategory.OST_GenericModel],
        "Specialty Equipment": [DB.BuiltInCategory.OST_SpecialityEquipment],
        "Walls": [DB.BuiltInCategory.OST_Walls],
        "Floors": [DB.BuiltInCategory.OST_Floors],
        "Doors": [DB.BuiltInCategory.OST_Doors],
        "Windows": [DB.BuiltInCategory.OST_Windows],
    }

    # Use pyrevit SelectFromList with multiselect
    selected_categories = forms.SelectFromList.show(
        list(category_options.keys()),
        title="Explode Axon - Categories",
        multiselect=True,
        button_name="Select Categories to Process"
    )

    # Default to Furniture if no selection or cancelled
    if not selected_categories:
        selected_categories = ["Furniture"]

    # Collect all BuiltInCategories for selected options
    all_bics = []
    for choice in selected_categories:
        if choice in category_options:
            all_bics.extend(category_options[choice])

    category_ids = set()
    for bic in all_bics:
        try:
            cat = DB.Category.GetCategory(doc, bic)
            if cat is not None:
                category_ids.add(cat.Id)
        except Exception:
            continue

    # Create a descriptive label for the selection
    if len(selected_categories) == 1:
        choice_label = selected_categories[0]
    else:
        choice_label = "Multiple Categories ({})".format(", ".join(selected_categories))

    return category_ids, choice_label


def pick_displacement_step_feet():
    """Ask user how much to move up per level group (in feet) using a slider. Returns a float."""
    try:
        # Use pyrevit slider with wider range
        step_value = forms.ask_for_one_number(
            default=20.0,
            min=1.0,
            max=100.0,
            prompt="How many feet per level should elements be displaced?",
            title="Explode Axon - Displacement Step"
        )
        
        if step_value is None:
            return 20.0  # Default value if cancelled
            
        return float(step_value)
        
    except Exception as e:
        print("Error getting displacement step: {}".format(str(e)))
        return 20.0  # Default fallback


################## main code below #####################
if __name__ == "__main__":
    explode_axon(DOC)

