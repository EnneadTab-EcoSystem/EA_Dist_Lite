
__title__ = "MakeCrvPipe"
__doc__ = """Draw thin pipes along the curves on your [EDGE] layers so Enscape renders the edge.

Enscape will not show a line where two coplanar faces meet, which flattens joints and reveals
seams that should read as crisp. A slim pipe on the curve gives it something solid to shade.

Usage:
1. Put the curves you want to read as edges on a layer with [EDGE] in its name
2. Run the button; existing pipes are rebuilt rather than duplicated"""

from EnneadTab import ERROR_HANDLE
import rhinoscriptsyntax as rs
import scriptcontext as sc
import Rhino # pyright: ignore
import System # pyright: ignore
from EnneadTab import LOG, ERROR_HANDLE


@LOG.log(__file__, __title__)
@ERROR_HANDLE.try_catch_error()
def make_crv_pipe():

    for layer in rs.LayerNames():
        if "[EDGE]" in layer:
            break
    else:
        EnneadTab.NOTIFICATION.messenger("Cannot find any layer with [EDGE] in the name...")
        return


    rs.EnableRedraw(False)
    objs = rs.ObjectsByLayer(layer)
    crvs = [x for x in objs if rs.IsCurve(x)]
    print ("Found {} curves".format(len(crvs)))
    others = list(set(objs) - set(crvs))
    if others:
        rs.DeleteObjects(others)

    pipes = [rs.AddPipe(x, 0,0.1) for x in crvs]
    breps = [rs.coercebrep(x) for x in pipes]
    rs.DeleteObjects(pipes)

    mesh_setting = Rhino.Geometry.MeshingParameters.FastRenderMesh 
    for brep in breps:
        meshes = Rhino.Geometry.Mesh.CreateFromBrep(brep, mesh_setting)
        joined_mesh = Rhino.Geometry.Mesh()
        joined_mesh.Append(meshes)
        
    
        mesh_obj = sc.doc.Objects.AddMesh(joined_mesh)
        rs.ObjectLayer(mesh_obj, layer)

    EnneadTab.NOTIFICATION.messenger("Edge Pipe updated")




if __name__ == "__main__":
    make_crv_pipe()