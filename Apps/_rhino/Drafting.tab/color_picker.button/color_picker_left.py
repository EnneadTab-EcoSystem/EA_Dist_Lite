__title__ = "ColorPicker"
__doc__ = """Open an online color palette generator in your browser for scheme inspiration.

Starts you off on a preset EnneadTab palette that you can shuffle and lock until the mix
feels right, then take the codes back into Rhino, Revit or a presentation."""

import webbrowser
from EnneadTab import ERROR_HANDLE, LOG


@LOG.log(__file__, __title__)
@ERROR_HANDLE.try_catch_error()
def color_picker():
    webbrowser.open("https://coolors.co/d6f6dd-dac4f7-f4989c-ebd2b4-acecf7")

    
if __name__ == "__main__":
    color_picker()
