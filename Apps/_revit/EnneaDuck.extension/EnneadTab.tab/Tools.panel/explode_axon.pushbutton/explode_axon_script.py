#!/usr/bin/python
# -*- coding: utf-8 -*-

__doc__ = "Create an exploded axon diagram by displacing furniture elements upward by 50 feet in a 3D view."
__title__ = "Explode Axon"

import proDUCKtion # pyright: ignore 
proDUCKtion.validify()

from EnneadTab import ERROR_HANDLE, LOG, NOTIFICATION, TIME, USER, ENVIRONMENT, DATA_CONVERSION
from EnneadTab.REVIT import REVIT_APPLICATION, REVIT_SELECTION, REVIT_VIEW
from Autodesk.Revit import DB # pyright: ignore 

UIDOC = REVIT_APPLICATION.get_uidoc()
DOC = REVIT_APPLICATION.get_doc()

AXON_VIEW_NAME = "EXPLODED AXON DIAGRAM"

@LOG.log(__file__, __title__)
@ERROR_HANDLE.try_catch_error()
def explode_axon(doc):
    """Create exploded axon diagram by displacing ALL elements based on their level height."""
    
    # Show start notification
    NOTIFICATION.messenger("Starting Level-Based Explode Axon operation...")
    
    # Get or create 3D view
    view = get_or_create_3d_view(doc, AXON_VIEW_NAME)
    
    # Create level-based displacement for ALL elements
    success_count = create_level_based_displacement(doc, view)
    
    # Switch to the view using REVIT_VIEW module
    REVIT_VIEW.set_active_view_by_name(AXON_VIEW_NAME, doc)
    
    # Show completion notification
    completion_message = "Created level-based exploded axon diagram with {} elements displaced.".format(success_count)
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
            print("Created new 3D view: {}".format(view_name))
            t.Commit()
            return view
        
        # Fallback: get first available 3D view
        collector = DB.FilteredElementCollector(doc)
        views = collector.OfClass(DB.View3D).WhereElementIsNotElementType()
        
        for view in views:
            if not view.IsTemplate:
                view.Name = view_name
                print("Renamed existing 3D view to: {}".format(view_name))
                t.Commit()
                return view
        
        t.RollBack()
        raise Exception("Could not create or find a suitable 3D view")
        
    except Exception as e:
        t.RollBack()
        raise Exception("Failed to create or modify 3D view: {}".format(str(e)))


def get_furniture_elements(doc):
    """Get all furniture elements in the model with comprehensive error handling."""
    try:
        print("Starting furniture element collection...")
        
        # Get furniture elements
        collector = DB.FilteredElementCollector(doc)
        furniture_elements = collector.OfCategory(DB.BuiltInCategory.OST_Furniture).WhereElementIsNotElementType()
        furniture_list = list(furniture_elements)
        print("Found {} furniture elements".format(len(furniture_list)))
        
        # Get furniture systems
        collector = DB.FilteredElementCollector(doc)
        furniture_systems = collector.OfCategory(DB.BuiltInCategory.OST_FurnitureSystems).WhereElementIsNotElementType()
        furniture_systems_list = list(furniture_systems)
        print("Found {} furniture systems".format(len(furniture_systems_list)))
        
   
        # Combine all furniture-like elements
        all_furniture = furniture_list + furniture_systems_list 
        
        print("Total furniture-like elements found: {}".format(len(all_furniture)))
        
        
        
        return all_furniture
        
    except Exception as e:
        print("Error collecting furniture elements: {}".format(str(e)))
        ERROR_HANDLE.print_note("Error collecting furniture elements: {}".format(str(e)))
        return []


def create_level_based_displacement(doc, view):
    """Create level-based displacement where ALL elements move up based on their level grouping."""
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
            # Get ALL elements on this level using FilteredElementCollector with level filter
            level_elements = get_all_elements_on_level(doc, level)
            
            if not level_elements:
                print("Level {}: No elements found".format(level.Name))
                continue
                
            # Calculate displacement based on level grouping (level index * 10ft)
            # Level 1 (base): 0ft displacement
            # Level 2: 10ft displacement
            # Level 3: 20ft displacement
            # Level 4: 30ft displacement
            # etc.
            displacement_height = i * 10  # Each level group moves up by 10ft more than the previous
            displacement_vector = DB.XYZ(0, 0, displacement_height)
            
            print("Level {} (Group {}): Displacing {} elements by {} ft".format(
                level.Name, i, len(level_elements), displacement_height))
            
            # Create displacement for elements in this level
            level_success = create_displacement_for_elements(doc, view, level_elements, displacement_vector)
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
        # List of annotation categories that need to be visible
        annotation_categories = [
            DB.BuiltInCategory.OST_TextNotes,
            DB.BuiltInCategory.OST_DetailItems,
            DB.BuiltInCategory.OST_GenericAnnotation,
            DB.BuiltInCategory.OST_RevisionClouds,
            DB.BuiltInCategory.OST_RevisionTags,
            DB.BuiltInCategory.OST_Viewports,
            DB.BuiltInCategory.OST_Sheets,
            DB.BuiltInCategory.OST_ReferenceLines,
            DB.BuiltInCategory.OST_ReferencePlanes,
            DB.BuiltInCategory.OST_Grids,
            DB.BuiltInCategory.OST_Levels,
            DB.BuiltInCategory.OST_Dimensions,
            DB.BuiltInCategory.OST_SpotDimensions,
            DB.BuiltInCategory.OST_SpotElevations,
            DB.BuiltInCategory.OST_SpotCoordinates,
            DB.BuiltInCategory.OST_IndependentTags,
            DB.BuiltInCategory.OST_MultiReferenceAnnotations,
            DB.BuiltInCategory.OST_KeynoteTags,
            DB.BuiltInCategory.OST_KeynoteText,
            DB.BuiltInCategory.OST_StructuralFramingTags,
            DB.BuiltInCategory.OST_StructuralColumnTags,
            DB.BuiltInCategory.OST_StructuralFoundationTags,
            DB.BuiltInCategory.OST_StructuralConnectionTags,
            DB.BuiltInCategory.OST_StructuralRebarTags,
            DB.BuiltInCategory.OST_StructuralAreaReinforcementTags,
            DB.BuiltInCategory.OST_StructuralPathReinforcementTags,
            DB.BuiltInCategory.OST_StructuralFabricAreasTags,
            DB.BuiltInCategory.OST_StructuralFabricReinforcementTags,
            DB.BuiltInCategory.OST_StructuralTrussTags,
            DB.BuiltInCategory.OST_MechanicalEquipmentTags,
            DB.BuiltInCategory.OST_DuctTags,
            DB.BuiltInCategory.OST_DuctFittingTags,
            DB.BuiltInCategory.OST_DuctAccessoryTags,
            DB.BuiltInCategory.OST_DuctCurvesTags,
            DB.BuiltInCategory.OST_PipeTags,
            DB.BuiltInCategory.OST_PipeFittingTags,
            DB.BuiltInCategory.OST_PipeAccessoryTags,
            DB.BuiltInCategory.OST_PipeCurvesTags,
            DB.BuiltInCategory.OST_CableTrayTags,
            DB.BuiltInCategory.OST_ConduitTags,
            DB.BuiltInCategory.OST_ElectricalEquipmentTags,
            DB.BuiltInCategory.OST_ElectricalFixturesTags,
            DB.BuiltInCategory.OST_LightingFixturesTags,
            DB.BuiltInCategory.OST_ElectricalDevicesTags,
            DB.BuiltInCategory.OST_DataDevicesTags,
            DB.BuiltInCategory.OST_CommunicationDevicesTags,
            DB.BuiltInCategory.OST_NurseCallDevicesTags,
            DB.BuiltInCategory.OST_SecurityDevicesTags,
            DB.BuiltInCategory.OST_FireAlarmDevicesTags,
            DB.BuiltInCategory.OST_TelephoneDevicesTags,
            DB.BuiltInCategory.OST_DoorTags,
            DB.BuiltInCategory.OST_WindowTags,
            DB.BuiltInCategory.OST_RoomTags,
            DB.BuiltInCategory.OST_AreaTags,
            DB.BuiltInCategory.OST_SpaceTags,
            DB.BuiltInCategory.OST_PlumbingFixturesTags,
            DB.BuiltInCategory.OST_MechanicalEquipmentTags,
            DB.BuiltInCategory.OST_SpecialtyEquipmentTags,
            DB.BuiltInCategory.OST_FurnitureTags,
            DB.BuiltInCategory.OST_FurnitureSystemsTags,
            DB.BuiltInCategory.OST_CaseworkTags,
            DB.BuiltInCategory.OST_PlantingTags,
            DB.BuiltInCategory.OST_SiteTags,
            DB.BuiltInCategory.OST_ParkingTags,
            DB.BuiltInCategory.OST_MassTags,
            DB.BuiltInCategory.OST_CurtainWallMullionsTags,
            DB.BuiltInCategory.OST_CurtainPanelsTags,
            DB.BuiltInCategory.OST_CurtainWallTags,
            DB.BuiltInCategory.OST_StairsTags,
            DB.BuiltInCategory.OST_RampsTags,
            DB.BuiltInCategory.OST_ElevatorTags,
            DB.BuiltInCategory.OST_EscalatorTags,
            DB.BuiltInCategory.OST_MovingWalkwayTags,
            DB.BuiltInCategory.OST_EntourageTags,
            DB.BuiltInCategory.OST_ModelTextTags,
            DB.BuiltInCategory.OST_GenericModelTags,
            DB.BuiltInCategory.OST_StructuralFramingTags,
            DB.BuiltInCategory.OST_StructuralColumnsTags,
            DB.BuiltInCategory.OST_StructuralFoundationsTags,
            DB.BuiltInCategory.OST_StructuralConnectionsTags,
            DB.BuiltInCategory.OST_StructuralRebarTags,
            DB.BuiltInCategory.OST_StructuralAreaReinforcementTags,
            DB.BuiltInCategory.OST_StructuralPathReinforcementTags,
            DB.BuiltInCategory.OST_StructuralFabricAreasTags,
            DB.BuiltInCategory.OST_StructuralFabricReinforcementTags,
            DB.BuiltInCategory.OST_StructuralTrussTags,
            DB.BuiltInCategory.OST_WallsTags,
            DB.BuiltInCategory.OST_CurtainWallMullionsTags,
            DB.BuiltInCategory.OST_CurtainPanelsTags,
            DB.BuiltInCategory.OST_CurtainWallTags,
            DB.BuiltInCategory.OST_RoofsTags,
            DB.BuiltInCategory.OST_CeilingsTags,
            DB.BuiltInCategory.OST_FloorsTags,
            DB.BuiltInCategory.OST_StairsTags,
            DB.BuiltInCategory.OST_RampsTags,
            DB.BuiltInCategory.OST_ElevatorTags,
            DB.BuiltInCategory.OST_EscalatorTags,
            DB.BuiltInCategory.OST_MovingWalkwayTags,
            DB.BuiltInCategory.OST_EntourageTags,
            DB.BuiltInCategory.OST_ModelTextTags,
            DB.BuiltInCategory.OST_GenericModelTags
        ]
        
        # Enable each annotation category
        for category in annotation_categories:
            try:
                # Get the category object
                cat = DB.Category.GetCategory(doc, category)
                if cat:
                    # Make sure the category is visible in the view
                    if view.GetCategoryHidden(cat.Id):
                        view.SetCategoryHidden(cat.Id, False)
            except Exception as e:
                # Some categories might not exist in all projects, skip them
                continue
        
        print("Annotation categories enabled for displacement")
        
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


def get_all_elements_on_level(doc, level):
    """Get ALL elements on a specific level using FilteredElementCollector with level filter."""
    try:
        # Create a level filter
        level_filter = DB.ElementLevelFilter(level.Id)
        
        # Get all elements that can be displaced (exclude system families, views, etc.)
        collector = DB.FilteredElementCollector(doc)
        
        # Apply level filter and get all elements
        elements = collector.WherePasses(level_filter).WhereElementIsNotElementType()
        
        # Filter out elements that shouldn't be displaced
        displaceable_elements = []
        for element in elements:
            # Skip certain element types that shouldn't be displaced
            if should_skip_element_for_displacement(element):
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


################## main code below #####################
if __name__ == "__main__":
    explode_axon(DOC)







