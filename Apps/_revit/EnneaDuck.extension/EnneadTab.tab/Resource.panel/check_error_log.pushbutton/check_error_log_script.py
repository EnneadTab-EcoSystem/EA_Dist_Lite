#!/usr/bin/python
# -*- coding: utf-8 -*-

__doc__ = "Opens the EnneadTab error log Google Form in your default browser. This allows you to view and submit error reports, track known issues, and stay updated on bug fixes and improvements. Essential for troubleshooting and providing feedback to the EnneadTab development team."
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