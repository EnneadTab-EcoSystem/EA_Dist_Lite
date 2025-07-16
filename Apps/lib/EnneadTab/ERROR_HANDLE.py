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
            if _error_handler_recursion_depth >= _max_error_handler_recursion_depth:
                print("Maximum error handler recursion depth reached ({})".format(_max_error_handler_recursion_depth))
                # Just call the function directly without error handling
                return func(*args, **kwargs)
                
            # Increment depth counter
            _error_handler_recursion_depth += 1
            
            try:
                out = func(*args, **kwargs)
                # Decrement depth counter before returning
                _error_handler_recursion_depth -= 1
                return out
            except Exception as e:
                if is_pass:
                    # Ensure we decrement even when passing
                    _error_handler_recursion_depth -= 1
                    return
                    
                # Safely convert error message to string, handling Array[str] objects
                try:
                    if hasattr(e, '__iter__') and not isinstance(e, (str, bytes)):
                        # Handle array-like objects by joining them
                        error_msg = " ".join(str(item) for item in e)
                    else:
                        error_msg = str(e)
                except:
                    error_msg = "Unable to convert error to string"
                
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

                subject_line = ENVIRONMENT.PLUGIN_NAME + " Auto Error Log"
                if is_silent:
                    subject_line += "(Silent)"
                try:
                    EMAIL.email_error(error_time + error, func.__name__, USER.USER_NAME, subject_line=subject_line)
                except Exception as e:
                    print_note("Cannot send email: {}".format(get_alternative_traceback()))

                if not is_silent:
                    try:
                        error_file = FOLDER.get_local_dump_folder_file("error_general_log.txt")
                        error += "\n\n######If you have " + ENVIRONMENT.PLUGIN_NAME + " UI window open, just close the original " + ENVIRONMENT.PLUGIN_NAME + " window. Do no more action, otherwise the program might crash.##########\n#########Not sure what to do? Msg Sen Zhang, you have dicovered a important bug and we need to fix it ASAP!!!!!########BTW, a local copy of the error is available at {}".format(error_file)
                    except Exception as path_error:
                        # Fallback if FOLDER is not available
                        error_file = "error_general_log.txt"
                        error += "\n\n######If you have " + ENVIRONMENT.PLUGIN_NAME + " UI window open, just close the original " + ENVIRONMENT.PLUGIN_NAME + " window. Do no more action, otherwise the program might crash.##########\n#########Not sure what to do? Msg Sen Zhang, you have dicovered a important bug and we need to fix it ASAP!!!!!########BTW, a local copy of the error is available at {}".format(error_file)
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

                if ENVIRONMENT.IS_REVIT_ENVIRONMENT and not is_silent:
                    NOTIFICATION.messenger(
                        main_text="!Critical Warning, close all Revit UI window from " + ENVIRONMENT.PLUGIN_NAME + " and reach to Sen Zhang.")
                
                # Make sure to decrement the counter even in case of exception
                _error_handler_recursion_depth -= 1
                    
        error_wrapper.original_function = func
        return error_wrapper
    return decorator



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
        from pyrevit import script
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


