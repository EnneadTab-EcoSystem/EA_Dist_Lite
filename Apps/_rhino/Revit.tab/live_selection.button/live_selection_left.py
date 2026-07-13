
__title__ = "LiveSelection"
__doc__ = """Mirror your Rhino selection over to Revit so both models highlight the same thing.

Saves hunting for the Revit counterpart of an object by hand when you are coordinating
between the two, which is where most cross-platform mistakes creep in."""


from EnneadTab import ERROR_HANDLE, LOG

@LOG.log(__file__, __title__)
@ERROR_HANDLE.try_catch_error()
def live_selection():
    print ("Placeholder func <{}> that does this:{}".format(__title__, __doc__))

    
if __name__ == "__main__":
    live_selection()
