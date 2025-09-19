
__title__ = "EnneadCity"
__doc__ = "Work on your plot - GUI Interface"

import rhinoscriptsyntax as rs
import scriptcontext as sc

import os
import sys
from EnneadTab import ERROR_HANDLE, LOG
# get current script file directory
my_directory = os.path.dirname(os.path.realpath(__file__))

sys.path.append(my_directory)

try:
    import city_utility # pyright: ignore
    import ennead_city_gui # pyright: ignore
except Exception as e:
    print("Error importing EnneadCity modules: {}".format(str(e)))
    import rhinoscriptsyntax as rs
    rs.MessageBox("Error loading EnneadCity modules. Please check the installation.")

# Modules loaded successfully
@LOG.log(__file__, __title__)
@ERROR_HANDLE.try_catch_error()
def ennead_city():

    """Show the EnneadCity GUI interface for plot management"""
    try:
        return ennead_city_gui.ennead_city_gui()
    except Exception as e:
        print("Error showing EnneadCity GUI: {}".format(str(e)))
        import rhinoscriptsyntax as rs
        rs.MessageBox("Error showing EnneadCity GUI: {}".format(str(e)))
        return False

    
if __name__ == "__main__":
    ennead_city()
