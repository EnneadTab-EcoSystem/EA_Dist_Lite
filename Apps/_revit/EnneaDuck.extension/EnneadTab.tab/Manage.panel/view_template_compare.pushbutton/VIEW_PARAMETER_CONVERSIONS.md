# View Parameter Integer-to-Text Conversions

## Overview

The view template comparison tool now includes comprehensive integer-to-text conversions for common view parameters. This enhancement makes the comparison reports much more readable by converting numeric values to human-readable text.

## New Parameter Conversions Added

### **1. Display Model**
- **Parameter Name**: "Display Model"
- **Integer Values**:
  - `0` → "Normal"
  - `1` → "Halftone"
  - `2` → "Do not display"
  - Other values → "Unknown (value)"

### **2. Model Display**
- **Parameter Name**: "Model Display"
- **Integer Values**:
  - `0` → "Wireframe"
  - `1` → "Hidden Line"
  - `2` → "Shaded"
  - `3` → "Consistent Colors"
  - `4` → "Textures"
  - `5` → "Realistic"
  - Other values → "Unknown (value)"

### **3. Far Clipping**
- **Parameter Name**: "Far Clipping"
- **Integer Values**:
  - `0` → "No Clipping"
  - `1` → "Clip With Lines"
  - `2` → "Clip Without Lines"
  - Other values → "Unknown (value)"

### **4. Show Hidden Lines**
- **Parameter Name**: "Show Hidden Lines"
- **Integer Values**:
  - `0` → "Hide"
  - `1` → "Show"
  - Other values → "Unknown (value)"

### **5. Sun Path**
- **Parameter Name**: "Sun Path"
- **Integer Values**:
  - `0` → "Hide"
  - `1` → "Show"
  - Other values → "Unknown (value)"

### **6. Parts Visibility**
- **Parameter Name**: "Parts Visibility"
- **Integer Values**:
  - `0` → "Show Original"
  - `1` → "Show Parts"
  - `2` → "Show Both"
  - Other values → "Unknown (value)"

## Previously Supported Conversions

### **7. Detail Level**
- **Parameter Name**: "Detail Level"
- **Integer Values**:
  - `0` → "Coarse"
  - `1` → "Medium"
  - `2` → "Fine"
  - Other values → "Unknown (value)"

### **8. Discipline**
- **Parameter Name**: "Discipline"
- **Integer Values**:
  - `0` → "Architectural"
  - `1` → "Structural"
  - `2` → "Mechanical"
  - `3` → "Electrical"
  - `4` → "Plumbing"
  - `5` → "Coordination"
  - Other values → "Unknown (value)"

### **9. Color Scheme Location**
- **Parameter Name**: "Color Scheme Location"
- **Integer Values**:
  - `0` → "Foreground"
  - `1` → "Background"
  - Other values → "Unknown (value)"

### **10. Yes/No Parameters**
- **Parameter Type**: `DB.ParameterType.YesNo`
- **Integer Values**:
  - `0` → "No"
  - `1` → "Yes"
  - Other values → "Unknown (value)"

## Implementation Details

### **Conversion Map**
The conversions are implemented using a dictionary-based approach in the `_apply_special_integer_conversions` method:

```python
conversion_map = {
    'detail level': self._convert_detail_level_to_text,
    'discipline': self._convert_discipline_to_text,
    'color scheme location': self._convert_color_scheme_location_to_text,
    'display model': self._convert_display_model_to_text,
    'model display': self._convert_model_display_to_text,
    'far clipping': self._convert_far_clipping_to_text,
    'show hidden lines': self._convert_show_hidden_lines_to_text,
    'sun path': self._convert_sun_path_to_text,
    'parts visibility': self._convert_parts_visibility_to_text
}
```

### **Parameter Detection**
Parameters are detected using case-insensitive string matching:
- The parameter name is converted to lowercase
- Keywords are searched within the parameter name
- Multiple keywords can match a single parameter (e.g., "show hidden lines")

### **Error Handling**
Each conversion method includes comprehensive error handling:
- Try-catch blocks around conversion logic
- Detailed error logging using `ERROR_HANDLE.print_note`
- Fallback to "Error: [value]" for conversion failures
- "Unknown (value)" for unrecognized integer values

## Example Output

### **Before Conversion**:
```json
{
  "view_parameters": {
    "Display Model": "0",
    "Far Clipping": "2",
    "Show Hidden Lines": "1",
    "Sun Path": "0",
    "Parts Visibility": "1",
    "Detail Level": "1",
    "Discipline": "0"
  }
}
```

### **After Conversion**:
```json
{
  "view_parameters": {
    "Display Model": "Normal",
    "Far Clipping": "Clip Without Lines",
    "Show Hidden Lines": "Show",
    "Sun Path": "Hide",
    "Parts Visibility": "Show Parts",
    "Detail Level": "Medium",
    "Discipline": "Architectural"
  }
}
```

## Benefits

### **1. Improved Readability**
- Users can immediately understand parameter values
- No need to look up numeric codes
- Clear, descriptive text instead of cryptic numbers

### **2. Better Comparison Reports**
- HTML reports show meaningful parameter differences
- Easier to identify important changes between templates
- More professional and user-friendly output

### **3. Enhanced Debugging**
- Debug logging includes all relevant parameter types
- Better troubleshooting capabilities
- Clear error messages for conversion failures

### **4. Extensible Design**
- Easy to add new parameter types
- Consistent conversion pattern
- Maintainable code structure

## Adding New Parameter Types

To add a new parameter conversion:

1. **Add to Conversion Map**:
```python
conversion_map = {
    # ... existing conversions ...
    'new parameter': self._convert_new_parameter_to_text
}
```

2. **Create Conversion Method**:
```python
def _convert_new_parameter_to_text(self, value):
    """Convert new parameter to readable text."""
    try:
        if value == 0:
            return "Option 1"
        elif value == 1:
            return "Option 2"
        else:
            return "Unknown ({})".format(value)
    except Exception as e:
        ERROR_HANDLE.print_note("Error converting new parameter: {}".format(str(e)))
        return "Error: {}".format(value)
```

3. **Add Debug Keywords** (if needed):
```python
debug_keywords = ['detail', 'discipline', 'color', 'scheme', 'location', 'new', 'parameter']
```

## Technical Notes

- **Case-Insensitive Matching**: Parameter names are matched regardless of case
- **Keyword-Based Detection**: Uses substring matching for flexible parameter identification
- **Error Resilience**: Comprehensive error handling prevents crashes
- **Performance Optimized**: Only processes parameters that need conversion
- **Backward Compatible**: Existing functionality preserved

## Future Enhancements

Potential areas for future improvement:
- **More Parameter Types**: Additional view parameters that use integer values
- **Dynamic Conversion**: Loading conversion rules from configuration files
- **Localization**: Support for multiple languages in conversion text
- **Custom Conversions**: User-defined conversion rules for project-specific parameters
