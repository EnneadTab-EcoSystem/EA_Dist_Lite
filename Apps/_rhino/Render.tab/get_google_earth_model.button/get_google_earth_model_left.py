
__title__ = "GetGoogleEarthModel"
__doc__ = "Open a video tutorial on capturing Google Earth 3D context models through Blender. A companion Blender script (blosm.py) in this button folder cleans up the imported materials before bringing the model into Rhino."


from EnneadTab import ERROR_HANDLE, LOG
import webbrowser
@LOG.log(__file__, __title__)
@ERROR_HANDLE.try_catch_error()
def get_google_earth_model():
    webbrowser.open("https://www.youtube.com/watch?v=YtlK4046VRQ")

    print ("Also check script folder for the python script used in blender")

    
if __name__ == "__main__":
    get_google_earth_model()
