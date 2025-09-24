
__title__ = "CheckErrorLog"
__doc__ = "Opens the Google error log URL in the default browser"


from EnneadTab import ERROR_HANDLE, LOG, ENVIRONMENT
import webbrowser

@LOG.log(__file__, __title__)
@ERROR_HANDLE.try_catch_error()
def check_error_log():
    """Open the Google error log URL in the default browser."""
    google_error_log_url = ENVIRONMENT.ERROR_LOG_GOOGLE_FORM_RESULT
    print("Opening Google error log URL: {}".format(google_error_log_url))
    webbrowser.open(google_error_log_url)

    
if __name__ == "__main__":
    check_error_log()
