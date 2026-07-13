
__title__ = "DestroyLayer"
__doc__ = """Delete layers outright, even when they still hold objects.

Rhino normally refuses to remove a layer that is in use, especially when a block definition
is holding it hostage. This clears the objects out and takes the layer with them, so a
bloated layer tree can finally be pruned.

Usage:
1. Run the button and pick the layers to remove
2. The layers and everything on them are gone once you confirm"""

import rhinoscriptsyntax as rs
import scriptcontext as sc
from EnneadTab.RHINO import RHINO_LAYER
from EnneadTab import LOG, ERROR_HANDLE


@LOG.log(__file__, __title__)
@ERROR_HANDLE.try_catch_error()
def destroy_layer():
    layers = RHINO_LAYER.get_layers(message="What layers to destory?")  
    if not layers: return

    for layer in layers:
        print (layer)
        print (rs.IsLayer(layer))
        rs.PurgeLayer(layer)




if __name__ == "__main__":
    destroy_layer()