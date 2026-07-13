
__title__ = "Text2ScriptSetting"
__doc__ = """Report the current settings of the Text2Script generator on the Rhino command line.

Right-click companion to Text2Script, the tool that turns a plain-English request into a
runnable Rhino script. Nothing in your model is read or changed."""


from EnneadTab import ERROR_HANDLE, LOG

@LOG.log(__file__, __title__)
@ERROR_HANDLE.try_catch_error()
def text2script_setting():
    print ("Placeholder func <{}> that does this:{}".format(__title__, __doc__))

    
if __name__ == "__main__":
    text2script_setting()
