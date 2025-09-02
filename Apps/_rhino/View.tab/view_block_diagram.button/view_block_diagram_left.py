
__title__ = "ViewBlockDiagram"
__doc__ = "This button does ViewBlockDiagram when left click"


from EnneadTab import ERROR_HANDLE, LOG

@LOG.log(__file__, __title__)
@ERROR_HANDLE.try_catch_error()
def view_block_diagram():
    print ("Placeholder func <{}> that does this:{}".format(__title__, __doc__))

    
if __name__ == "__main__":
    view_block_diagram()
