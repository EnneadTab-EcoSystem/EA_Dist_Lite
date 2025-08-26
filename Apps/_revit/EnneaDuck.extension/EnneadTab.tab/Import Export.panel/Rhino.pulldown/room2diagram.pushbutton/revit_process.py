#!/usr/bin/python
# -*- coding: utf-8 -*-

"""
RevitProcess module for handling Revit-specific processing in room2diagram export.
"""

# ============================================================================
# RHINOINSIDE IMPORT CHECK - MUST BE FIRST
# ============================================================================
try:
    import clr  # pyright: ignore
    clr.AddReference('RhinoCommon')
    import Rhino  # pyright: ignore
    clr.AddReference('RhinoInside.Revit')
    from RhinoInside.Revit.Convert.Geometry import GeometryEncoder as RIR_ENCODER  # pyright: ignore
    RHINO_IMPORT_OK = True
except:
    RHINO_IMPORT_OK = False

# ============================================================================
# STANDARD IMPORTS
# ============================================================================
import System  # pyright: ignore
import os
from EnneadTab import ENVIRONMENT, ERROR_HANDLE, TIME, SAMPLE_FILE
from EnneadTab.REVIT import REVIT_VIEW, REVIT_SELECTION, REVIT_UNIT, REVIT_FAMILY, REVIT_TAG
from Autodesk.Revit import DB # pyright: ignore
from base_processor import BaseProcessor
import traceback


class RevitProcess(BaseProcessor):
    """Handles Revit-specific processing for drafting view export."""
    
    def __init__(self, revit_doc, fillet_radius, offset_distance):
        """Initialize Revit processor.
        
        Args:
            revit_doc: Active Revit document
            fillet_radius: Corner fillet radius in feet
            offset_distance: Inner offset distance in feet
        """
        BaseProcessor.__init__(self, revit_doc, fillet_radius, offset_distance)
        print("RevitProcess initialized with fillet_radius={}, offset_distance={}".format(fillet_radius, offset_distance))
    
    def _has_curves(self, curve_loop):
        """Check if a CurveLoop has any curves using iterator approach."""
        if not curve_loop:
            return False
        
        try:
            curve_iterator = curve_loop.GetCurveLoopIterator()
            return curve_iterator.MoveNext()
        except Exception as e:
            print("Error checking curve loop: {}".format(str(e)))
            return False
    
    def _process_curves_for_drafting(self, curve_loop):
        """Process curves for drafting view with fillet and offset operations."""
        if not curve_loop:
            return None
        
        # Convert curve loop to list of curves
        curves = []
        curve_iterator = curve_loop.GetCurveLoopIterator()
        while curve_iterator.MoveNext():
            curves.append(curve_iterator.Current)
        
        print("Processing {} curves with fillet_radius={}, offset_distance={}".format(len(curves), self.fillet_radius, self.offset_distance))
        
        # Use base class curve processing (returns processed Rhino curves)
        processed_rhino_curves = self.process_curves(curves, "revit")
        
        if not processed_rhino_curves:
            return curve_loop  # Return original if processing fails
        
        # Convert processed Rhino curves back to Revit CurveLoop
        return self._convert_rhino_curves_to_curve_loop(processed_rhino_curves)
    
    def _convert_rhino_curves_to_curve_loop(self, rhino_curves):
        """Convert processed Rhino curves to Revit CurveLoop using ToCurveLoop."""
        if not rhino_curves or len(rhino_curves) == 0:
            return None
        
        try:
            # BaseProcessor typically returns a single joined polycurve with fillet and offset applied
            # RIR_ENCODER.ToCurveLoop() can convert this directly to a Revit CurveLoop
            if len(rhino_curves) > 0:
                rhino_curve = rhino_curves[0]  # Get the first (and typically only) curve
                
                if not rhino_curve:
                    return None
                
                if not hasattr(rhino_curve, 'IsValid') or not rhino_curve.IsValid:
                    return None
                
                # Use RIR_ENCODER.ToCurveLoop() to convert the joined polycurve directly to Revit CurveLoop
                try:
                    curve_loop = RIR_ENCODER.ToCurveLoop(rhino_curve)
                    if curve_loop and self._has_curves(curve_loop):
                        return curve_loop
                    else:
                        return None
                except Exception as e:
                    print("Error converting joined polycurve to CurveLoop: {}".format(str(e)))
                    return None
            else:
                return None
            
        except Exception as e:
            print("Error in _convert_rhino_curves_to_curve_loop: {}".format(str(e)))
            return None

    def _create_filled_region_from_curves(self, curve_loop, filled_region_type, floor_plan_view):
        """Create filled region from curve loop."""
        try:
            if not curve_loop or not filled_region_type or not floor_plan_view:
                return False, None
            
            # Create filled region within transaction
            with DB.Transaction(self.revit_doc, "Create Bubble Diagram Filled Region") as t:
                t.Start()
                try:
                    # Create a list of curve loops - DB.FilledRegion.Create expects a collection
                    curve_loops = System.Collections.Generic.List[DB.CurveLoop]()
                    curve_loops.Add(curve_loop)
                    
                    # Create filled region
                    filled_region = DB.FilledRegion.Create(
                        self.revit_doc,
                        filled_region_type.Id,
                        floor_plan_view.Id,
                        curve_loops
                    )
                    
                    if filled_region:
                        print("Created filled region successfully")
                        t.Commit()
                        return True, filled_region
                    else:
                        print("Failed to create filled region")
                        t.RollBack()
                        return False, None
                        
                except Exception as e:
                    print("Error in transaction creating filled region: {}".format(str(e)))
                    t.RollBack()
                    return False, None
                
        except Exception as e:
            print("Error creating filled region: {}".format(str(e)))
            return False, None
    
    def _add_comment_to_filled_region(self, filled_region, space_identifier, space_area, space_object):
        """Add comment to filled region with space information including original area and department.
        
        Args:
            filled_region: Revit filled region object
            space_identifier: Space identifier string
            space_area: Area value in square feet
            space_object: Original Revit space object to get parameters from
        """
        try:
            if not filled_region or not space_object:
                return False
            
            # Get original area from space object
            original_area = 0
            try:
                area_param = space_object.LookupParameter("Area")
                if area_param:
                    original_area = area_param.AsDouble()
                    # Convert to square feet if needed
                    original_area_sf = DB.UnitUtils.ConvertFromInternalUnits(original_area, REVIT_UNIT.lookup_unit_id("squareFeet"))
                    original_area_rounded = int(round(original_area_sf)) if original_area_sf > 0 else 0
                else:
                    original_area_rounded = 0
            except Exception as e:
                print("Warning: Could not get original area from space: {}".format(str(e)))
                original_area_rounded = 0
            
            # Get department from space object
            department = "N/A"
            try:
                dept_param = space_object.LookupParameter("Department")
                if dept_param:
                    dept_value = dept_param.AsString()
                    if dept_value:
                        department = dept_value
            except Exception as e:
                print("Warning: Could not get department from space: {}".format(str(e)))
            
            # Create comment content with original area and department
            comment_content = "{} - {} SF - Dept: {}".format(space_identifier, original_area_rounded, department)
            
            # Add comment to filled region within transaction
            with DB.Transaction(self.revit_doc, "Add Comment to Filled Region") as t:
                t.Start()
                try:
                    # Try multiple possible parameter names for comments
                    comment_param = None
                    param_names_to_try = ["Comments", "Comment", "Description", "Mark", "Type Comments"]
                    
                    for param_name in param_names_to_try:
                        try:
                            param = filled_region.LookupParameter(param_name)
                            if param and not param.IsReadOnly:
                                comment_param = param
                                print("Found comment parameter: '{}'".format(param_name))
                                break
                        except Exception as e:
                            print("Warning: Could not access parameter '{}': {}".format(param_name, str(e)))
                            continue
                    
                    if comment_param:
                        comment_param.Set(comment_content)
                        print("Added comment to filled region: {}".format(comment_content))
                        t.Commit()
                        return True
                    else:
                        # If no comment parameter found, try to add a custom parameter or use a different approach
                        print("Warning: No suitable comment parameter found on filled region")
                        print("Available parameters on filled region:")
                        try:
                            for param in filled_region.Parameters:
                                if param and param.Definition:
                                    print("  - {} (ReadOnly: {})".format(param.Definition.Name, param.IsReadOnly))
                        except Exception as e:
                            print("  Could not list parameters: {}".format(str(e)))
                        
                        # Try to use the "Mark" parameter as fallback
                        try:
                            mark_param = filled_region.LookupParameter("Mark")
                            if mark_param and not mark_param.IsReadOnly:
                                mark_param.Set(comment_content)
                                print("Added comment to filled region using Mark parameter: {}".format(comment_content))
                                t.Commit()
                                return True
                        except Exception as e:
                            print("Warning: Could not use Mark parameter: {}".format(str(e)))
                        
                        t.RollBack()
                        return False
                except Exception as e:
                    print("Error in transaction adding comment: {}".format(str(e)))
                    t.RollBack()
                    return False
                
        except Exception as e:
            print("Error adding comment to filled region: {}".format(str(e)))
            return False
    
    def _get_or_create_bubble_diagram_tag_family(self):
        """Get or create bubble diagram tag family for filled regions."""
        try:
            # Try to get existing tag family or load from file if not found
            tag_family_name = "BubbleDiagram Tag"
            
            # Use SAMPLE_FILE.get_file to get the family file path
            family_file_path = SAMPLE_FILE.get_file("BubbleDiagram Tag.rfa")
            
            if family_file_path:
                print("Found BubbleDiagram Tag.rfa at: {}".format(family_file_path))
                # Use get_family_by_name with load_path_if_not_exist parameter
                tag_family = REVIT_FAMILY.get_family_by_name(
                    tag_family_name, 
                    doc=self.revit_doc,
                    load_path_if_not_exist=family_file_path
                )
                
                if tag_family:
                    print("Successfully loaded BubbleDiagram Tag family")
                    return tag_family
                else:
                    print("Failed to load BubbleDiagram Tag family from file")
                    return None
            else:
                print("BubbleDiagram Tag.rfa not found using SAMPLE_FILE.get_file")
                print("Please ensure the family file is available in the EnneadTab sample files folder")
                return None
                
        except Exception as e:
            print("Error getting or creating tag family: {}".format(str(e)))
            return None
    
    def _create_tag_for_filled_region(self, filled_region, space_identifier, floor_plan_view):
        """Create tag for filled region using tag family and type.
        
        Args:
            filled_region: Revit filled region object
            space_identifier: Space identifier string
            floor_plan_view: Revit floor plan view to create tag in
        """
        try:
            if not filled_region or not floor_plan_view:
                return False
            
            # Get or create tag family
            tag_family = self._get_or_create_bubble_diagram_tag_family()
            if not tag_family:
                print("Warning: Could not create or find tag family. Tags will be skipped.")
                return False
            
            # Get tag symbol (type) - properly handle HashSet
            tag_symbol_ids = tag_family.GetFamilySymbolIds()
            if not tag_symbol_ids or tag_symbol_ids.Count == 0:
                print("Warning: No tag symbols found in tag family")
                return False
            
            # Convert HashSet to list and get first element
            tag_symbol_id_list = list(tag_symbol_ids)
            if not tag_symbol_id_list:
                print("Warning: Could not convert tag symbol IDs to list")
                return False
            
            tag_symbol = self.revit_doc.GetElement(tag_symbol_id_list[0])
            if not tag_symbol.IsActive:
                with DB.Transaction(self.revit_doc, "Activate Tag Symbol") as t:
                    t.Start()
                    tag_symbol.Activate()
                    t.Commit()
            
            # Create tag within transaction
            with DB.Transaction(self.revit_doc, "Create Bubble Diagram Tag") as t:
                t.Start()
                try:
                    # Create tag for the filled region using the tag type
                    tag = DB.IndependentTag.Create(
                        self.revit_doc,
                        tag_symbol.Id,  # Tag type ID
                        floor_plan_view.Id,
                        DB.Reference(filled_region),
                        True,  # HasLeader
                        DB.TagOrientation.Horizontal,
                        filled_region.Location.Point
                    )
                    
                    if tag:
                        print("Created tag for filled region: {} using tag type: {}".format(
                            space_identifier, tag_symbol.Name))
                        t.Commit()
                        return True
                    else:
                        print("Failed to create tag for filled region: {}".format(space_identifier))
                        t.RollBack()
                        return False
                        
                except Exception as e:
                    print("Error in transaction creating tag: {}".format(str(e)))
                    t.RollBack()
                    return False
                
        except Exception as e:
            print("Error creating tag for filled region {}: {}".format(space_identifier, str(e)))
            return False
    
    def _create_floor_plan_view(self, level_name):
        """Create floor plan view for Revit export and hide all model categories except detail items."""
        try:
            # Create floor plan view name
            view_name = "BubbleDiagram_{}".format(level_name)
            
            # Check if view already exists and rename it
            existing_view = REVIT_VIEW.get_view_by_name(view_name, self.revit_doc)
            if existing_view:
                try:
                    existing_view.Name = existing_view.Name + "_Old({})".format(TIME.get_YYYY_MM_DD())
                except Exception as e:
                    print("Could not rename existing view, creating new one with timestamp")
                    import time
                    view_name = "{}_{}".format(view_name, int(time.time()))
            
            # Find the level by name
            level = None
            levels = DB.FilteredElementCollector(self.revit_doc).OfClass(DB.Level).ToElements()
            for lvl in levels:
                if lvl.Name == level_name:
                    level = lvl
                    break
            
            if not level:
                print("Warning: Could not find level '{}', using first available level".format(level_name))
                if levels:
                    level = levels[0]
                else:
                    print("Error: No levels found in document")
                    return None
            
            # Create new floor plan view within transaction
            floor_plan_view = None
            with DB.Transaction(self.revit_doc, "Create Bubble Diagram Floor Plan View") as t:
                t.Start()
                try:
                    # Get the floor plan view type
                    view_types = DB.FilteredElementCollector(self.revit_doc).OfClass(DB.ViewFamilyType).ToElements()
                    floor_plan_type = None
                    for view_type in view_types:
                        if view_type.FamilyName == "Floor Plan":
                            floor_plan_type = view_type
                            break
                    
                    if not floor_plan_type:
                        print("Warning: Could not find Floor Plan view type, using first available")
                        if view_types:
                            floor_plan_type = view_types[0]
                        else:
                            print("Error: No view plan types found in document")
                            t.RollBack()
                            return None
                    
                    # Create floor plan view
                    floor_plan_view = DB.ViewPlan.Create(self.revit_doc, 
                                                        floor_plan_type.Id, 
                                                        level.Id)
                    
                    if floor_plan_view:
                        # Set view name
                        floor_plan_view.Name = view_name
                        
                        # Set ViewGroup and ViewSeries properties
                        view_group_param = floor_plan_view.LookupParameter("Views_$Group")
                        if view_group_param and not view_group_param.IsReadOnly:
                            view_group_param.Set("EnneadTab")
                        
                        view_series_param = floor_plan_view.LookupParameter("Views_$Series")
                        if view_series_param and not view_series_param.IsReadOnly:
                            view_series_param.Set("BubbleDiagram")
                        
                        print("Set Views_$Group to 'EnneadTab' and Views_$Series to 'BubbleDiagram'")
                        
                        # Set view scale to match the original source view
                        try:
                            scale_param = floor_plan_view.LookupParameter("View Scale")
                            if scale_param and not scale_param.IsReadOnly:
                                # Get scale from source view if available
                                if hasattr(self, 'source_view') and self.source_view:
                                    try:
                                        source_scale_param = self.source_view.LookupParameter("View Scale")
                                        if source_scale_param:
                                            source_scale = source_scale_param.AsInteger()
                                            scale_param.Set(source_scale)
                                            print("Set view scale to match source view: 1:{}".format(source_scale))
                                        else:
                                            # Fallback to 1/8" = 1'-0" scale (1:96)
                                            scale_param.Set(96)
                                            print("Set view scale to default 1/8\" = 1'-0\" (source view scale not available)")
                                    except Exception as e:
                                        print("Warning: Could not get scale from source view: {}. Using default scale.".format(str(e)))
                                        scale_param.Set(96)
                                        print("Set view scale to default 1/8\" = 1'-0\"")
                                else:
                                    # No source view available, use default scale
                                    scale_param.Set(96)
                                    print("Set view scale to default 1/8\" = 1'-0\" (no source view)")
                        except Exception as e:
                            print("Warning: Could not set view scale: {}".format(str(e)))
                        
                        # Set view discipline to Coordination for better category control
                        try:
                            discipline_param = floor_plan_view.LookupParameter("Discipline")
                            if discipline_param and not discipline_param.IsReadOnly:
                                discipline_param.Set(1)  # 1 = Coordination
                                print("Set view discipline to Coordination")
                        except Exception as e:
                            print("Warning: Could not set view discipline: {}".format(str(e)))
                        
                        # Configure view categories for bubble diagram
                        self._configure_bubble_diagram_view_categories(floor_plan_view)
                    
                    t.Commit()
                    
                except Exception as e:
                    print("Error in transaction creating floor plan view: {}".format(str(e)))
                    t.RollBack()
                    return None
            
            return floor_plan_view
            
        except Exception as e:
            print("Error creating floor plan view: {}".format(str(e)))
            return None
    
    def _configure_bubble_diagram_view_categories(self, view):
        """Configure view categories for bubble diagram - hide all except detail items, tags, grids, and dimensions."""
        try:
            # Define categories to keep visible
            visible_categories = [
                DB.BuiltInCategory.OST_DetailComponents,  # Detail items
                DB.BuiltInCategory.OST_DetailTags,        # Detail tags
                DB.BuiltInCategory.OST_Grids,             # Grids
                DB.BuiltInCategory.OST_Dimensions         # Dimensions
            ]
            
            print("Starting category configuration for bubble diagram view...")
            
            # Method 1: Use document settings categories (more reliable approach)
            for category in self.revit_doc.Settings.Categories:
                try:
                    # Skip categories that can't be hidden
                    if not view.CanCategoryBeHidden(category.Id):
                        continue
                    
                    # Check if this category should be visible
                    should_be_visible = category.Id.IntegerValue in [int(cat) for cat in visible_categories]
                    
                    # Set category visibility using the standard pattern from codebase
                    view.SetCategoryHidden(category.Id, not should_be_visible)
                    
                    if should_be_visible:
                        print("Showing category: {} ({})".format(category.Name, category.Id))
                    else:
                        print("Hiding category: {} ({})".format(category.Name, category.Id))
                        
                except Exception as e:
                    # Some categories might not be controllable, skip them
                    print("Warning: Could not control category {}: {}".format(category.Name, str(e)))
                    continue
            
            # Method 2: Also explicitly hide specific model categories (backup approach)
            try:
                # Hide walls, doors, windows, and other model elements
                model_categories_to_hide = [
                    DB.BuiltInCategory.OST_Walls,
                    DB.BuiltInCategory.OST_Doors,
                    DB.BuiltInCategory.OST_Windows,
                    DB.BuiltInCategory.OST_Rooms,
                    DB.BuiltInCategory.OST_Areas,
                    DB.BuiltInCategory.OST_Spaces,
                    DB.BuiltInCategory.OST_Ceilings,
                    DB.BuiltInCategory.OST_Floors,
                    DB.BuiltInCategory.OST_Columns,
                    DB.BuiltInCategory.OST_StructuralFraming,
                    DB.BuiltInCategory.OST_Furniture,
                    DB.BuiltInCategory.OST_PlumbingFixtures,
                    DB.BuiltInCategory.OST_ElectricalFixtures,
                    DB.BuiltInCategory.OST_MechanicalEquipment,
                    DB.BuiltInCategory.OST_DuctCurves,
                    DB.BuiltInCategory.OST_PipeCurves,
                    DB.BuiltInCategory.OST_CableTray,
                    DB.BuiltInCategory.OST_Conduit,
                    DB.BuiltInCategory.OST_ElectricalEquipment,
                    DB.BuiltInCategory.OST_LightingFixtures,
                    DB.BuiltInCategory.OST_GenericModel,
                    DB.BuiltInCategory.OST_ModelText,
                    DB.BuiltInCategory.OST_ModelLines,
                    DB.BuiltInCategory.OST_ModelGroups
                ]
                
                for built_in_cat in model_categories_to_hide:
                    try:
                        category = DB.Category.GetCategory(self.revit_doc, built_in_cat)
                        if category and view.CanCategoryBeHidden(category.Id):
                            view.SetCategoryHidden(category.Id, True)
                            print("Explicitly hiding model category: {}".format(category.Name))
                    except Exception as e:
                        print("Warning: Could not hide category {}: {}".format(built_in_cat, str(e)))
                        continue
                        
            except Exception as e:
                print("Warning: Error in Method 2 category hiding: {}".format(str(e)))
            
            # Refresh the view to ensure changes take effect
            try:
                view.RefreshActiveView()
                print("Refreshed view to apply category changes")
            except Exception as e:
                print("Warning: Could not refresh view: {}".format(str(e)))
            
            print("Configured view categories for bubble diagram - hidden all except detail items, tags, grids, and dimensions")
            
        except Exception as e:
            print("Error hiding categories: {}".format(str(e)))
            import traceback
            print("Full traceback: {}".format(traceback.format_exc()))
    
    def _process_space_for_revit(self, space_data, floor_plan_view):
        """Process a single space for Revit export."""
        try:
            # Handle both space_data dictionary and direct space object
            if isinstance(space_data, dict):
                # Input is a processed space_data dictionary
                space = space_data['space']
                space_identifier = space_data['identifier']
                space_area = space_data['area']
                boundary_curves = space_data['curves']
                revit_color = space_data['color']
                
            else:
                # Input is a direct space object (legacy support)
                space = space_data
                space_identifier = space.LookupParameter(self.para_name).AsString()
                if not space_identifier:
                    return False
                
                # Get area from space object
                try:
                    space_area = int(round(space.Area)) if space.Area > 0 else 0
                except:
                    space_area = 0
                
                # Get color from color dictionary
                revit_color = self.color_dict.get(space_identifier)
                
                # Use boundary curves from space_data (already extracted by BaseProcessor)
                boundary_curves = space_data.get('curves', [])
            
            # Validate color
            if not revit_color:
                print("No color found, skipping space")
                return False
            
            # Get or create filled region type
            region_type_name = "_ColorScheme_{}".format(space_identifier)
            filled_region_type = REVIT_SELECTION.get_filledregion_type(
                self.revit_doc,
                region_type_name,
                color_if_not_exist=(revit_color.Red, revit_color.Green, revit_color.Blue)
            )
            
            if not filled_region_type:
                print("Could not get or create filled region type")
                return False
            
            # Create filled region and add comment/tag
            filled_region_success = False
            comment_success = False
            tag_success = False
            
            # Process boundary curves and create filled region
            filled_region_success = False
            created_filled_region = None
            print("DEBUG: Processing {} boundary curves for space {}".format(len(boundary_curves) if boundary_curves else 0, space_identifier))
            if boundary_curves:
                try:
                    # First, process the curves through BaseProcessor to apply fillet and offset
                    print("DEBUG: Processing curves through BaseProcessor to apply fillet and offset")
                    processed_curves = self.process_curves(boundary_curves, "revit")
                    
                    if processed_curves and len(processed_curves) > 0:
                        print("DEBUG: BaseProcessor returned {} processed curves".format(len(processed_curves)))
                        
                        # Get the first (and typically only) processed curve from BaseProcessor
                        processed_curve = processed_curves[0]
                        if processed_curve and hasattr(processed_curve, 'IsValid') and processed_curve.IsValid:
                            print("DEBUG: Converting processed curve (with fillet/offset) to Revit CurveLoop")
                            try:
                                # Use RIR_ENCODER.ToCurveLoop() to convert the processed curve directly to Revit CurveLoop
                                curve_loop = RIR_ENCODER.ToCurveLoop(processed_curve)
                                if curve_loop and self._has_curves(curve_loop):
                                    print("DEBUG: Successfully converted processed curve to Revit CurveLoop")
                                    
                                    # Create filled region with the CurveLoop
                                    try:
                                        filled_region_success, created_filled_region = self._create_filled_region_from_curves(curve_loop, filled_region_type, floor_plan_view)
                                        if filled_region_success:
                                            print("Created filled region with processed curves (fillet and offset applied)")
                                    except Exception as e:
                                        print("Failed to create filled region with processed curves for space {}: {}".format(space_identifier, str(e)))
                                else:
                                    print("DEBUG: Failed to convert processed curve to valid Revit CurveLoop")
                                    curve_loop = None
                            except Exception as e:
                                print("DEBUG: Error converting processed curve to Revit CurveLoop: {}".format(str(e)))
                                curve_loop = None
                        else:
                            print("DEBUG: Processed curve is invalid")
                            curve_loop = None
                    else:
                        print("DEBUG: BaseProcessor failed to process curves - NO FALLBACK")
                        curve_loop = None
                    
                    if not curve_loop:
                        print("No valid curve loop created for space: {}".format(space_identifier))
                except Exception as e:
                    print("Error processing boundary curves for space {}: {}".format(space_identifier, str(e)))
            
            # Add comment and tag to the filled region if it was created successfully
            if filled_region_success and created_filled_region:
                try:
                    # Verify filled region creation and list available parameters
                    print("Verifying filled region creation for space: {}".format(space_identifier))
                    self._verify_filled_region_creation(created_filled_region, space_identifier)
                    
                    # Add comment to filled region
                    print("Adding comment to filled region for space: {}".format(space_identifier))
                    comment_success = self._add_comment_to_filled_region(created_filled_region, space_identifier, space_area, space)
                    
                    # Create tag for filled region
                    print("Creating tag for filled region for space: {}".format(space_identifier))
                    tag_success = self._create_tag_for_filled_region(created_filled_region, space_identifier, floor_plan_view)
                except Exception as e:
                    print("Failed to add comment/tag for space {}: {}".format(space_identifier, str(e)))
                    import traceback
                    print("Full traceback: {}".format(traceback.format_exc()))
            
            # Return success if filled region was created successfully
            success = filled_region_success
            if success:
                print("Successfully processed space: {} (region: {}, comment: {}, tag: {})".format(
                    space_identifier, filled_region_success, comment_success, tag_success))
            else:
                print("Failed to process space: {} (region: {}, comment: {}, tag: {})".format(
                    space_identifier, filled_region_success, comment_success, tag_success))
            
            return success
            
        except Exception as e:
            print("Error processing space for Revit: {}".format(str(e)))
            return False
    
    def _process_spaces_for_revit(self, results, source_view=None):
        """Process spaces for Revit export."""
        try:
            # Store source view for use in floor plan creation
            if source_view:
                self.source_view = source_view
            
            # Get level name and processed spaces
            level_name = results.get('level_name', 'Unknown_Level')
            processed_spaces = results.get('processed_spaces', [])
            
            print("Processing {} spaces for Revit export (Level: {})".format(len(processed_spaces), level_name))
            
            # Create floor plan view
            floor_plan_view = self._create_floor_plan_view(level_name)
            if not floor_plan_view:
                return False
            
            # Process each space
            processed_count = 0
            for space_data in processed_spaces:
                if self._process_space_for_revit(space_data, floor_plan_view):
                    processed_count += 1
            
            print("Successfully processed {}/{} spaces for Revit".format(processed_count, len(processed_spaces)))
            return True
            
        except Exception as e:
            print("Error in Revit processing: {}".format(str(e)))
            return False
    
    def process_spaces_from_results(self, results, source_view=None):
        """Process spaces from results for Revit export.
        
        Args:
            results: Dictionary containing processed space data
            source_view: Original source view (for getting scale and other properties)
        """
        try:
            # Store source view for use in floor plan creation
            self.source_view = source_view
            
            # Delegate to Revit-specific processing
            return self._process_spaces_for_revit(results, source_view)
            
        except Exception as e:
            print("Error in Revit processing: {}".format(str(e)))
            return False
    
    def _verify_filled_region_creation(self, filled_region, space_identifier):
        """Verify that filled region was created successfully and has necessary parameters.
        
        Args:
            filled_region: The created filled region object
            space_identifier: Space identifier for debugging
            
        Returns:
            bool: True if filled region is valid and has parameters, False otherwise
        """
        try:
            if not filled_region:
                print("ERROR: Filled region is None for space: {}".format(space_identifier))
                return False
            
            if not filled_region.IsValidObject:
                print("ERROR: Filled region is not valid for space: {}".format(space_identifier))
                return False
            
            # Check if filled region has parameters
            if not filled_region.Parameters:
                print("WARNING: Filled region has no parameters for space: {}".format(space_identifier))
                return False
            
            # List available parameters for debugging
            print("Available parameters on filled region for space '{}':".format(space_identifier))
            try:
                for param in filled_region.Parameters:
                    if param and param.Definition:
                        print("  - {} (ReadOnly: {}, StorageType: {})".format(
                            param.Definition.Name, 
                            param.IsReadOnly,
                            param.StorageType
                        ))
            except Exception as e:
                print("  Could not list parameters: {}".format(str(e)))
            
            return True
            
        except Exception as e:
            print("Error verifying filled region: {}".format(str(e)))
            return False


