__title__ = "ViewToggle"

KEY = "F4"

__doc__ = """Flip the active viewport between Top and Perspective with one click.

Saves reaching for the viewport tabs every time you want to check a plan relationship and
then get back to the model. Running it also binds the F4 key to the same toggle, so from
then on you can switch with the keyboard alone."""


from EnneadTab import ERROR_HANDLE, LOG
import rhinoscriptsyntax as rs
import Rhino # pyright: ignore

@LOG.log(__file__, __title__)
@ERROR_HANDLE.try_catch_error()
def view_toggle():

    
    # Toggle between Top and Perspective views
    if rs.IsViewPerspective(rs.CurrentView()):  # Check if current view is Perspective
        rs.CurrentView("Top")
    else:
        rs.CurrentView("Perspective")



    keyboard_setting = Rhino.ApplicationSettings.ShortcutKeySettings
    keyboard_setting.SetMacro(Rhino.ApplicationSettings.ShortcutKey[KEY], 
                              "EA_{}".format(__title__))

    
if __name__ == "__main__":
    view_toggle()
