# Error Diagnostics Improvements

## Overview
Enhanced error handling and diagnostics for `revit_remote_server_script.py` to provide better troubleshooting information when files fail to open, particularly for ACC (Autodesk Construction Cloud) files.

**IMPORTANT**: All external error logging now uses `error_registry.json` as the single source of truth. Job-specific errors can be in job `.sexyDuck` files, but no other external error files are created.

## Changes Made

### 1. Enhanced `_validate_file_before_open` Function (Lines 321-388)

#### New Features:
- **File Type Detection**: Automatically detects Local, ACC, and BIM360 files
- **Cloud-Specific Validation**: Special handling for ACC/BIM360 files with detailed diagnostics
- **BasicFileInfo Pre-check**: For cloud files, validates file integrity before attempting to open
- **Improved Error Messages**: Actionable error messages with specific troubleshooting steps

#### Improvements:
- **File Read Test**: Increased from 1 byte to 1KB for better issue detection
- **Error Code Capture**: Captures and reports specific I/O error codes
- **File Metadata Logging**: Logs worksharing status, format, and Revit version
- **Targeted Error Messages**: Different messages for different failure scenarios

#### Error Messages Now Include:
- File type (Local/ACC/BIM360)
- Specific troubleshooting steps
- Possible root causes
- File size and metadata

### 2. Enhanced `get_doc` Function (Lines 390-515)

#### New Features:
- **File Details Dictionary**: Captures comprehensive file metadata for diagnostics
  - `is_workshared`: Whether file uses worksharing
  - `format`: File format information
  - `saved_version`: Revit version file was saved in
  - `all_changes_saved`: Central model sync status

- **Structured Error Handling**: Separate try-catch for `OpenDocumentFile` operation
- **Error Classification**: Categorizes errors and provides specific solutions
  - COM/OLE errors (0x80004005)
  - Permission/Access errors
  - Corruption errors

#### Error Diagnostics Include:
1. **Error Type**: Python exception type
2. **Error Message**: Full error message from Revit
3. **File Path**: Complete path to the problem file
4. **File Details**: Metadata captured from BasicFileInfo
5. **Diagnosis**: Likely root cause of the issue
6. **Solutions**: Step-by-step troubleshooting instructions

### Example Enhanced Error Output

**Before:**
```
get_doc failed for 'C:\...\file.rvt': The model could not be opened: Unspecified error (COleException 0x80004005)
```

**After:**
```
OpenDocumentFile failed | Error type: Exception | Error message: The model could not be opened: Unspecified error (COleException 0x80004005) | File: C:\Users\...\SPARC_A_EA_CUNY_Building.rvt | File details: {'is_workshared': 'True', 'format': 'Revit2024', 'saved_version': '2024'} | DIAGNOSIS: COM/OLE error - often caused by cloud sync issues, file locks, or Autodesk services | SOLUTIONS: 1) Wait 1-2 minutes for cloud sync to complete, 2) Check Autodesk Desktop Connector status, 3) Verify no other user has file open, 4) Restart Revit if issue persists
```

## Benefits

### For Debugging:
1. **Faster Root Cause Analysis**: Error messages now include context about what went wrong
2. **Better Logging**: All diagnostic information is logged to debug files
3. **Cloud File Support**: Special handling for ACC/BIM360 sync issues

### For Users:
1. **Actionable Error Messages**: Users know what to try next
2. **Clear Diagnostics**: Users understand what went wrong
3. **Categorized Solutions**: Different solutions for different error types

### For Developers:
1. **Rich Debug Info**: File metadata captured before failure
2. **Error Patterns**: Can identify common failure patterns from error registry
3. **Maintainability**: Clear separation between validation, opening, and error handling

## Error Logging Consolidation

### Single Source of Truth: `error_registry.json`

All external error logging now goes ONLY to `error_registry.json`:

**✅ Allowed:**
- Job-specific data in `.sexyDuck` files (job status updates)
- `error_registry.json` for centralized error tracking
- `debug.txt` for debug messages (not errors)
- Console output for emergency failures

**❌ Removed/Deprecated:**
- ~~`_write_failure_payload()`~~ - Deprecated, replaced by `_log_unique_error()`
- ~~Separate `ERROR.sexyDuck` files~~
- ~~Separate `ERROR.txt` files~~
- ~~Documents folder error files~~

### Changes:
1. **`get_doc` errors**: Now use `_log_unique_error()` instead of `_write_failure_payload()`
2. **`_handle_job_failure`**: Logs to `error_registry.json` instead of creating separate files
3. **`_emergency_error_log`**: Tries `error_registry.json` first, only creates txt files if completely inaccessible
4. **All error paths**: Consolidated to use `_log_unique_error()` for external error tracking

## Error Registry Integration

The error registry (`error_registry.json`) now captures:
- Enhanced error messages with full diagnostics
- File metadata when available
- Troubleshooting recommendations
- Error classification (COM/OLE, Permission, Corruption, etc.)
- Deduplication by error type (counts occurrences instead of creating duplicates)

## Testing Recommendations

To test the improvements:

1. **ACC Sync Issues**: Test with ACC file that's not fully synced
2. **File Locks**: Test with file open by another user
3. **Permission Issues**: Test with file user doesn't have access to
4. **Corrupted Files**: Test with known corrupted file
5. **Network Issues**: Test with network disconnect during file access

## Future Enhancements

Potential improvements for future iterations:

1. **Retry Logic**: Automatic retry with exponential backoff for transient errors
2. **Health Checks**: Pre-flight checks for Autodesk services
3. **Metrics Collection**: Track error patterns to identify systemic issues
4. **User Notifications**: Push notifications for common fixable issues
5. **Automatic Recovery**: Self-healing for known transient issues

## Related Files

- `revit_remote_server_script.py`: Main implementation
- `error_registry.json`: Centralized error tracking
- Debug logs: Located in `_debug/` directory within RevitSlaveDatabase

## Compatibility

- **IronPython 2.7**: All changes maintain Python 2.7 compatibility
- **Revit API**: Uses only standard Revit API calls
- **pyRevit**: Compatible with pyRevit hosting environment

