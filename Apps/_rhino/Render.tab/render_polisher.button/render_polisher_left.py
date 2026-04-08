# -*- coding: utf-8 -*-
__title__ = "EnneaDuck Render Studio"
__doc__ = """Open e.AI — EnneaDuck's rendering studio.

AI-powered rendering and video generation for architectural visualization:
- Multi-style image generation (Gemini + Imagen)
- Image editing and style transfer
- Video generation from stills
- Iterative conversational refinement

Opens ennead-ai.com in your default browser.
"""

__is_popular__ = True
import webbrowser
from EnneadTab import ERROR_HANDLE, LOG

@LOG.log(__file__, __title__)
@ERROR_HANDLE.try_catch_error()
def render_polisher():
    webbrowser.open("https://ennead-ai.com")

if __name__ == "__main__":
    render_polisher()
