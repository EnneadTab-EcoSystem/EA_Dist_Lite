"""
EnneadTab Logging System

A comprehensive logging system for tracking and analyzing EnneadTab script usage.
This module provides detailed function execution logging with timing, arguments,
and results tracking across different environments.

Key Features:
    - Detailed function execution logging
    - Execution time tracking and formatting
    - Cross-environment compatibility (Revit/Rhino)
    - Automatic log file backup
    - User-specific log files
    - Context manager for temporary logging
    - JSON-based log storage
    - UTF-8 encoding support

Note:
    Log files are stored in the EA dump folder with user-specific naming
    and automatic backup functionality.
"""

import time
from contextlib import contextmanager
import io
import pprint  # For pretty printing log data

import USER
import TIME
import FOLDER
import DATA_FILE
import ENVIRONMENT
import ERROR_HANDLE

LOG_FILE_NAME = "log_{}".format(USER.USER_NAME)

# Google Form field IDs for usage logging
USAGE_LOG_FORM_FIELDS = {
    'entry.333183173': 'environment',     # Environment field
    'entry.1318607272': 'function_name',  # FunctionName field  
    'entry.1785264643': 'result',         # Result field
}


def _build_usage_form_data(environment, function_name, result):
    """Build form data dictionary for usage logging Google Form.
    
    Args:
        environment (str): The application environment
        function_name (str): The name of the function that was executed
        result (str): The result of the function execution
        
    Returns:
        dict: Form data dictionary with field IDs and values
    """
    return {
        'entry.333183173': environment,     # Environment field
        'entry.1318607272': function_name,  # FunctionName field  
        'entry.1785264643': result,         # Result field
    }


@contextmanager
def log_usage(func, *args):
    """Context manager for temporary function usage logging.
    
    Creates a detailed log entry for a single function execution including
    start time, duration, arguments, and results.

    Args:
        func (callable): Function to log
        *args: Arguments to pass to the function

    Yields:
        Any: Result of the function execution

    Example:
        with log_usage(my_function, arg1, arg2) as result:
            # Function execution is logged
            process_result(result)
    """
    t_start = time.time()
    res = func(*args)
    yield res
    t_end = time.time()
    duration = TIME.get_readable_time(t_end - t_start)
    with io.open(FOLDER.get_local_dump_folder_file(LOG_FILE_NAME), "a", encoding="utf-8") as f:
        f.writelines("\nRun at {}".format(TIME.get_formatted_time(t_start)))
        f.writelines("\nDuration: {}".format(duration))
        f.writelines("\nFunction name: {}".format(func.__name__))
        f.writelines("\nArguments: {}".format(args))
        f.writelines("\nResult: {}".format(res))


# with log_usage(LOG_FILE_NAME) as f:
#     f.writelines('\nYang is writing!')


"""log and log is break down becasue rhino need a wrapper to direct run script directly
whereas revit need to look at local func run"""


@FOLDER.backup_data(LOG_FILE_NAME, "log")
def log(script_path, func_name_as_record):
    """Decorator for persistent function usage logging.
    
    Creates a detailed JSON log entry for each function execution with
    timing, environment, and execution details. Includes automatic backup
    functionality.

    Args:
        script_path (str): Full path to the script file
        func_name_as_record (str|list): Function name or list of aliases
            to record. If list provided, longest name is used.

    Returns:
        callable: Decorated function with logging capability

    Example:
        @log("/path/to/script.py", "MyFunction")
        def my_function(arg1, arg2):
            # Function execution will be logged
            return result
    """
    # If a script has multiple aliases, just use the longest one as the record
    if isinstance(func_name_as_record, list):
        func_name_as_record = max(func_name_as_record, key=len)

    def decorator(func):
        def wrapper(*args, **kwargs):
            try:
                with DATA_FILE.update_data(LOG_FILE_NAME) as data:
                    t_start = time.time()
                    out = func(*args, **kwargs)
                    t_end = time.time()
                    if not data:
                        data = dict()
                    data[TIME.get_formatted_current_time()] = {
                        "application": ENVIRONMENT.get_app_name(),
                        "function_name": func_name_as_record.replace("\n", " "),
                        "arguments": args,
                        "result": str(out),
                        "script_path": script_path,
                        "duration": TIME.get_readable_time(t_end - t_start),
                    }

                    # print ("data to be place in log is ", data)

                # Send usage data to Google Form
                try:
                    environment = ENVIRONMENT.get_app_name()
                    function_name = func_name_as_record.replace("\n", " ")
                    result = str(out)
                    send_usage_to_google_form(environment, function_name, result)
                except Exception as e:
                    # Don't let Google Form errors break the main logging
                    pass

                return out
            except:
                out = func(*args, **kwargs)
                return out

        return wrapper

    return decorator


def read_log(user_name=USER.USER_NAME):
    """Display formatted log entries for a specific user.
    
    Retrieves and pretty prints the JSON log data for the specified user,
    showing all recorded function executions and their details.

    Args:
        user_name (str, optional): Username to read logs for.
            Defaults to current user.

    Note:
        Output is formatted with proper indentation for readability.
    """
    data = DATA_FILE.get_data(LOG_FILE_NAME)
    print("Printing user log from <{}>".format(user_name))
    pprint.pprint(data, indent=4)


def send_usage_to_google_form(environment, function_name, result):
    """Send usage information to Google Form for automated usage tracking.

    Sends usage details to a Google Form for automated usage tracking and analysis.
    Form includes environment, function name, and result information.
    
    Automatically detects the best available HTTP library based on environment:
    - Rhino: Uses urllib2/urllib (IronPython 2.7 style)
    - Revit: Uses urllib3 (if available)
    - Terminal/IDE: Uses built-in urllib modules (Python 3 style)

    Args:
        environment (str): The application environment (Revit/Rhino/etc.)
        function_name (str): The name of the function that was executed
        result (str): The result of the function execution
    """
    try:
        # Try different HTTP libraries based on environment availability
        if _try_urllib3_usage_implementation(environment, function_name, result):
            return
        elif _try_urllib2_usage_implementation(environment, function_name, result):
            return
        elif _try_urllib_request_usage_implementation(environment, function_name, result):
            return
        else:
            ERROR_HANDLE.print_note("No suitable HTTP library found for sending usage to Google Form")
            
    except Exception as e:
        # Don't let Google Form errors break the main logging
        ERROR_HANDLE.print_note("Failed to send usage to Google Form: {}".format(e))
        pass


def _try_urllib3_usage_implementation(environment, function_name, result):
    """Try to use urllib3 for sending usage data (Revit environment).
    
    Args:
        environment (str): The application environment
        function_name (str): The name of the function that was executed
        result (str): The result of the function execution
        
    Returns:
        bool: True if successful, False if urllib3 not available or failed
    """
    try:
        import urllib3
        
        # Google Form URL
        g_form_url = ENVIRONMENT.USAGE_LOG_GOOGLE_FORM_SUBMIT
        
        # Build form data using common helper function
        form_data = _build_usage_form_data(environment, function_name, result)
        
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
                ERROR_HANDLE.print_note("Usage data sent to Google Form successfully (urllib3)")
            else:
                ERROR_HANDLE.print_note("Form submission completed but may not have been recorded (urllib3)")
            return True
        else:
            ERROR_HANDLE.print_note("Failed to send usage data to Google Form - Status: {} (urllib3)".format(response.status))
            return False
            
    except ImportError:
        # urllib3 not available
        return False
    except Exception as e:
        ERROR_HANDLE.print_note("Error sending to Google Form (urllib3): {}".format(e))
        return False


def _try_urllib2_usage_implementation(environment, function_name, result):
    """Try to use urllib2 for sending usage data (Rhino environment).
    
    Args:
        environment (str): The application environment
        function_name (str): The name of the function that was executed
        result (str): The result of the function execution
        
    Returns:
        bool: True if successful, False if urllib2 not available or failed
    """
    try:
        import urllib2
        import urllib
        
        # Google Form URL
        g_form_url = ENVIRONMENT.USAGE_LOG_GOOGLE_FORM_SUBMIT
        
        # Build form data using common helper function
        form_data = _build_usage_form_data(environment, function_name, result)
        
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
            ERROR_HANDLE.print_note("Response content preview: {}".format(response_content[:200]))  # Debug: show first 200 chars
            if "Thank you" in response_content or "submitted" in response_content.lower():
                ERROR_HANDLE.print_note("Usage data sent to Google Form successfully (urllib2)")
            else:
                ERROR_HANDLE.print_note("Form submission completed but may not have been recorded (urllib2)")
                ERROR_HANDLE.print_note("This usually means the field IDs don't match the form fields")
            return True
        else:
            ERROR_HANDLE.print_note("Failed to send usage data to Google Form - Status: {} (urllib2)".format(response.getcode()))
            return False
            
    except ImportError:
        # urllib2 not available
        return False
    except urllib2.URLError as e:
        ERROR_HANDLE.print_note("Network error sending to Google Form (urllib2): {}".format(e))
        return False
    except Exception as e:
        ERROR_HANDLE.print_note("Error sending to Google Form (urllib2): {}".format(e))
        return False


def _try_urllib_request_usage_implementation(environment, function_name, result):
    """Try to use urllib.request for sending usage data (Terminal/IDE environment).
    
    Args:
        environment (str): The application environment
        function_name (str): The name of the function that was executed
        result (str): The result of the function execution
        
    Returns:
        bool: True if successful, False if urllib.request not available or failed
    """
    try:
        import urllib.request
        import urllib.parse
        
        # Google Form URL
        g_form_url = ENVIRONMENT.USAGE_LOG_GOOGLE_FORM_SUBMIT
        
        # Build form data using common helper function
        form_data = _build_usage_form_data(environment, function_name, result)
        
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
                ERROR_HANDLE.print_note("Usage data sent to Google Form successfully (urllib.request)")
            else:
                ERROR_HANDLE.print_note("Form submission completed but may not have been recorded (urllib.request)")
            return True
        else:
            ERROR_HANDLE.print_note("Failed to send usage data to Google Form - Status: {} (urllib.request)".format(response.getcode()))
            return False
            
    except ImportError:
        # urllib.request not available
        return False
    except urllib.error.URLError as e:
        ERROR_HANDLE.print_note("Network error sending to Google Form (urllib.request): {}".format(e))
        return False
    except Exception as e:
        ERROR_HANDLE.print_note("Error sending to Google Form (urllib.request): {}".format(e))
        return False


def unit_test():
    """Run comprehensive tests of the logging system.
    
    Tests log creation, reading, and backup functionality.
    """
    pass


###########################################################
if __name__ == "__main__":
    unit_test()
