__title__ = "D5AssetLocator"
__doc__ = """Open the Render Asset Editor - the EnneadTab app for D5 and Enscape assets.

This tool has moved out of EnneadTab into its own standalone, auto-updating application, so it can
ship fixes without waiting on an EnneadTab release. It now covers D5 AND Enscape in one place. This
button opens its page in your browser; install it once and it keeps itself up to date from then on.

What it does:
- Locate hidden D5 asset folders across your system
- Access and modify materials on D5 objects
- Customize properties of those beautiful D5 trees, furniture and people
- Save hours of searching through obscure file directories

https://enneadtab.com/render-asset-editor
"""

__is_popular__ = True
import webbrowser
from EnneadTab import ERROR_HANDLE, LOG

RENDER_ASSET_EDITOR_URL = "https://enneadtab.com/render-asset-editor"


@LOG.log(__file__, __title__)
@ERROR_HANDLE.try_catch_error()
def d5_asset_locator():
    webbrowser.open(RENDER_ASSET_EDITOR_URL)


if __name__ == "__main__":
    d5_asset_locator()
