#!/usr/bin/python
# -*- coding: utf-8 -*-

__doc__ = """Open EnneadTab-ARVR: Mobile Camera AR Overlay for 3D Models.

Beam any 3D model directly onto your smartphone camera in augmented reality with zero app installs:
- Instant QR-code room pairing between desktop and phone
- Instant mobile camera AR overlay with 1:1 spatial anchors
- WebGL desktop model inspection and real-time syncing

Export your Revit model to glTF/GLB or select from presets, then scan with your phone camera.
Opens https://enneadtab.com/arvr in your browser.
"""
__title__ = "AR/VR\nOverlay"

import proDUCKtion # pyright: ignore 
proDUCKtion.validify()

import webbrowser

from EnneadTab import ERROR_HANDLE, LOG, NOTIFICATION
from EnneadTab.REVIT import REVIT_APPLICATION
from Autodesk.Revit import DB # pyright: ignore 

UIDOC = REVIT_APPLICATION.get_uidoc()
DOC = REVIT_APPLICATION.get_doc()


@LOG.log(__file__, __title__)
@ERROR_HANDLE.try_catch_error()
def arvr_overlay(doc):
    url = "https://enneadtab.com/arvr"
    NOTIFICATION.messenger(
        main_text="Opening EnneadTab-ARVR web hub.\n\n"
                  "Export your Revit geometry or choose from presets, "
                  "then scan the QR code with your mobile camera for zero-install AR.")
    webbrowser.open(url)


################## main code below #####################
if __name__ == "__main__":
    arvr_overlay(DOC)
