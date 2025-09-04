#!/usr/bin/python
# -*- coding: utf-8 -*-

__doc__ = "3D View Manager for Area2Mass Tool - Creates and manages dedicated 3D views for mass visualization"
__title__ = "Area2Mass View Manager"

import clr
clr.AddReference('RevitAPI')
clr.AddReference('RevitServices')

from Autodesk.Revit import DB
from EnneadTab import ERROR_HANDLE, ENVIRONMENT
from EnneadTab.REVIT import REVIT_VIEW


class Area2MassViewManager:
    """Manages 3D views for Area2Mass tool."""
    
    def __init__(self, project_doc):
        self.project_doc = project_doc
        self.view_name = "AREA2MASS - 3D VIEW"
        self.view = None
    
    def get_or_create_3d_view(self):
        """Get existing 3D view or create a new one."""
        try:
            # Try to find existing view first
            self.view = self._find_existing_view()
            if self.view:
                return self.view
            
            # Create new 3D view if not found
            self.view = self._create_new_3d_view()
            
            if self.view:
                return self.view
            else:
                return None
                
        except Exception as e:
            ERROR_HANDLE.print_note("DEBUG: {}".format(e))
            return None
    
    def _find_existing_view(self):
        """Find existing 3D view with the specified name."""
        try:
            collector = DB.FilteredElementCollector(self.project_doc)
            views = collector.OfClass(DB.View3D).WhereElementIsNotElementType()
            
            for view in views:
                if view.Name == self.view_name:
                    return view
            
            return None
            
        except Exception as e:
            return None
    
    def _create_new_3d_view(self):
        """Create a new 3D view for mass visualization."""
        try:
            # Start transaction for view creation
            t = DB.Transaction(self.project_doc, "Create Area2Mass 3D View")
            t.Start()
            
            try:
                # Get default 3D view type
                view_family_type = self._get_default_3d_view_type()
                
                if view_family_type:
                    # Create isometric view with proper view type
                    view = DB.View3D.CreateIsometric(self.project_doc, view_family_type.Id)
                else:
                    # Fallback: create isometric view without specific type
                    view = DB.View3D.CreateIsometric(self.project_doc, DB.ElementId.InvalidElementId)
                
                # Set view properties
                view.Name = self.view_name
                
                # Configure view for mass visualization
                self._configure_view_for_mass(view)
                
                t.Commit()
                return view
                
            except Exception as e:
                t.RollBack()
                ERROR_HANDLE.print_note("DEBUG: {}".format(e))
                return None
                
        except Exception as e:
            ERROR_HANDLE.print_note("DEBUG: {}".format(e))
            return None
    
    def _get_default_3d_view_type(self):
        """Get the default 3D view family type."""
        try:
            view_family_types = DB.FilteredElementCollector(self.project_doc).OfClass(DB.ViewFamilyType)
            
            for vft in view_family_types:
                if vft.ViewFamily == DB.ViewFamily.ThreeDimensional:
                    return vft
            
            return None
            
        except Exception as e:
            ERROR_HANDLE.print_note("DEBUG: {}".format(e))
            return None
    
    def _configure_view_for_mass(self, view):
        """Configure the view specifically for mass visualization."""
        try:
            # Set view scale for better visualization
            try:
                view.Scale = 100  # 1:100 scale
            except:
                pass
            
            # Ensure mass category is visible
            self._ensure_mass_category_visible(view)
            
            # Set view orientation for better mass visualization
            self._set_view_orientation(view)
            
            # Configure other view properties
            self._set_view_properties(view)
            
            # Set EnneadTab view grouping and series (like explode_axon tool)
            self._set_enneadtab_view_properties(view)
            
        except Exception as e:
            ERROR_HANDLE.print_note("DEBUG: {}".format(e))
            pass
    
    def _ensure_mass_category_visible(self, view):
        """Ensure mass category is visible in the view."""
        try:
            # Get mass category
            mass_category = self.project_doc.Settings.Categories.get_Item(DB.BuiltInCategory.OST_Mass)
            if mass_category:
                # Set category visibility
                view.SetCategoryHidden(mass_category.Id, False)
            else:
                ERROR_HANDLE.print_note("DEBUG: Mass category not found")
                pass
                
        except Exception as e:
            ERROR_HANDLE.print_note("DEBUG: {}".format(e))
            pass
    
    def _set_view_orientation(self, view):
        """Set optimal view orientation for mass visualization."""
        try:
            # Set to isometric view for better mass understanding
            # The view is already created as isometric, but we can adjust if needed
            
            # Get the view's eye position and up direction
            eye_position = view.GetOrientation().EyePosition
            up_direction = view.GetOrientation().UpDirection
            
        except Exception as e:
            ERROR_HANDLE.print_note("DEBUG: {}".format(e))
            pass
    
    def _set_view_properties(self, view):
        """Set additional view properties for better mass visualization."""
        try:
            # Set view detail level to medium for good performance and visibility
            try:
                view.DetailLevel = DB.ViewDetailLevel.Medium
            except:
                pass
            
            # Set view discipline to architectural for mass visualization
            try:
                view.get_Parameter(DB.BuiltInParameter.VIEWER_BOUND_OFFSET_FAR).Set(1000)  # Far clip offset
            except:
                pass
                
        except Exception as e:
            ERROR_HANDLE.print_note("DEBUG: {}".format(e))
            pass
    
    def _set_enneadtab_view_properties(self, view):
        """Set EnneadTab view grouping and series properties (like explode_axon tool)."""
        try:
            # Start transaction for setting view properties
            t = DB.Transaction(self.project_doc, "Set EnneadTab View Properties")
            t.Start()
            
            try:
                # Set view group to "EnneadTab" (like other EnneadTab tools)
                view.LookupParameter("Views_$Group").Set(ENVIRONMENT.PLUGIN_NAME)
                pass
                
                # Set view series to "Area2Mass" for easy identification
                view.LookupParameter("Views_$Series").Set("(●´∞`●) Area2Mass")
                pass
                
                t.Commit()
                pass
                
            except Exception as e:
                t.RollBack()
              
                ERROR_HANDLE.print_note("DEBUG: {}".format(e))
                pass
                
        except Exception as e:
            ERROR_HANDLE.print_note("DEBUG: {}".format(e))
            pass
    
    def switch_to_view(self):
        """Switch the active view to the Area2Mass 3D view."""
        try:
            if self.view:
                # Use REVIT_VIEW module to switch to the view
                REVIT_VIEW.set_active_view_by_name(self.view_name, self.project_doc)
                return True
            else:
                return False
                
        except Exception as e:
            return False
    
    def get_view_info(self):
        """Get information about the current view."""
        if not self.view:
            return "No view available"
        
        try:
            info = []
            info.append("View Name: {}".format(self.view.Name))
            info.append("View ID: {}".format(self.view.Id))
            info.append("View Type: {}".format(self.view.ViewType))
            info.append("Scale: {}".format(self.view.Scale))
            info.append("Detail Level: {}".format(self.view.DetailLevel))
            
            return "\n".join(info)
            
        except Exception as e:
            return "Error getting view info: {}".format(str(e))
    
    def cleanup_view(self):
        """Clean up the view if needed (optional cleanup operations)."""
        try:
            if self.view:
                print("View cleanup completed for: {}".format(self.view_name))
            return True
            
        except Exception as e:
            print("Error during view cleanup: {}".format(str(e)))
            return False


if __name__ == "__main__":
    """Test the Area2MassViewManager class when run as main module."""
    print("Area2MassViewManager module - This module provides 3D view management functionality.")
    print("To test this module, run it within a Revit environment with proper document context.")