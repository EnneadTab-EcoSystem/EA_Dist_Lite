# -*- coding: utf-8 -*-
__title__ = "QuickMassing"
__doc__ = """Create parametric massing models with advanced level editor interface.

Features:
- Interactive level editor table with reorder, add, remove functionality
- Dedicated surface picker with surface filter
- Real-time elevation calculations
- Persistent settings storage
- Visual level management interface

Usage:
1. Left-click to activate the QuickMassing tool
2. Use the level editor to configure building levels
3. Pick surfaces for massing creation
4. Generate massing model based on your specifications

Note: All settings are saved between sessions for convenience."""
__is_popular__ = True

import os
import rhinoscriptsyntax as rs
import scriptcontext as sc
import Eto.Forms as Forms # pyright: ignore
import Eto.Drawing as Drawing # pyright: ignore
import Rhino # pyright: ignore
from EnneadTab import DATA_FILE, NOTIFICATION, ERROR_HANDLE
from EnneadTab.RHINO import RHINO_UI
import traceback

FORM_KEY = 'quick_massing_modeless_form'

class LevelEditorTable(Forms.GridView):
    """Custom GridView for managing building levels with elevation calculations."""
    
    def __init__(self):
        self.levels = []
        self.refresh_callback = None  # Will be set to a callable function
        self.load_default_levels()
        
        # Configure grid
        self.AllowColumnReordering = False
        self.AllowMultipleSelection = False
        self.GridLines = Forms.GridLines.Horizontal
        self.ShowHeader = True
        self.AllowEditing = True
        
        # Disable cell editing to prevent crashes - we'll use buttons instead
        self.AllowEditing = False
        
        # Preview control flag
        self.preview_enabled = True
        
        # Create columns
        self.create_columns()
        
        # Load data
        self.load_data()
        
    def create_columns(self):
        """Create and configure grid columns."""
        # Level Name column
        level_col = Forms.GridColumn()
        level_col.HeaderText = "Level"
        level_col.DataCell = Forms.TextBoxCell(0)  # Index 0 for level name
        # Remove fixed width to allow auto-sizing
        level_col.Editable = False  # Disable editing to prevent crashes
        self.Columns.Add(level_col)
        
        # Floor to Floor Height column
        height_col = Forms.GridColumn()
        height_col.HeaderText = "FloorToFloor"
        height_col.DataCell = Forms.TextBoxCell(1)  # Index 1 for height
        # Remove fixed width to allow auto-sizing
        height_col.Editable = False  # Disable editing to prevent crashes
        self.Columns.Add(height_col)
        
        # Elevation column (read-only)
        elev_col = Forms.GridColumn()
        elev_col.HeaderText = "Elevation (ReadOnly)"
        elev_col.DataCell = Forms.TextBoxCell(2)  # Index 2 for elevation
        # Remove fixed width to allow auto-sizing
        elev_col.Editable = False  # Make elevation column read-only
        self.Columns.Add(elev_col)
        
    def load_default_levels(self):
        """Load default levels from settings or create default set."""
        saved_levels = DATA_FILE.get_sticky("quick_massing_levels", None, DATA_FILE.DataType.DICT, tiny_wait=True)
        if saved_levels and isinstance(saved_levels, list):
            self.levels = saved_levels
        else:
            # Create default levels
            self.levels = [
                {"name": "Level B1", "height": 4.5, "is_datum": False},
                {"name": "Level 1", "height": 6.0, "is_datum": True},
                {"name": "Level 2", "height": 4.5, "is_datum": False},
                {"name": "Level 3", "height": 4.5, "is_datum": False}
            ]
            
    def get_elevation_for_level(self, level_index):
        """Calculate elevation for a specific level based on DATUM level and cumulative heights."""
        if not isinstance(self.levels, list) or level_index < 0 or level_index >= len(self.levels):
            return 0
        
        # Find DATUM level index
        datum_index = None
        for i, level in enumerate(self.levels):
            if isinstance(level, dict) and level.get("is_datum", False):
                datum_index = i
                break
        
        if datum_index is None:
            # If no DATUM level found, use the first level as base
            datum_index = 0
        
        # DATUM level always has elevation 0
        if level_index == datum_index:
            return 0.0
        
        # Calculate elevation based on DATUM level position
        if level_index > datum_index:
            # Level is above DATUM - add heights from DATUM to this level
            elevation = 0.0
            for i in range(datum_index, level_index):
                if i < len(self.levels) and isinstance(self.levels[i], dict):
                    elevation += self.levels[i].get("height", 0)
            return elevation
        else:
            # Level is below DATUM - subtract heights from this level to DATUM
            elevation = 0.0
            for i in range(level_index, datum_index):
                if i < len(self.levels) and isinstance(self.levels[i], dict):
                    elevation -= self.levels[i].get("height", 0)
            return elevation
                
    def load_data(self):
        """Load data into the grid with error handling."""
        try:
            if not isinstance(self.levels, list):
                print("ERROR: Levels is not a list")
                return
                
            # Create data tuples for the grid
            # Display levels in reverse order (highest elevation at top, lowest at bottom)
            data_tuples = []
            for i in reversed(range(len(self.levels))):
                level = self.levels[i]
                
                if not isinstance(level, dict):
                    continue
                    
                elevation = self.get_elevation_for_level(i)
                
                data_tuples.append((
                    level.get("name", ""),
                    str(level.get("height", 0)),
                    str(elevation)
                ))
            
            # Set the data store
            self.DataStore = data_tuples
            
        except Exception as ex:
            print("ERROR loading data: {}".format(str(ex)))
            
    def add_level(self, index=None):
        """Add a new level at the specified index."""
        if not isinstance(self.levels, list):
            self.levels = []
            
        if index is None:
            index = len(self.levels)
            
        new_level = {
            "name": "Level {}".format(len(self.levels) + 1),
            "height": 4.5,
            "is_datum": False
        }
        self.levels.insert(index, new_level)
        self.load_data()
        self.save_levels()
        
    def remove_level(self, grid_index):
        """Remove level at specified grid index, but not DATUM level."""
        level_index = self.grid_index_to_level_index(grid_index)
        if not isinstance(self.levels, list) or len(self.levels) <= 1:
            return
        
        # Prevent removing DATUM level
        if self.levels[level_index].get("is_datum", False):
            return  # Cannot remove DATUM level
            
        if 0 <= level_index < len(self.levels):
            del self.levels[level_index]
            self.load_data()
            self.save_levels()
            
    def grid_index_to_level_index(self, grid_index):
        """Convert grid row index to actual level index (reversed)."""
        try:
            if not isinstance(self.levels, list) or len(self.levels) == 0:
                print("ERROR: levels is not a list or is empty")
                return -1
            if grid_index < 0 or grid_index >= len(self.levels):
                print("ERROR: grid_index {} out of range for levels length {}".format(grid_index, len(self.levels)))
                return -1
            result = len(self.levels) - 1 - grid_index
            print("Converted grid_index {} to level_index {}".format(grid_index, result))
            return result
        except Exception as ex:
            print("ERROR in grid_index_to_level_index: {}".format(str(ex)))
            return -1
    
    def level_index_to_grid_index(self, level_index):
        """Convert actual level index to grid row index (reversed)."""
        try:
            if not isinstance(self.levels, list) or len(self.levels) == 0:
                print("ERROR: levels is not a list or is empty")
                return -1
            if level_index < 0 or level_index >= len(self.levels):
                print("ERROR: level_index {} out of range for levels length {}".format(level_index, len(self.levels)))
                return -1
            result = len(self.levels) - 1 - level_index
            print("Converted level_index {} to grid_index {}".format(level_index, result))
            return result
        except Exception as ex:
            print("ERROR in level_index_to_grid_index: {}".format(str(ex)))
            return -1
    
    def move_level(self, grid_index, direction):
        """Move level in specified direction (up/down in elevation order).
        
        Args:
            grid_index: Index in the grid display
            direction: "up" (towards higher elevation/top of display) or "down" (towards lower elevation/bottom of display)
        """
        try:
            level_index = self.grid_index_to_level_index(grid_index)
            
            # Check if trying to move DATUM level itself
            if self.levels[level_index].get("is_datum", False):
                return  # Cannot move DATUM level itself
            
            # Determine target index based on direction
            if direction == "up":
                # Move up = towards higher elevation = towards top of display = towards index 0
                target_index = level_index - 1
                if level_index <= 0:
                    return
            elif direction == "down":
                # Move down = towards lower elevation = towards bottom of display = towards higher index
                target_index = level_index + 1
                if level_index >= len(self.levels) - 1:
                    return
            else:
                return
            
            # Validate target index
            if target_index < 0 or target_index >= len(self.levels):
                return
            
            # Disable preview during move operation
            self.disable_preview()
                
            self.levels[level_index], self.levels[target_index] = self.levels[target_index], self.levels[level_index]
            
            # Calculate new selection index after the move
            if direction == "up":
                new_selection_index = grid_index - 1  # Moving up means selection moves up in grid
            else:  # direction == "down"
                new_selection_index = grid_index + 1  # Moving down means selection moves down in grid
            
            self.load_data()
            self.save_levels()
            
            # Restore selection to the new position
            if 0 <= new_selection_index < len(self.levels):
                self.SelectedRowIndex = new_selection_index
            
            # Re-enable preview after move is complete
            self.enable_preview()
            
        except Exception as ex:
            print("ERROR moving level {}: {}".format(direction, str(ex)))
    
    def move_level_up(self, grid_index):
        """Move level up in elevation (towards higher elevation, top of grid display)."""
        self.move_level(grid_index, "up")
            
    def move_level_down(self, grid_index):
        """Move level down in elevation (towards lower elevation, bottom of grid display)."""
        self.move_level(grid_index, "down")
            
    def save_levels(self):
        """Save levels to settings with error handling."""
        try:
            DATA_FILE.set_sticky("quick_massing_levels", self.levels, DATA_FILE.DataType.DICT, tiny_wait=True)
        except Exception as ex:
            print("ERROR saving levels: {}".format(str(ex)))
    
    def on_cell_edited(self, sender, e):
        """Handle cell edited events - fires after user finishes editing."""
        try:
            print("=== CELL EDITED DEBUG ===")
            print("Event type: {}".format(type(e)))
            print("Event Row: {}".format(getattr(e, 'Row', 'NO_ROW')))
            print("Event Column: {}".format(getattr(e, 'Column', 'NO_COLUMN')))
            
            # Get row and column from event
            row = getattr(e, 'Row', None)
            column = getattr(e, 'Column', None)
            
            print("Extracted - Row: {}, Column: {}".format(row, column))
            
            # Validate we have the minimum required data
            if row is None or column is None:
                print("ERROR: Missing row or column information")
                return
            
            # Process the cell edit directly (CellEdited fires after edit is complete)
            self.process_cell_edit(row, column, e)
            
        except Exception as ex:
            print("=== CELL EDITED CRITICAL ERROR ===")
            print("Error type: {}".format(type(ex).__name__))
            print("Error message: {}".format(str(ex)))
            import traceback
            print("Full traceback:")
            traceback.print_exc()
            print("=== END CRITICAL ERROR ===")
            return
    
    def process_cell_edit(self, row, column, e):
        """Process the cell edit with comprehensive validation."""
        try:
            print("=== PROCESS CELL EDIT ===")
            print("Row: {}, Column: {}".format(row, column))
            print("Event type: {}".format(type(e)))
            print("Levels type: {}".format(type(self.levels)))
            print("Levels count: {}".format(len(self.levels) if isinstance(self.levels, list) else "Not a list"))
            
            # Validate levels data
            if not isinstance(self.levels, list) or len(self.levels) == 0:
                print("ERROR: Levels is not a valid list or is empty")
                return
            
            # Validate row index
            if row < 0 or row >= len(self.levels):
                print("ERROR: Row index {} out of range for levels length {}".format(row, len(self.levels)))
                return
            
            # Convert grid row index to level index with error handling
            try:
                level_index = self.grid_index_to_level_index(row)
                print("Converted level_index: {}".format(level_index))
            except Exception as conv_ex:
                print("ERROR in grid_index_to_level_index conversion: {}".format(str(conv_ex)))
                return
            
            # Validate level index
            if level_index < 0 or level_index >= len(self.levels):
                print("ERROR: Invalid level_index: {}".format(level_index))
                return
            
            # Get level data with validation
            try:
                level = self.levels[level_index]
                print("Level data: {}".format(level))
            except Exception as level_ex:
                print("ERROR accessing level data: {}".format(str(level_ex)))
                return
            
            # Validate level is a dictionary
            if not isinstance(level, dict):
                print("ERROR: Level is not a dict: {}".format(type(level)))
                return
            
            # Get the new value from the event (recommended approach)
            try:
                print("Event Item: {}".format(getattr(e, 'Item', 'NO_ITEM')))
                print("Event Column: {}".format(column))
                
                # Use e.Item[e.Column] as recommended in Eto.Forms documentation
                if hasattr(e, 'Item') and e.Item is not None:
                    if isinstance(e.Item, (list, tuple)) and column < len(e.Item):
                        new_value = e.Item[column]
                        print("New value from e.Item[{}]: {}".format(column, new_value))
                    else:
                        print("ERROR: e.Item is not accessible or column out of range")
                        return
                else:
                    print("ERROR: e.Item is None or not available")
                    return
                
            except Exception as data_ex:
                print("ERROR getting value from event: {}".format(str(data_ex)))
                import traceback
                print("Event access traceback:")
                traceback.print_exc()
                return
            
            # Update level data based on column with individual error handling
            try:
                if column == 0:  # Level name column
                    print("Editing level name: {} -> {}".format(level.get("name", ""), str(new_value)))
                    level["name"] = str(new_value)
                elif column == 1:  # Height column
                    print("Editing height: {} -> {}".format(level.get("height", 0), new_value))
                    try:
                        new_height = float(new_value)
                        if new_height < 0:
                            print("WARNING: Negative height value, setting to 0")
                            new_height = 0.0
                        level["height"] = new_height
                        print("Height updated successfully: {}".format(level["height"]))
                    except (ValueError, TypeError) as ve:
                        print("Height conversion error: {}".format(str(ve)))
                        level["height"] = 0.0
                else:
                    print("WARNING: Unknown column index: {}".format(column))
                    return
                
                print("Level after update: {}".format(level))
                
            except Exception as update_ex:
                print("ERROR updating level data: {}".format(str(update_ex)))
                return
            
            # Save changes with error handling
            try:
                print("Saving levels...")
                self.save_levels()
                print("Levels saved successfully")
            except Exception as save_ex:
                print("ERROR saving levels: {}".format(str(save_ex)))
                return
            
            # Refresh grid display with error handling
            try:
                print("Loading data...")
                self.load_data()  # Refresh the grid display
                print("Grid data loaded successfully")
            except Exception as load_ex:
                print("ERROR loading grid data: {}".format(str(load_ex)))
                return
            
            # Trigger refresh callback with error handling
            try:
                print("Triggering refresh callback...")
                if self.refresh_callback:
                    self.refresh_callback()
                    print("Refresh callback completed successfully")
                else:
                    print("No refresh callback set")
            except Exception as callback_ex:
                print("ERROR in refresh callback: {}".format(str(callback_ex)))
                # Don't return here - callback error shouldn't stop the process
            
            print("Cell editing completed successfully")
                        
        except Exception as ex:
            print("=== PROCESS CELL EDIT CRITICAL ERROR ===")
            print("Error type: {}".format(type(ex).__name__))
            print("Error message: {}".format(str(ex)))
            import traceback
            print("Full traceback:")
            traceback.print_exc()
            print("=== END CRITICAL ERROR ===")
            # Don't re-raise the exception to prevent Rhino crash
            return
    
    def disable_preview(self):
        """Disable preview generation to avoid rapid-fire changes during editing."""
        self.preview_enabled = False
        print("Preview disabled")
    
    def enable_preview(self):
        """Re-enable preview generation after editing is complete."""
        self.preview_enabled = True
        print("Preview enabled")
    
    def refresh_preview(self, selected_surfaces=None, is_final_creation=False):
        """Shared method to refresh preview massing with validation and cleanup."""
        try:
            # Check if preview is enabled
            if not self.preview_enabled:
                print("Preview disabled - skipping refresh")
                return
            
            # Disable auto redraw for better performance during preview generation
            rs.EnableRedraw(False)
            
            # 1. Validate all input ready: level data and input surfaces
            if not isinstance(self.levels, list) or len(self.levels) == 0:
                return  # No level data available
            
            # Use provided surfaces or create preview surface
            if selected_surfaces and len(selected_surfaces) > 0:
                surfaces_to_use = selected_surfaces
            else:
                # Create a simple preview surface for demonstration
                preview_surface = self.create_preview_surface()
                if not preview_surface:
                    return  # Cannot create preview surface
                surfaces_to_use = [preview_surface]
            
            # 2. Purge previous temp preview elements by keyword (only for preview, not final creation)
            if not is_final_creation:
                self.purge_temp_massing()
            
            # 3. Make new elements for massing and text dots
            for surface in surfaces_to_use:
                self.create_massing_for_surface(surface, is_final_creation)
            
            # Re-enable auto redraw after preview generation is complete
            rs.EnableRedraw(True)
            
        except Exception:
            # Re-enable auto redraw even if there's an error
            rs.EnableRedraw(True)
            # Silently handle preview errors to not interrupt main functionality
            pass
    
    def generate_preview_massing(self):
        """Legacy method - now calls shared refresh_preview."""
        self.refresh_preview()
    
    def purge_temp_massing(self):
        """Remove all temporary massing objects from the document."""
        try:
            # Get all objects in the document
            all_objects = rs.AllObjects()
            if all_objects:
                for obj in all_objects:
                    if rs.IsObject(obj):
                        obj_name = rs.ObjectName(obj)
                        if obj_name and ("TEMP_MASSING_PREVIEW" in str(obj_name) or "TEMP_MASSING_PREVIEW_TEXT" in str(obj_name)):
                            rs.DeleteObject(obj)
        except Exception:
            # Silently handle purge errors
            pass
    
    def create_preview_surface(self):
        """Create a simple preview surface for massing demonstration."""
        try:
            # Create a simple rectangular surface for preview
            points = [
                [0, 0, 0],
                [10, 0, 0], 
                [10, 10, 0],
                [0, 10, 0],
                [0, 0, 0]
            ]
            
            # Create the surface
            surface = rs.AddSrfPt(points)
            if surface:
                # Name the surface for identification
                rs.ObjectName(surface, "TEMP_MASSING_PREVIEW_SURFACE")
                return surface
        except Exception:
            pass
        return None
    
    def create_massing_for_surface(self, surface, is_final_creation=False):
        """Create massing for a single surface based on configured levels.
        Uses consistent stacking logic: each level builds its own massing using its floor-to-floor height."""
        if not isinstance(self.levels, list) or len(self.levels) == 0:
            return
        
        # Find DATUM level index (base level)
        datum_index = None
        for i, level in enumerate(self.levels):
            if isinstance(level, dict) and level.get("is_datum", False):
                datum_index = i
                break
        
        if datum_index is None:
            # If no DATUM level found, use the first level as base
            datum_index = 0
        
        # Create massing for each level using consistent logic
        self.create_massing_consistent_stacking(surface, datum_index, is_final_creation)
    
    def create_massing_consistent_stacking(self, surface, datum_index, is_final_creation=False):
        """Create massing using consistent stacking logic: each level builds its own massing using its floor-to-floor height."""
        try:
            # Process ALL levels using their own elevation and floor-to-floor height
            for i in range(len(self.levels)):
                level = self.levels[i]
                if not isinstance(level, dict):
                    continue
                    
                level_height = level.get("height", 0)
                level_elevation = self.get_elevation_for_level(i)
                
                # Create massing for this level using its own elevation and floor-to-floor height
                self.create_single_level_massing(surface, level, i, level_elevation, level_height, is_final_creation)
            
        except Exception as ex:
            print("ERROR in consistent stacking: {}".format(str(ex)))
    
    def create_single_level_massing(self, surface, level, level_index, level_elevation, level_height, is_final_creation=False):
        """Create massing for a single level using its floor-to-floor height."""
        try:
            
            # Copy surface to level elevation
            level_surface = rs.CopyObject(surface, [0, 0, level_elevation])
            if not level_surface:
                print("ERROR: Failed to copy surface for level {}".format(level_index))
                return
            
            # Create extrusion curve using this level's floor-to-floor height
            extrusion_curve = rs.AddCurve([
                [0, 0, 0],
                [0, 0, level_height]
            ])
            
            if extrusion_curve:
                # Create the massing volume and name it
                massing_obj = rs.ExtrudeSurface(level_surface, extrusion_curve)
                if massing_obj:
                    # Name the object based on whether it's preview or final creation
                    if is_final_creation:
                        object_name = "MASSING_LEVEL_{}_{}".format(level_index, level.get("name", ""))
                    else:
                        object_name = "TEMP_MASSING_PREVIEW_LEVEL_{}".format(level_index)
                    rs.ObjectName(massing_obj, object_name)
                    # Add text label to the center of the massing
                    self.add_massing_text_label(massing_obj, level, level_index, is_final_creation)
                else:
                    print("ERROR: Failed to create massing object for level {}".format(level_index))
                
                rs.DeleteObject(extrusion_curve)
            else:
                print("ERROR: Failed to create extrusion curve for level {}".format(level_index))
            
            # Clean up
            rs.DeleteObject(level_surface)
            
        except Exception as ex:
            print("=== SINGLE LEVEL MASSING ERROR ===")
            print("Error type: {}".format(type(ex).__name__))
            print("Error message: {}".format(str(ex)))
            import traceback
            print("Full traceback:")
            traceback.print_exc()
            print("=== END SINGLE LEVEL MASSING ERROR ===")
    
    def create_massing_for_datum_level(self, surface, datum_index, base_elevation):
        """Create massing for the DATUM level itself."""
        level = self.levels[datum_index]
        if not isinstance(level, dict):
            return
            
        level_height = level.get("height", 0)
        
        # Copy surface for DATUM level
        current_surface = rs.CopyObject(surface, [0, 0, base_elevation])
        if not current_surface:
            return
            
        # Create extrusion curve for DATUM level
        extrusion_curve = rs.AddCurve([
            [0, 0, 0],
            [0, 0, level_height]
        ])
        
        if extrusion_curve:
            # Create the massing volume and name it
            massing_obj = rs.ExtrudeSurface(current_surface, extrusion_curve)
            if massing_obj:
                rs.ObjectName(massing_obj, "TEMP_MASSING_PREVIEW_LEVEL_{}".format(datum_index))
                # Add text label to the center of the massing
                self.add_massing_text_label(massing_obj, level, datum_index)
            
            rs.DeleteObject(extrusion_curve)
        
        # Clean up
        rs.DeleteObject(current_surface)
    
    def create_massing_upward(self, surface, datum_index, base_elevation):
        """Create massing from DATUM level upward."""
        current_surface = surface
        cumulative_height = 0
        
        # Process levels above DATUM level
        for i in range(datum_index + 1, len(self.levels)):
            level = self.levels[i]
            if not isinstance(level, dict):
                continue
                
            level_height = level.get("height", 0)
            
            # Create extrusion curve upward from current position
            extrusion_curve = rs.AddCurve([
                [0, 0, 0],
                [0, 0, level_height]
            ])
            
            # Move surface to correct elevation (DATUM + cumulative height)
            rs.MoveObject(current_surface, [0, 0, cumulative_height])
            
            # Create the massing volume and name it
            massing_obj = rs.ExtrudeSurface(current_surface, extrusion_curve)
            if massing_obj:
                rs.ObjectName(massing_obj, "TEMP_MASSING_PREVIEW_LEVEL_{}".format(i))
                # Add text label to the center of the massing
                self.add_massing_text_label(massing_obj, level, i)
            
            rs.DeleteObject(extrusion_curve)
            
            # Update cumulative height for next level
            cumulative_height += level_height
            
            # Copy surface for next level
            if current_surface != surface:
                rs.DeleteObject(current_surface)
            current_surface = rs.CopyObject(surface, [0, 0, level_height])
        
        # Clean up
        if current_surface != surface:
            rs.DeleteObject(current_surface)
    
    def create_massing_downward(self, surface, datum_index, base_elevation):
        """Create massing from DATUM level downward."""
        current_surface = surface
        cumulative_height = 0
        
        # Process levels below DATUM level (in reverse order)
        for i in range(datum_index - 1, -1, -1):
            level = self.levels[i]
            if not isinstance(level, dict):
                continue
                
            level_height = level.get("height", 0)
            
            # Create extrusion curve downward from current position
            extrusion_curve = rs.AddCurve([
                [0, 0, 0],
                [0, 0, -level_height]  # Negative for downward extrusion
            ])
            
            # Move surface to correct elevation (DATUM - cumulative height)
            rs.MoveObject(current_surface, [0, 0, -cumulative_height])
            
            # Create the massing volume and name it
            massing_obj = rs.ExtrudeSurface(current_surface, extrusion_curve)
            if massing_obj:
                rs.ObjectName(massing_obj, "TEMP_MASSING_PREVIEW_LEVEL_{}".format(i))
                # Add text label to the center of the massing
                self.add_massing_text_label(massing_obj, level, i)
            
            rs.DeleteObject(extrusion_curve)
            
            # Update cumulative height for next level
            cumulative_height += level_height
            
            # Copy surface for next level
            if current_surface != surface:
                rs.DeleteObject(current_surface)
            current_surface = rs.CopyObject(surface, [0, 0, -level_height])
        
        # Clean up
        if current_surface != surface:
            rs.DeleteObject(current_surface)
    
    def add_massing_text_label(self, massing_obj, level, level_index, is_final_creation=False):
        """Add text label to the center of a massing object."""
        try:
            # Get the bounding box of the massing object
            bbox = rs.BoundingBox(massing_obj)
            if not bbox:
                return
            
            # Calculate center point
            center = [
                (bbox[0][0] + bbox[2][0]) / 2,
                (bbox[0][1] + bbox[2][1]) / 2,
                (bbox[0][2] + bbox[2][2]) / 2
            ]
            
            # Get level data
            level_name = level.get("name", "Level {}".format(level_index + 1))
            level_height = level.get("height", 0)
            elevation = self.get_elevation_for_level(level_index)
            
            # Create text dot label
            text_content = "{} @ {} w/ {}".format(level_name, elevation, level_height)
            text_obj = rs.AddTextDot(text_content, center)
            
            if text_obj:
                # Name the text object based on whether it's preview or final creation
                if is_final_creation:
                    text_name = "TEXT_LEVEL_{}_{}".format(level_index, level_name)
                else:
                    text_name = "TEMP_MASSING_PREVIEW_TEXT_{}".format(level_index)
                rs.ObjectName(text_obj, text_name)
                
        except Exception:
            # Silently handle text creation errors
            pass

class QuickMassingDialog(Forms.Form):
    """Modeless dialog for QuickMassing level editor interface."""
    
    def __init__(self):
        """Initialize dialog UI components and default state."""
        # Eto initials
        self.Title = "Quick Massing - Level Editor"
        self.Resizable = True
        self.Padding = Drawing.Padding(10)
        self.Spacing = Drawing.Size(5, 5)
        self.Size = Drawing.Size(400, 500)
        self.Closed += self.OnFormClosed
        
        # Initialize data
        self.selected_surfaces = []
        
        # Create layout
        self.create_layout()
        
        # Apply dark style with logo
        RHINO_UI.apply_dark_style(self)
        
    def create_logo_image(self):
        """Create logo image for the dialog."""
        self.logo = Forms.ImageView()
        
        # Use the same logo path pattern as other forms
        from EnneadTab import IMAGE
        logo_path = IMAGE.get_image_path_by_name("icon_logo_dark_background.png")
        if logo_path and os.path.exists(logo_path):
            temp_bitmap = Drawing.Bitmap(logo_path)
            self.logo.Image = temp_bitmap.WithSize(200, 30)
        else:
            # Fallback to a simple text label if logo not found
            self.logo = Forms.Label(Text="Quick Massing", Font=Drawing.Font("Arial", 14, Drawing.FontStyle.Bold))
        
        return self.logo
        
    def create_layout(self):
        """Create the main dialog layout."""
        layout = Forms.DynamicLayout()
        layout.Padding = Drawing.Padding(10)
        layout.Spacing = Drawing.Size(5, 5)
        
        # Add logo at the top
        layout.AddSeparateRow(None, self.create_logo_image())
        layout.AddRow(None)  # Spacer
        
        # Surface picker section
        surface_section = Forms.GroupBox(Text="Surface Selection")
        surface_layout = Forms.DynamicLayout()
        surface_layout.Padding = Drawing.Padding(5)
        
        self.surface_picker_button = Forms.Button(Text="Pick Surfaces for Massing")
        self.surface_picker_button.Click += self.on_pick_surfaces
        self.surface_info_label = Forms.Label(Text="No surfaces selected")
        
        surface_layout.AddRow(self.surface_picker_button)
        surface_layout.AddRow(self.surface_info_label)
        surface_section.Content = surface_layout
        
        # Level editor section
        level_section = Forms.GroupBox(Text="Level Editor")
        level_layout = Forms.DynamicLayout()
        level_layout.Padding = Drawing.Padding(5)
        
        # Create level editor table
        self.level_table = LevelEditorTable()
        # Set refresh callback to use selected surfaces
        setattr(self.level_table, 'refresh_callback', self.refresh_level_preview)
        
        # Add control buttons for level management
        controls_layout = Forms.DynamicLayout()
        
        self.add_level_button = Forms.Button(Text="Add Level")
        self.add_level_button.Click += self.on_add_level
        
        self.remove_level_button = Forms.Button(Text="Remove Selected")
        self.remove_level_button.Click += self.on_remove_level
        
        self.move_up_button = Forms.Button(Text="Move Up (Higher Elevation)")
        self.move_up_button.Click += self.on_move_level_up
        
        self.move_down_button = Forms.Button(Text="Move Down (Lower Elevation)")
        self.move_down_button.Click += self.on_move_level_down
        
        self.edit_level_button = Forms.Button(Text="Edit Selected Level")
        self.edit_level_button.Click += self.on_edit_level
        
        controls_layout.AddRow(self.add_level_button, self.remove_level_button)
        controls_layout.AddRow(self.move_up_button, self.move_down_button)
        controls_layout.AddRow(self.edit_level_button)
        
        level_layout.AddRow(self.level_table)
        level_layout.AddRow(controls_layout)
        level_section.Content = level_layout
        
        # Action buttons
        action_layout = Forms.DynamicLayout()
        
        self.create_button = Forms.Button(Text="Create Massing")
        self.create_button.Click += self.on_create_massing
        
        self.cancel_button = Forms.Button(Text="Cancel")
        self.cancel_button.Click += self.on_cancel_clicked
        
        action_layout.AddRow(None, self.create_button, self.cancel_button)
        
        # Add sections to main layout
        layout.AddRow(surface_section)
        layout.AddRow(level_section)
        layout.AddRow(action_layout)
        
        self.Content = layout

    @ERROR_HANDLE.try_catch_error()
    def on_pick_surfaces(self, sender, e):
        """Handle surface picking with surface filter."""
        try:
            # Clear previous selection
            rs.UnselectAllObjects()
            
            # Get surfaces with filter
            surfaces = rs.GetObjects("Select surfaces for massing", filter=rs.filter.surface)
            if surfaces:
                self.selected_surfaces = surfaces
                self.surface_info_label.Text = "{} surface(s) selected".format(len(surfaces))
                NOTIFICATION.messenger("Selected {} surface(s) for massing".format(len(surfaces)))
                # Save selected surfaces
                self.save_surfaces()
                # Generate preview massing with selected surfaces
                self.level_table.refresh_preview(self.selected_surfaces)
            else:
                self.selected_surfaces = []
                self.surface_info_label.Text = "No surfaces selected"
                
        except Exception as e:
            NOTIFICATION.messenger("Error picking surfaces: {}".format(str(e)))
    
    def refresh_level_preview(self):
        """Refresh the level preview with current selected surfaces."""
        self.level_table.refresh_preview(self.selected_surfaces)
            
    @ERROR_HANDLE.try_catch_error()
    def on_add_level(self, sender, e):
        """Add a new level to the table."""
        self.level_table.add_level()
        # Generate preview after adding level
        self.level_table.refresh_preview(self.selected_surfaces)
        
    @ERROR_HANDLE.try_catch_error()
    def on_remove_level(self, sender, e):
        """Remove selected level from the table."""
        selected_rows = list(self.level_table.SelectedRows)
        if selected_rows and len(selected_rows) > 0:
            selected_index = selected_rows[0]
            # Check if trying to remove DATUM level
            level_index = self.level_table.grid_index_to_level_index(selected_index)
            if self.level_table.levels[level_index].get("is_datum", False):
                NOTIFICATION.messenger("Cannot remove DATUM level - it must stay as the reference level")
                return
            self.level_table.remove_level(selected_index)
            # Generate preview after removing level
            self.level_table.refresh_preview(self.selected_surfaces)
    
    @ERROR_HANDLE.try_catch_error()
    def on_move_level_up(self, sender, e):
        """Move selected level up in elevation (towards top of list)."""
        selected_rows = list(self.level_table.SelectedRows)
        if selected_rows and len(selected_rows) > 0:
            selected_index = selected_rows[0]
            # Check if trying to move DATUM level
            level_index = self.level_table.grid_index_to_level_index(selected_index)
            if self.level_table.levels[level_index].get("is_datum", False):
                NOTIFICATION.messenger("Cannot move DATUM level - it must stay at elevation 0")
                return
            # Move up in elevation means move towards top of list (decrease grid index)
            self.level_table.move_level_up(selected_index)
            # Generate preview after moving level
            self.level_table.refresh_preview(self.selected_surfaces)
    
    @ERROR_HANDLE.try_catch_error()
    def on_move_level_down(self, sender, e):
        """Move selected level down in elevation (towards bottom of list)."""
        selected_rows = list(self.level_table.SelectedRows)
        if selected_rows and len(selected_rows) > 0:
            selected_index = selected_rows[0]
            # Check if trying to move DATUM level
            level_index = self.level_table.grid_index_to_level_index(selected_index)
            if self.level_table.levels[level_index].get("is_datum", False):
                NOTIFICATION.messenger("Cannot move DATUM level - it must stay at elevation 0")
                return
            # Move down in elevation means move towards bottom of list (increase grid index)
            self.level_table.move_level_down(selected_index)
            # Generate preview after moving level
            self.level_table.refresh_preview(self.selected_surfaces)
    
    @ERROR_HANDLE.try_catch_error()
    def on_edit_level(self, sender, e):
        """Handle edit level button click - open simple edit dialog."""
        try:
            # Check if any rows are selected
            selected_rows = list(self.level_table.SelectedRows)
            if not selected_rows or len(selected_rows) == 0:
                NOTIFICATION.messenger("Please select a level to edit")
                return
            
            selected_index = selected_rows[0]
            level_index = self.level_table.grid_index_to_level_index(selected_index)
            
            if level_index < 0 or level_index >= len(self.level_table.levels):
                NOTIFICATION.messenger("Invalid level selection")
                return
            
            level = self.level_table.levels[level_index]
            
            # Create simple edit dialog
            edit_dialog = Forms.Dialog()
            edit_dialog.Title = "Edit Level: {}".format(level.get("name", ""))
            edit_dialog.Size = Drawing.Size(300, 200)
            edit_dialog.Resizable = False
            
            # Create layout
            layout = Forms.DynamicLayout()
            layout.Padding = Drawing.Padding(10)
            layout.Spacing = Drawing.Size(5, 5)
            
            # Level name input
            layout.AddRow(Forms.Label(Text="Level Name:"))
            name_textbox = Forms.TextBox()
            name_textbox.Text = level.get("name", "")
            layout.AddRow(name_textbox)
            
            # Height input
            layout.AddRow(Forms.Label(Text="Floor-to-Floor Height:"))
            height_textbox = Forms.TextBox()
            height_textbox.Text = str(level.get("height", 0))
            layout.AddRow(height_textbox)
            
            # Buttons
            button_layout = Forms.DynamicLayout()
            ok_button = Forms.Button(Text="OK")
            cancel_button = Forms.Button(Text="Cancel")
            
            button_layout.AddRow(ok_button, cancel_button)
            layout.AddRow(button_layout)
            
            edit_dialog.Content = layout
            
            # Disable preview during editing to avoid rapid-fire changes
            self.level_table.disable_preview()
            
            # Handle button clicks
            def on_ok_click(s, ev):
                try:
                    # Update level data
                    level["name"] = name_textbox.Text
                    try:
                        level["height"] = float(height_textbox.Text)
                        if level["height"] < 0:
                            level["height"] = 0.0
                    except (ValueError, TypeError):
                        level["height"] = 0.0
                    
                    # Save and refresh
                    self.level_table.save_levels()
                    self.level_table.load_data()
                    
                    # Re-enable preview and refresh
                    self.level_table.enable_preview()
                    self.level_table.refresh_preview(self.selected_surfaces)
                    edit_dialog.Close()
                except Exception as ex:
                    print("ERROR updating level: {}".format(str(ex)))
                    NOTIFICATION.messenger("Error updating level: {}".format(str(ex)))
            
            def on_cancel_click(s, ev):
                # Re-enable preview even if cancelled
                self.level_table.enable_preview()
                edit_dialog.Close()
            
            ok_button.Click += on_ok_click
            cancel_button.Click += on_cancel_click
            
            # Show dialog
            edit_dialog.ShowModal()
            
        except Exception as ex:
            print("ERROR in on_edit_level: {}".format(str(ex)))
            NOTIFICATION.messenger("Error opening edit dialog: {}".format(str(ex)))

    @ERROR_HANDLE.try_catch_error()
    def on_create_massing(self, sender, e):
        """Create massing based on level configuration."""
        if not self.selected_surfaces:
            NOTIFICATION.messenger("Please select surfaces first")
            return
            
        if not self.level_table.levels:
            NOTIFICATION.messenger("Please configure at least one level")
            return
       
        self.Close()
        self.create_massing()
        
    @ERROR_HANDLE.try_catch_error()
    def create_massing(self):
        """Create massing based on configured levels."""
        if not self.selected_surfaces:
            NOTIFICATION.messenger("No surfaces selected for massing")
            return
            
        if not self.level_table.levels:
            NOTIFICATION.messenger("No levels configured")
            return

        try:
            # Use the unified preview logic with final creation flag
            self.level_table.refresh_preview(self.selected_surfaces, is_final_creation=True)
            
            # Save level configuration after successful massing creation
            self.level_table.save_levels()
            
            NOTIFICATION.messenger("Created final massing for {} surface(s)".format(len(self.selected_surfaces)))
            
        except Exception as e:
            NOTIFICATION.messenger("Error creating final massing: {}".format(str(e)))
            
    # Old create_massing_for_surface method removed - now using unified preview logic
    
    # Old create_massing_upward and create_massing_downward methods removed - now using unified preview logic

    
    def save_surfaces(self):
        """Save selected surfaces to settings."""
        try:
            if self.selected_surfaces:
                DATA_FILE.set_sticky("quick_massing_surfaces", self.selected_surfaces, DATA_FILE.DataType.STR, tiny_wait=True)
        except Exception:
            # If saving fails, continue silently
            pass

    def on_cancel_clicked(self, sender, e):
        """Handle cancel button click."""
        self.Close()
        
    def OnFormClosed(self, sender, e):
        """Handle form closed event."""
        # Clean up temp massing objects when dialog closes
        try:
            self.level_table.purge_temp_massing()
        except Exception:
            pass
            
        if sc.sticky.has_key(FORM_KEY):
            del sc.sticky[FORM_KEY]
        self.Close()


# @ERROR_HANDLE.try_catch_error()
def quick_massing():
    """Open the QuickMassing dialog as a modeless UI in Rhino."""
    try:
        if sc.sticky.has_key(FORM_KEY):
            return
            
        dlg = QuickMassingDialog()
        dlg.Owner = Rhino.UI.RhinoEtoApp.MainWindow
        dlg.Show()
        sc.sticky[FORM_KEY] = dlg
    except Exception:
        print (traceback.format_exc())
    
if __name__ == "__main__":
    quick_massing()