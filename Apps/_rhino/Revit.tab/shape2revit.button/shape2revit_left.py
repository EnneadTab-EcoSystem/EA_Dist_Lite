__title__ = "Shape2Revit"
__doc__ = """Send loose Rhino geometry to Revit, turning each object into its own family.

For one-off shapes that were never organised into blocks. Every selected surface, solid or
mesh becomes a separate Revit family, so use it sparingly or the Revit file ends up carrying
hundreds of them. When your geometry is already blocked, reach for Block2Family instead: it
reuses one family per definition and keeps the Revit model far lighter.

Features:
- Works with surfaces, polysurfaces and meshes
- Original shape and placement are preserved
- Your Rhino model is left exactly as you had it"""

import rhinoscriptsyntax as rs
import scriptcontext as sc
from EnneadTab import ENVIRONMENT, ERROR_HANDLE, LOG, NOTIFICATION, DATA_FILE, FILE_NAME_UTILITY
from EnneadTab.RHINO import RHINO_OBJ_DATA, RHINO_UI
import Eto # pyright: ignore
import Rhino # pyright: ignore
import System # pyright: ignore

import os
import sys
# Add the block2family.button directory to sys.path
current_dir = os.path.dirname(__file__)
block2family_dir = os.path.abspath(os.path.join(current_dir, '..', 'block2family.button'))
if block2family_dir not in sys.path:
    sys.path.insert(0, block2family_dir)
import block2family_left as B2F # pyright: ignore

S2F_PREFIX = "{}_CONVERT_".format(ENVIRONMENT.PLUGIN_ABBR)

class Shape2RevitDialog(Eto.Forms.Dialog[bool]):
    def __init__(self):
        self.Title = "Shape2Revit"
        self.Padding = Eto.Drawing.Padding(10)
        self.Resizable = True
        self.MinimumSize = Eto.Drawing.Size(400, 300)
        
        # Create layout
        layout = Eto.Forms.DynamicLayout()
        layout.Padding = Eto.Drawing.Padding(10)
        layout.Spacing = Eto.Drawing.Size(5, 5)
        
        # Add description
        description = Eto.Forms.Label()
        description.Text = __doc__
        description.Wrap = Eto.Forms.WrapMode.Word
        layout.AddRow(description)
        
        # Add checkbox
        self.never_show = Eto.Forms.CheckBox()
        self.never_show.Text = "Never show this dialog again"
        layout.AddRow(self.never_show)
        
        # Add buttons
        button_layout = Eto.Forms.DynamicLayout()
        button_layout.Spacing = Eto.Drawing.Size(5, 0)
        
        self.confirm_button = Eto.Forms.Button(Text = "Confirm")
        self.confirm_button.Click += self.on_confirm
        
        self.cancel_button = Eto.Forms.Button(Text = "Cancel")
        self.cancel_button.Click += self.on_cancel
        
        button_layout.AddRow(None, self.confirm_button, self.cancel_button)
        layout.AddRow(button_layout)
        
        self.Content = layout
        RHINO_UI.apply_dark_style(self)
        
    def on_confirm(self, sender, e):
        if self.never_show.Checked:
            DATA_FILE.set_sticky("SHAPE2REVIT_NEVER_SHOW", True)
        self.Close(True)
        
    def on_cancel(self, sender, e):
        self.Close(False)

@LOG.log(__file__, __title__)
@ERROR_HANDLE.try_catch_error()
def shape2revit():
    # Check if we should show the dialog
    if not DATA_FILE.get_sticky("SHAPE2REVIT_NEVER_SHOW", False):
        dialog = Shape2RevitDialog()
        result = Rhino.UI.EtoExtensions.ShowSemiModal(dialog, Rhino.RhinoDoc.ActiveDoc, Rhino.UI.RhinoEtoApp.MainWindow)
        if not result:
            return
    
    # Get geometry with specific filters
    filter_value = rs.filter.surface | rs.filter.polysurface | rs.filter.mesh
    geos = rs.GetObjects("Select geometry to convert to Revit families, blocks will be ignored. Note this is a inefficent usage of revit, and will impact revit performance significantly.", filter_value)
    if not geos:
        return

    rs.EnableRedraw(False)
    temp_block_collection = []
    
    # Process each geometry
    for geo in geos:
        # Get bounding box center for insertion point
        bbox = rs.BoundingBox(geo)
        if not bbox:
            continue
        center = RHINO_OBJ_DATA.get_center(geo)
        
        # Create temporary block name with sanitization
        raw_block_name = "{}{}".format(S2F_PREFIX, str(geo)) # using guid from rs.parsing
        block_name = FILE_NAME_UTILITY.sanitize_revit_name(raw_block_name)
        
        # Create block from geometry
        if rs.IsBlock(block_name):
            rs.DeleteBlock(block_name)
        rs.AddBlock([geo], center, name=block_name, delete_input=False)
        
        # Insert block instance
        temp_block = rs.InsertBlock(block_name, center)
        if not temp_block:
            continue
        
        # Copy user data from original geometry to block instance
        user_keys = rs.GetUserText(geo)
        if user_keys:
            for key in user_keys:
                value = rs.GetUserText(geo, key)
                rs.SetUserText(temp_block, key, value)
        
        temp_block_collection.append(temp_block)

    B2F.block2family(temp_block_collection)
    rs.DeleteObjects(temp_block_collection)
    for block_name in rs.BlockNames():
        rs.DeleteBlock(block_name) if block_name.startswith(S2F_PREFIX) else None
    
    NOTIFICATION.messenger("Conversion complete!")
    
if __name__ == "__main__":
    shape2revit()
