# Color Scheme Location Parameter Enhancement

## Overview

The view template comparison tool has been enhanced to convert **Color Scheme Location** parameter values from numeric codes to human-readable text, making the comparison reports more user-friendly and easier to understand.

## What Was Enhanced

### Color Scheme Location Values

The Color Scheme Location parameter controls whether color schemes are displayed in the background or foreground of views:

- **"0"** = **Foreground** - Color schemes appear in front of other elements
- **"1"** = **Background** - Color schemes appear behind other elements

## Implementation

### 1. Parameter Value Conversion (`template_data_collector.py`)

**New Method:** `_convert_color_scheme_location_to_text(location_value)`
- Converts integer values to readable text
- Handles edge cases and errors gracefully
- Integrated into the existing parameter value conversion pipeline

**Enhanced Method:** `_get_parameter_value_as_string(param)`
- Added detection for "Color Scheme Location" parameter
- Automatically applies text conversion when the parameter is found
- Maintains existing functionality for other parameters

## Code Implementation

```python
def _convert_color_scheme_location_to_text(self, location_value):
    """
    Convert Color Scheme Location value to readable text.
    
    Args:
        location_value: Integer value (0 or 1)
        
    Returns:
        str: Readable location text
    """
    try:
        if location_value == 0:
            return "Foreground"
        elif location_value == 1:
            return "Background"
        else:
            return "Unknown ({})".format(location_value)
    except Exception as e:
        ERROR_HANDLE.print_note("Error converting color scheme location to text: {}".format(str(e)))
        return "Error: {}".format(location_value)
```

## Benefits

1. **Improved Readability**: Users see "Foreground" and "Background" instead of "0" and "1"
2. **Better Understanding**: Clear indication of what the parameter setting means
3. **Consistent Formatting**: Matches other parameter conversions (Detail Level, Discipline, etc.)
4. **Error Handling**: Graceful handling of unexpected values

## Example Output

**Before Enhancement:**
```
View Parameters Differences:
- Color Scheme Location: Template1="0", Template2="1"
```

**After Enhancement:**
```
View Parameters Differences:
- Color Scheme Location: Template1="Foreground", Template2="Background"
```

## Impact on Comparison

This enhancement affects:
- **View Parameters Comparison**: Color Scheme Location differences are now more readable
- **Comprehensive Comparison Tables**: Shows text values instead of numeric codes
- **HTML Reports**: Better user experience with clear parameter descriptions
- **JSON Export**: Maintains both numeric and text values for programmatic access

## Technical Details

- **Parameter Detection**: Uses case-insensitive string matching for "Color Scheme Location"
- **Value Mapping**: 0 → "Foreground", 1 → "Background"
- **Error Handling**: Returns "Unknown (value)" for unexpected values
- **Integration**: Seamlessly integrated with existing parameter conversion system

## Compatibility

- No breaking changes to existing functionality
- Maintains backward compatibility with numeric values
- Works with all existing comparison features
- Follows the same pattern as other parameter conversions
