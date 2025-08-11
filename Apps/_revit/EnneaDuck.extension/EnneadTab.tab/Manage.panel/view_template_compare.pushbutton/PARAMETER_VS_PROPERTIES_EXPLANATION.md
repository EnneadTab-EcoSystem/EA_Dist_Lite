# View Parameters vs View Properties: Detail Level and Discipline

## Overview

The view template comparison tool collects data in two different ways, which can result in different representations of the same information (Detail Level and Discipline) appearing in `view_parameters` vs `view_properties`.

## Key Differences

### **1. `view_parameters` Collection**
- **Method**: `get_view_parameters(template)`
- **Source**: `template.Parameters` (all view parameters)
- **Processing**: Each parameter is processed through `_get_parameter_value_as_string()`
- **Conversion**: Relies on parameter name detection for text conversion

### **2. `view_properties` Collection**
- **Method**: `_get_view_properties(template)`
- **Source**: Direct view object properties (`template.DetailLevel`, `template.Discipline`)
- **Processing**: Direct access to view properties with immediate conversion
- **Conversion**: Always converts to text using dedicated conversion methods

## Why the Difference Occurs

### **Parameter Name Detection Issue**

The `view_parameters` method relies on detecting parameter names to apply text conversion:

```python
# In _get_parameter_value_as_string()
if param_name and ("Detail Level" in param_name or "detail level" in param_name.lower()):
    return self._convert_detail_level_to_text(int_value)

if param_name and ("Discipline" in param_name or "discipline" in param_name.lower()):
    return self._convert_discipline_to_text(int_value)
```

**Problem**: The actual parameter names might not be exactly "Detail Level" or "Discipline". They could be:
- "View Detail Level"
- "View Discipline" 
- "Detail Level"
- "Discipline"
- Or other variations

### **Direct Property Access**

The `view_properties` method accesses these values directly:

```python
# In _get_view_properties()
properties['overall_detail_level'] = self._convert_detail_level_to_text(template.DetailLevel)
properties['discipline'] = self._convert_discipline_to_text(template.Discipline)
```

This always works because it bypasses parameter name detection entirely.

## Enhancement Made

### **Improved Parameter Detection**

I've enhanced the parameter detection logic to be more flexible:

1. **Case-Insensitive Matching**: Now checks both "Detail Level" and "detail level"
2. **Debug Logging**: Added temporary debug output to identify actual parameter names
3. **Robust Detection**: Uses `.lower()` and `.find()` for better matching

### **Debug Output**

The enhanced code now logs parameter names that contain "detail" or "discipline" to help identify the exact parameter names:

```python
# Debug: Log parameter names for troubleshooting
if param_name and (param_name.lower().find('detail') >= 0 or param_name.lower().find('discipline') >= 0):
    ERROR_HANDLE.print_note("DEBUG: Found parameter '{}' with value {} (type: {})".format(
        param_name, int_value, param.StorageType
    ))
```

## Expected Behavior After Enhancement

### **Before Enhancement:**
- `view_parameters`: Detail Level = "0", Discipline = "1" (numeric values)
- `view_properties`: Detail Level = "Coarse", Discipline = "Architectural" (text values)

### **After Enhancement:**
- `view_parameters`: Detail Level = "Coarse", Discipline = "Architectural" (text values)
- `view_properties`: Detail Level = "Coarse", Discipline = "Architectural" (text values)

## Why Both Methods Exist

1. **`view_parameters`**: Captures all template-controlled parameters, including custom parameters
2. **`view_properties`**: Captures specific view properties that may not be available as parameters

## Recommendations

1. **Use Debug Output**: Run the tool to see the actual parameter names in the logs
2. **Verify Conversion**: Check if Detail Level and Discipline now appear as text in both sections
3. **Remove Debug Code**: Once parameter names are identified, the debug logging can be removed

## Technical Notes

- The debug logging will help identify the exact parameter names used by Revit
- The enhanced detection should catch most variations of parameter naming
- Both methods provide valuable information and should be maintained
