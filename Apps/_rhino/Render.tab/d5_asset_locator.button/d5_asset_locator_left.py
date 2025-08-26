__title__ = "D5AssetLocator"
__doc__ = """Your personal detective for hunting down elusive D5 assets!

This handy tool launches the D5AssetChanger application that helps you:
- Locate hidden D5 asset folders across your system
- Access and modify materials on D5 objects
- Customize properties of those beautiful D5 trees, furniture and people
- Save hours of searching through obscure file directories

Perfect for visualization specialists who need precise control over their D5 assets.
"""

__is_popular__ = True
from EnneadTab import ERROR_HANDLE, LOG, EXE

@LOG.log(__file__, __title__)
@ERROR_HANDLE.try_catch_error()
def d5_asset_locator():
    EXE.try_open_app("D5AssetChanger")
    
if __name__ == "__main__":
    d5_asset_locator()
