#!/usr/bin/python
# -*- coding: utf-8 -*-

__doc__ = """Open the EnneadTab error log in your browser to see reported bugs and their status.

Every error EnneadTab catches is filed here. Use it to check whether the problem
you just hit is already known, to see what has been fixed, or to add detail to a
report you sent in."""
__title__ = "Check\nError Log"
__context__ = "zero-doc"
__tip__ = True
import proDUCKtion # pyright: ignore 
proDUCKtion.validify()

from EnneadTab import ERROR_HANDLE, LOG, ENVIRONMENT
import webbrowser

@LOG.log(__file__, __title__)
@ERROR_HANDLE.try_catch_error()
def check_error_log():
    """Open the Google error log URL in the default browser."""
    google_error_log_url = ENVIRONMENT.ERROR_LOG_GOOGLE_FORM_RESULT
    print("Opening Google error log URL: {}".format(google_error_log_url))
    webbrowser.open(google_error_log_url)

################## main code below #####################
if __name__ == "__main__":
    check_error_log() 