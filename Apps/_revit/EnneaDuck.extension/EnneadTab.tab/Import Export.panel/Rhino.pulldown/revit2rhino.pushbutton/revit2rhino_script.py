#!/usr/bin/python
# -*- coding: utf-8 -*-

__doc__ = """Export the Revit elements of your choice to a Rhino file.

Pick the categories to export (walls, floors, windows, furniture, curtain panels...), then choose which family / type combinations to include. Each element is converted into a Rhino block instance placed at its original location, with the geometry (Breps, or Meshes as fallback) organized on layers by Category / Family / Subcategory.

Blocks are named after the family and type (a short suffix is added when the same type differs by parameters, or for system families such as walls). The export file name contains a timestamp, and Rhino opens when the export finishes.

Tip: Rhino.Inside must be running, and an architectural view (such as a 3D view) must be active. Only elements visible in the active view are listed. Elements from linked models are not exported.
"""

__title__ = "Revit2Rhino"

import clr  # pyright: ignore
import logging

# Configure logging. The action module shares this logger name and configures
# its own handler, so only add a console handler here if none exists yet
# (avoids duplicate log lines).
logger = logging.getLogger("Revit2Rhino")
logger.setLevel(logging.INFO)
if not logger.handlers:
    console_handler = logging.StreamHandler()
    console_handler.setLevel(logging.INFO)
    console_handler.setFormatter(logging.Formatter('%(levelname)s - %(message)s'))
    logger.addHandler(console_handler)


def enable_debug_logging():
    """Raise the shared Revit2Rhino logger AND every handler attached to it
    (including the one the action module adds) to DEBUG."""
    logger.setLevel(logging.DEBUG)
    for handler in logger.handlers:
        handler.setLevel(logging.DEBUG)
    logger.debug("Debug logging enabled")


IMPORT_ERROR = None
try:
    import System  # pyright: ignore
    clr.AddReference('RhinoCommon')
    import Rhino  # pyright: ignore
    clr.AddReference('RhinoInside.Revit')
    from RhinoInside.Revit.Convert.Geometry import GeometryDecoder as RIR_DECODER  # pyright: ignore
    IMPORT_OK = True
except Exception as e:
    IMPORT_OK = False
    IMPORT_ERROR = str(e)


import proDUCKtion  # pyright: ignore
proDUCKtion.validify()

from EnneadTab import ERROR_HANDLE, LOG, NOTIFICATION, USER
from EnneadTab.REVIT import REVIT_APPLICATION, REVIT_VIEW

UIDOC = REVIT_APPLICATION.get_uidoc()
DOC = REVIT_APPLICATION.get_doc()

@LOG.log(__file__, __title__)
@ERROR_HANDLE.try_catch_error()
def revit2rhino(doc):
    """Main entry point for Revit to Rhino export."""
    # Check if Rhino.Inside is available
    if not IMPORT_OK:
        logger.error("Rhino.Inside import failed: {}".format(IMPORT_ERROR))
        NOTIFICATION.messenger("Please initiate [Rhino.Inside] First")
        return

    if REVIT_VIEW.is_focused_on_system_view():
        NOTIFICATION.messenger("You are focused on either ProjectBrower or PropetyPanel. Please activate an Architectural View such as 3D View.")
        return
    
    if not REVIT_VIEW.is_archi_view(doc.ActiveView):
        NOTIFICATION.messenger("Please activate an Architectural View such as 3D View.")
        return
    
    # Launch the UI - everything else is handled by the UI.
    # Import first so the action module has attached its handler, then enable
    # debug logging so every handler on the shared logger is raised.
    import revit2rhino_UI
    if USER.IS_DEVELOPER:
        enable_debug_logging()
    revit2rhino_UI.show_dialog()


if __name__ == "__main__":
    revit2rhino(DOC)
