# -*- coding: utf-8 -*-
__title__ = "ARVROverlay"
__doc__ = """Open EnneadTab-ARVR: Mobile Camera AR Overlay for 3D Models.

Beam any 3D model directly onto your smartphone camera in augmented reality with zero app installs:
- Instant QR-code room pairing between desktop and phone
- Instant mobile camera AR overlay with 1:1 spatial anchors
- WebGL desktop model inspection and real-time syncing

Opens https://enneadtab.com/arvr in your browser.
"""

__is_popular__ = True
import webbrowser
from EnneadTab import ERROR_HANDLE, LOG, NOTIFICATION

@LOG.log(__file__, __title__)
@ERROR_HANDLE.try_catch_error()
def arvr_overlay():
    url = "https://enneadtab.com/arvr"
    NOTIFICATION.messenger(
        main_text="Opening EnneadTab-ARVR web hub.\n\n"
                  "Export your selected geometry as .glb or choose from presets, "
                  "then scan the QR code with your mobile camera for zero-install AR.")
    webbrowser.open(url)

if __name__ == "__main__":
    arvr_overlay()
