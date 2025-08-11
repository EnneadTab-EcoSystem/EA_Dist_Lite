#!/usr/bin/python
# -*- coding: utf-8 -*-
"""Error handling and logging utilities for EnneadTab.

This module provides comprehensive error handling, logging, and reporting
functionality across the EnneadTab ecosystem. It includes automated error
reporting, developer debugging tools, and user notification systems.

Key Features:
- Automated error catching and logging
- Developer-specific debug messaging
- Error email notifications
- Stack trace formatting
- Silent error handling options
"""

import traceback

# Import modules with error handling
try:
    import ENVIRONMENT
except Exception as e:
    print("Error importing ENVIRONMENT in ERROR_HANDLE.py: {}".format(traceback.format_exc()))
    ENVIRONMENT = None

try:
    import EMAIL
except Exception as e:
    print("Error importing EMAIL in ERROR_HANDLE.py: {}".format(traceback.format_exc()))
    EMAIL = None

try:
    import USER
except Exception as e:
    print("Error importing USER in ERROR_HANDLE.py: {}".format(traceback.format_exc()))
    USER = None

try:
    import TIME
except Exception as e:
    print("Error importing TIME in ERROR_HANDLE.py: {}".format(traceback.format_exc()))
    TIME = None

try:
    import NOTIFICATION
except Exception as e:
    print("Error importing NOTIFICATION in ERROR_HANDLE.py: {}".format(traceback.format_exc()))
    NOTIFICATION = None

try:
    import OUTPUT
except Exception as e:
    print("Error importing OUTPUT in ERROR_HANDLE.py: {}".format(traceback.format_exc()))
    OUTPUT = None

try:
    import FOLDER
except Exception as e:
    print("Error importing FOLDER in ERROR_HANDLE.py: {}".format(traceback.format_exc()))
    FOLDER = None

try:
    import DATA_CONVERSION
except Exception as e:
    print("Error importing DATA_CONVERSION in ERROR_HANDLE.py: {}".format(traceback.format_exc()))
    DATA_CONVERSION = None


# Add recursion depth tracking
_error_handler_recursion_depth = 0
_max_error_handler_recursion_depth = 50  # Set a reasonable limit


####################################################################################################
"""
temp solution to debug where the error is coming from
"""


# Safe ENVIRONMENT accessor functions
def get_plugin_name():
    """Safely get plugin name with fallback."""
    if ENVIRONMENT is not None:
        try:
            return ENVIRONMENT.PLUGIN_NAME
        except:
            print(traceback.format_exc())
            pass
    return "EnneadTab"  # Default fallback

def get_plugin_extension():
    """Safely get plugin extension with fallback."""
    if ENVIRONMENT is not None:
        try:
            return ENVIRONMENT.PLUGIN_EXTENSION
        except:
            print(traceback.format_exc())
            pass
    return ".sexyDuck"  # Default fallback

def get_document_folder():
    """Safely get document folder with fallback."""
    if ENVIRONMENT is not None:
        try:
            return ENVIRONMENT.DOCUMENT_FOLDER
        except:
            print(traceback.format_exc())
            pass
    return None

def get_one_drive_desktop_folder():
    """Safely get OneDrive desktop folder with fallback."""
    if ENVIRONMENT is not None:
        try:
            return ENVIRONMENT.ONE_DRIVE_DESKTOP_FOLDER
        except:
            print(traceback.format_exc())
            pass
    return None

def get_error_log_google_form_submit():
    """Safely get error log Google form URL with fallback."""
    if ENVIRONMENT is not None:
        try:
            return ENVIRONMENT.ERROR_LOG_GOOGLE_FORM_SUBMIT
        except:
            print(traceback.format_exc())
            pass
    return None

def get_usage_log_google_form_submit():
    """Safely get usage log Google form URL with fallback."""
    if ENVIRONMENT is not None:
        try:
            return ENVIRONMENT.USAGE_LOG_GOOGLE_FORM_SUBMIT
        except:
            print(traceback.format_exc())
            pass
    return None

def get_app_name():
    """Safely get app name with fallback."""
    if ENVIRONMENT is not None:
        try:
            return ENVIRONMENT.get_app_name()
        except:
            print(traceback.format_exc())
            pass
    return "unknown"  # Default fallback

def is_revit_environment():
    """Safely check if in Revit environment."""
    if ENVIRONMENT is not None:
        try:
            return ENVIRONMENT.IS_REVIT_ENVIRONMENT
        except:
            print(traceback.format_exc())
            pass
    return False
####################################################################################################



def _ensure_recursion_depth_is_int():
    """Ensure _error_handler_recursion_depth is an integer, reset to 0 if not."""
    global _error_handler_recursion_depth
    if not isinstance(_error_handler_recursion_depth, int):
        print("WARNING: _error_handler_recursion_depth was {} with value {}, resetting to 0".format(type(_error_handler_recursion_depth), _error_handler_recursion_depth))
        _error_handler_recursion_depth = 0

def _safe_increment_recursion_depth():
    """Safely increment the recursion depth counter."""
    global _error_handler_recursion_depth
    _ensure_recursion_depth_is_int()
    _error_handler_recursion_depth += 1

def _safe_decrement_recursion_depth():
    """Safely decrement the recursion depth counter."""
    global _error_handler_recursion_depth
    _ensure_recursion_depth_is_int()
    _error_handler_recursion_depth -= 1

# Google Form field IDs for error logging
ERROR_LOG_FORM_FIELDS = {
    'entry.1706374190': 'error',         # Traceback field
    'entry.539936697': 'function_name',  # FunctionName field  
    'entry.730257591': 'user_name',      # UserName field
}


def _build_error_form_data(error, func_name, user_name):
    """Build form data dictionary for error logging Google Form.
    
    Args:
        error (str): The error message to send
        func_name (str): The name of the function where the error occurred
        user_name (str): The name of the user experiencing the error
        
    Returns:
        dict: Form data dictionary with field IDs and values
    """
    return {
        'entry.1706374190': error,         # Traceback field
        'entry.539936697': func_name,      # FunctionName field  
        'entry.730257591': user_name,      # UserName field
    }

def get_alternative_traceback():
    """Generate a formatted stack trace for the current exception.

    Creates a human-readable stack trace including exception type,
    message, and file locations. Output is visible to developers only.

    Returns:
        str: Formatted stack trace information
    """
    import sys
    OUT = []
    exc_type, exc_value, exc_traceback = sys.exc_info()
    
    # Handle exception type
    type_str = str(exc_type.__name__ if hasattr(exc_type, '__name__') else exc_type)
    OUT.append("Exception Type: {}".format(type_str))
    
    # Handle exception message
    try:
        msg = str(exc_value)
    except:
        msg = "Unable to convert error message to string"
    OUT.append("Exception Message: {}".format(msg))
    
    # Handle stack trace
    while exc_traceback:
        filename = str(exc_traceback.tb_frame.f_code.co_filename)
        lineno = str(exc_traceback.tb_lineno)
        OUT.append("File: {}, Line: {}".format(filename, lineno))
        exc_traceback = exc_traceback.tb_next

    result = "\n".join(OUT)
    if USER.IS_DEVELOPER:
        print(result)
    return result

def try_catch_error(is_silent=False, is_pass = False):
    """Decorator for catching exceptions and sending automated error log emails.

    Wraps functions to provide automated error handling, logging, and notification.
    Can operate in silent mode or pass-through mode for different error handling needs.

    Args:
        is_silent (bool, optional): If True, sends error email without user notification.
            Defaults to False.
        is_pass (bool, optional): If True, ignores errors without notification or email.
            Defaults to False.

    Returns:
        function: Decorated function with error handling
    """
    def decorator(func):
        def error_wrapper(*args, **kwargs):
            global _error_handler_recursion_depth, _max_error_handler_recursion_depth
            
            # Check if we've reached max depth
            _ensure_recursion_depth_is_int()
            if _error_handler_recursion_depth >= _max_error_handler_recursion_depth:
                print("Maximum error handler recursion depth reached ({})".format(str(_max_error_handler_recursion_depth)))
                # Just call the function directly without error handling
                return func(*args, **kwargs)
                
            # Increment depth counter
            _safe_increment_recursion_depth()
            
            try:
                out = func(*args, **kwargs)
                # Decrement depth counter before returning
                _safe_decrement_recursion_depth()
                return out
            except Exception as e:
                if is_pass:
                    # Ensure we decrement even when passing
                    _safe_decrement_recursion_depth()
                    return
                    
                # Safely convert error message to string, handling Array[str] objects
                try:
                    if e is None:
                        error_msg = "Unknown error (None)"
                    elif hasattr(e, '__iter__') and not isinstance(e, (str, bytes)):
                        # Handle array-like objects by joining them
                        try:
                            error_msg = " ".join(str(item) for item in e)
                        except:
                            error_msg = str(e)
                    else:
                        error_msg = str(e)
                except Exception as convert_error:
                    error_msg = "Unable to convert error to string: {}".format(str(convert_error))
                
                print_note(error_msg)
                print_note("error_Wrapper func for EA Log -- Error: " + error_msg)
                error_time = "Oops at {}\n\n".format(TIME.get_formatted_current_time())
                error = get_alternative_traceback()
                if not error:
                    try:
                        import traceback
                        error = traceback.format_exc()
                    except Exception as new_e:
                        error = error_msg
                        print(new_e)

                # Safely get plugin name with fallback
                plugin_name = get_plugin_name()
                
                subject_line = plugin_name + " Auto Error Log"
                if is_silent:
                    subject_line += "(Silent)"
                try:
                    EMAIL.email_error(error_time + error, func.__name__, USER.USER_NAME, subject_line=subject_line)
                except Exception as e:
                    print_note("Cannot send email: {}".format(get_alternative_traceback()))

                try:
                    send_error_to_google_form(error, func.__name__, USER.USER_NAME)
                except Exception as e:
                    pass

                if not is_silent:
                    try:
                        error_file = FOLDER.get_local_dump_folder_file("error_general_log.txt")
                        
              
                        error += "\n\n######If you have " + plugin_name + " UI window open, just close the original " + plugin_name + " window. Do no more action, otherwise the program might crash.##########\n#########Not sure what to do? Msg Sen Zhang, you have dicovered a important bug and we need to fix it ASAP!!!!!########BTW, a local copy of the error is available at {}".format(error_file)
                    except Exception as path_error:
                        # Fallback if FOLDER is not available
                        error_file = "error_general_log.txt"
                        error += "\n\n######If you have " + plugin_name + " UI window open, just close the original " + plugin_name + " window. Do no more action, otherwise the program might crash.##########\n#########Not sure what to do? Msg Sen Zhang, you have dicovered a important bug and we need to fix it ASAP!!!!!########BTW, a local copy of the error is available at {}".format(error_file)
                    try:
                        import io
                        with io.open(error_file, "w", encoding="utf-8") as f:
                            f.write(error)
                    except IOError as e:
                        print_note(e)

                    if OUTPUT is not None:
                        output = OUTPUT.get_output()
                        output.write(error_time, OUTPUT.Style.Subtitle)
                        output.write(error)
                        output.insert_divider()
                        output.plot()

                if is_revit_environment() and not is_silent and NOTIFICATION is not None:
                    NOTIFICATION.messenger(
                        "!Critical Warning, close all Revit UI window from " + plugin_name + " and reach to Sen Zhang.")
                
                # Make sure to decrement the counter even in case of exception
                _safe_decrement_recursion_depth()
                    
        error_wrapper.original_function = func
        return error_wrapper
    return decorator

def send_error_to_google_form(error, func_name, user_name):
    """Send error information to Google Form for automated error tracking.

    Sends error details to a Google Form for automated error tracking and analysis.
    Form includes error message, function name, and user information.
    
    Automatically detects the best available HTTP library based on environment:
    - Rhino: Uses urllib2/urllib (IronPython 2.7 style)
    - Revit: Uses urllib3 (if available)
    - Terminal/IDE: Uses built-in urllib modules (Python 3 style)

    Args:
        error (str): The error message to send
        func_name (str): The name of the function where the error occurred
        user_name (str): The name of the user experiencing the error
    """
    try:
        # Try different HTTP libraries based on environment availability
        if _try_urllib3_implementation(error, func_name, user_name):
            return
        elif _try_urllib2_implementation(error, func_name, user_name):
            return
        elif _try_urllib_request_implementation(error, func_name, user_name):
            return
        else:
            print_note("No suitable HTTP library found for sending error to Google Form")
            
    except Exception as e:
        # Don't let Google Form errors break the main error handling
        print_note("Failed to send error to Google Form: {}".format(e))
        pass


def _try_urllib3_implementation(error, func_name, user_name):
    """Try to use urllib3 for sending error data (Revit environment).
    
    Args:
        error (str): The error message to send
        func_name (str): The name of the function where the error occurred
        user_name (str): The name of the user experiencing the error
        
    Returns:
        bool: True if successful, False if urllib3 not available or failed
    """
    try:
        import urllib3
        import time
        
        # Google Form URL
        g_form_url = get_error_log_google_form_submit()
        if g_form_url is None:
            print_note("ENVIRONMENT not available, skipping Google Form submission")
            return False
        
        # Build form data using common helper function
        form_data = _build_error_form_data(error, func_name, user_name)
        
        # Create HTTP manager
        http = urllib3.PoolManager()
        
        # Headers
        headers = {
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36',
            'Content-Type': 'application/x-www-form-urlencoded',
            'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,image/webp,*/*;q=0.8',
            'Accept-Language': 'en-US,en;q=0.5',
            'Accept-Encoding': 'gzip, deflate',
            'Connection': 'keep-alive',
            'Upgrade-Insecure-Requests': '1'
        }
        
        # Encode form data
        encoded_data = urllib3.util.url.urlencode(form_data)
        
        # Send request
        response = http.request('POST', g_form_url, body=encoded_data, headers=headers, timeout=30.0)
        
        if response.status == 200:
            response_content = response.data.decode('utf-8')
            if "Thank you" in response_content or "submitted" in response_content.lower():
                print_note("Error data sent to Google Form successfully (urllib3)")
            else:
                print_note("Form submission completed but may not have been recorded (urllib3)")
            return True
        else:
            print_note("Failed to send error data to Google Form - Status: {} (urllib3)".format(response.status))
            return False
            
    except ImportError:
        # urllib3 not available
        return False
    except Exception as e:
        print_note("Error sending to Google Form (urllib3): {}".format(e))
        return False


def _try_urllib2_implementation(error, func_name, user_name):
    """Try to use urllib2 for sending error data (Rhino environment).
    
    Args:
        error (str): The error message to send
        func_name (str): The name of the function where the error occurred
        user_name (str): The name of the user experiencing the error
        
    Returns:
        bool: True if successful, False if urllib2 not available or failed
    """
    try:
        import urllib2 #pyright: ignore
        import urllib
        import time
        
        # Google Form URL
        g_form_url = get_error_log_google_form_submit()
        if g_form_url is None:
            print_note("ENVIRONMENT not available, skipping Google Form submission")
            return False
        
        # Build form data using common helper function
        form_data = _build_error_form_data(error, func_name, user_name)
        
        # Encode the data (IronPython 2.7 compatible)
        data = urllib.urlencode(form_data)
        
        # Create the request with comprehensive headers
        req = urllib2.Request(g_form_url, data)
        req.add_header('User-Agent', 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36')
        req.add_header('Content-Type', 'application/x-www-form-urlencoded')
        req.add_header('Accept', 'text/html,application/xhtml+xml,application/xml;q=0.9,image/webp,*/*;q=0.8')
        req.add_header('Accept-Language', 'en-US,en;q=0.5')
        req.add_header('Accept-Encoding', 'gzip, deflate')
        req.add_header('Connection', 'keep-alive')
        req.add_header('Upgrade-Insecure-Requests', '1')
        
        # Send the request
        response = urllib2.urlopen(req, timeout=30)
        # Google Forms returns a 200 status even on successful submission
        if response.getcode() == 200:
            # Read response to check for success indicators
            response_content = response.read()
            if "Thank you" in response_content or "submitted" in response_content.lower():
                # print_note("Error data sent to Google Form successfully (urllib2)")
                pass
            else:
                # print_note("Form submission completed but may not have been recorded (urllib2)")
                pass
            return True
        else:
            print_note("Failed to send error data to Google Form - Status: {} (urllib2)".format(response.getcode()))
            return False
            
    except ImportError:
        # urllib2 not available
        return False
    except urllib2.URLError as e:
        print_note("Network error sending to Google Form (urllib2): {}".format(e))
        return False
    except Exception as e:
        print_note("Error sending to Google Form (urllib2): {}".format(e))
        return False


def _try_urllib_request_implementation(error, func_name, user_name):
    """Try to use urllib.request for sending error data (Terminal/IDE environment).
    
    Args:
        error (str): The error message to send
        func_name (str): The name of the function where the error occurred
        user_name (str): The name of the user experiencing the error
        
    Returns:
        bool: True if successful, False if urllib.request not available or failed
    """
    try:
        import urllib.request
        import urllib.parse
        import time
        
        # Google Form URL
        g_form_url = get_error_log_google_form_submit()
        if g_form_url is None:
            print_note("ENVIRONMENT not available, skipping Google Form submission")
            return False
        
        # Build form data using common helper function
        form_data = _build_error_form_data(error, func_name, user_name)
        
        # Encode the data (Python 3.x compatible)
        data = urllib.parse.urlencode(form_data).encode('utf-8')
        
        # Create the request with comprehensive headers
        req = urllib.request.Request(g_form_url, data)
        req.add_header('User-Agent', 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36')
        req.add_header('Content-Type', 'application/x-www-form-urlencoded')
        req.add_header('Accept', 'text/html,application/xhtml+xml,application/xml;q=0.9,image/webp,*/*;q=0.8')
        req.add_header('Accept-Language', 'en-US,en;q=0.5')
        req.add_header('Accept-Encoding', 'gzip, deflate')
        req.add_header('Connection', 'keep-alive')
        req.add_header('Upgrade-Insecure-Requests', '1')
        
        # Send the request
        response = urllib.request.urlopen(req, timeout=30)
        # Google Forms returns a 200 status even on successful submission
        if response.getcode() == 200:
            # Read response to check for success indicators
            response_content = response.read().decode('utf-8')
            if "Thank you" in response_content or "submitted" in response_content.lower():
                print_note("Error data sent to Google Form successfully (urllib.request)")
            else:
                print_note("Form submission completed but may not have been recorded (urllib.request)")
            return True
        else:
            print_note("Failed to send error data to Google Form - Status: {} (urllib.request)".format(response.getcode()))
            return False
            
    except ImportError:
        # urllib.request not available
        return False
    except urllib.error.URLError as e:
        print_note("Network error sending to Google Form (urllib.request): {}".format(e))
        return False
    except Exception as e:
        print_note("Error sending to Google Form (urllib.request): {}".format(e))
        return False






def print_note(*args):
    """Print debug information visible only to developers.

    Formats and displays debug information with type annotations.
    Supports single or multiple arguments of any type.

    Args:
        *args: Variable number of items to display

    Example:
        print_note("hello", 123, ["a", "b"])
        Output:
            [Dev Debug Only Note]
            - str: hello
            - int: 123
            - list: ['a', 'b']
    """
    if not USER.IS_DEVELOPER:
        return
        
    try:
        from pyrevit import script #pyright: ignore
        output = script.get_output()
        
        # If single argument, keep original behavior
        if len(args) == 1:
            # Use utility function to safely convert to string
            if DATA_CONVERSION:
                arg_str = DATA_CONVERSION.safe_convert_to_string(args[0])
            else:
                try:
                    arg_str = str(args[0])
                except:
                    # Handle .NET Array objects that don't have .replace()
                    if hasattr(args[0], '__iter__') and not isinstance(args[0], (str, bytes)):
                        arg_str = "[" + ", ".join(str(item) for item in args[0]) + "]"
                    else:
                        arg_str = "Unable to convert to string"
            output.print_md("***[Dev Debug Only Note]***:{}".format(arg_str))
            return
            
        # For multiple arguments, print type and value for each
        output.print_md("***[Dev Debug Only Note]***")
        for arg in args:
            if DATA_CONVERSION:
                arg_str = DATA_CONVERSION.safe_convert_to_string(arg)
            else:
                try:
                    arg_str = str(arg)
                except:
                    # Handle .NET Array objects that don't have .replace()
                    if hasattr(arg, '__iter__') and not isinstance(arg, (str, bytes)):
                        arg_str = "[" + ", ".join(str(item) for item in arg) + "]"
                    else:
                        arg_str = "Unable to convert to string"
            output.print_md("- *{}*: {}".format(type(arg).__name__, arg_str))
            
    except Exception as e:
        # Fallback to print if pyrevit not available
        if len(args) == 1:
            if DATA_CONVERSION:
                arg_str = DATA_CONVERSION.safe_convert_to_string(args[0])
            else:
                try:
                    arg_str = str(args[0])
                except:
                    # Handle .NET Array objects that don't have .replace()
                    if hasattr(args[0], '__iter__') and not isinstance(args[0], (str, bytes)):
                        arg_str = "[" + ", ".join(str(item) for item in args[0]) + "]"
                    else:
                        arg_str = "Unable to convert to string"
            print("[Dev Debug Only Note]:{}".format(arg_str))
            return
            
        print("[Dev Debug Only Note]")
        for arg in args:
            if DATA_CONVERSION:
                arg_str = DATA_CONVERSION.safe_convert_to_string(arg)
            else:
                try:
                    arg_str = str(arg)
                except:
                    # Handle .NET Array objects that don't have .replace()
                    if hasattr(arg, '__iter__') and not isinstance(arg, (str, bytes)):
                        arg_str = "[" + ", ".join(str(item) for item in arg) + "]"
                    else:
                        arg_str = "Unable to convert to string"
            print("- {}: {}".format(type(arg).__name__, arg_str))


if __name__ == "__main__":
    send_error_to_google_form("test error", "test_function", "test_user")