
__title__ = "Anything"
__doc__ = """Run the EnneadTab Lab scratch script, a sandbox for trying out ideas in Rhino.

Kept as a testing ground for behavior that is still being explored, so it does not read or
change anything in your model. Whatever it does is reported on the Rhino command line."""


from EnneadTab import ERROR_HANDLE, LOG, VERSION_CONTROL

@LOG.log(__file__, __title__)
@ERROR_HANDLE.try_catch_error()
def anything():
    print ("Placeholder func <{}> that does this:{}".format(__title__, __doc__))

    print (x)


    
if __name__ == "__main__":
    anything()
