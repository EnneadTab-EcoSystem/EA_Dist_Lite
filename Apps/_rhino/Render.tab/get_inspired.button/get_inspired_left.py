
__title__ = "GetInspired"
__doc__ = "Opens e.AI rendering website (https://enneadtab.com/rendering/home) in the default browser"


from EnneadTab import ERROR_HANDLE, LOG
import webbrowser

@LOG.log(__file__, __title__)
@ERROR_HANDLE.try_catch_error()
def get_inspired():
    url = "https://enneadtab.com/rendering/home"
    webbrowser.open(url)
    print("Opening {} in browser...".format(url))

    
if __name__ == "__main__":
    get_inspired()
