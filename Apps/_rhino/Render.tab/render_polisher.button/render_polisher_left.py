__title__ = "RenderPolisher"
__doc__ = """Launch the Render Polisher application for enhancing and refining your renders!

This tool opens the RenderPolisher.exe application that helps you:
- Polish and enhance render outputs
- Apply post-processing effects
- Refine render quality and appearance
- Streamline your rendering workflow

Perfect for visualization specialists looking to take their renders to the next level.
"""

__is_popular__ = True
from EnneadTab import ERROR_HANDLE, LOG, EXE

@LOG.log(__file__, __title__)
@ERROR_HANDLE.try_catch_error()
def render_polisher():
    EXE.try_open_app("RenderPolisher")
    
if __name__ == "__main__":
    render_polisher()

