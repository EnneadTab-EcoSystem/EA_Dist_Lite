
__title__ = "GetGoogleEarthModel"
__doc__ = """Open the video tutorial on pulling a Google Earth 3D context model into Rhino.

Walks you through capturing the surrounding city in Blender and bringing it across, which
is the quickest way to get a real site context around your massing. A companion Blender
script sits in this button's folder and tidies up the imported materials first."""


from EnneadTab import ERROR_HANDLE, LOG
import webbrowser
@LOG.log(__file__, __title__)
@ERROR_HANDLE.try_catch_error()
def get_google_earth_model():
    webbrowser.open("https://www.youtube.com/watch?v=YtlK4046VRQ")

    print ("Also check script folder for the python script used in blender")

    
if __name__ == "__main__":
    get_google_earth_model()
