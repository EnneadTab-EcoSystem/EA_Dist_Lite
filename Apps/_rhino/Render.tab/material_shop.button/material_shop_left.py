__title__ = "MaterialShop"
__doc__ = """Open AmbientCG in your browser, a free library of rendering materials.

Hundreds of ready-to-use textures, HDRI skies and props, all free to download and drop into
a Rhino or Enscape scene. Good first stop when a render needs a convincing surface."""


from EnneadTab import ERROR_HANDLE, LOG
import webbrowser

@LOG.log(__file__, __title__)
@ERROR_HANDLE.try_catch_error()
def material_shop():
    webbrowser.open("https://ambientcg.com/")

    
if __name__ == "__main__":
    material_shop()
