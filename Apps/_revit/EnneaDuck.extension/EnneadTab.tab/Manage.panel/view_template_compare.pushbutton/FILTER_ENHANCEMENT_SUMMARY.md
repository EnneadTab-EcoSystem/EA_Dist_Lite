# Enhanced Filter Data Collection for View Template Comparison

## Overview

The view template comparison tool has been enhanced to capture and compare **filter enable status** and **filter visibility status** in addition to the existing graphic override settings. This provides a complete picture of how filters are configured in each view template.

## What Was Enhanced

### 1. Filter Data Collection (`template_data_collector.py`)

**Before:**
- Only captured graphic override settings via `GetFilterOverrides()`
- Filter data structure: `{filter_name: override_details}`

**After:**
- Captures three key filter properties:
  - **Enable Status**: `GetIsFilterEnabled()` - whether the filter is enabled/disabled
  - **Visibility Status**: `GetFilterVisibility()` - whether the filter is visible/hidden  
  - **Graphic Overrides**: `GetFilterOverrides()` - line, pattern, and transparency settings

- Enhanced filter data structure:
```python
{
    'enabled': bool,           # Filter enable status
    'visible': bool,           # Filter visibility status  
    'graphic_overrides': dict  # Graphic override settings
}
```

### 2. Filter Comparison Logic (`template_comparison_engine.py`)

**New Method:** `_compare_filter_data()`
- Compares enable status across templates
- Compares visibility status across templates
- Compares graphic override settings across templates
- Identifies differences in any of these three areas

**New Method:** `_has_filter_differences()`
- Determines if filter configurations differ between templates
- Handles cases where filters are not applied to all templates

### 3. HTML Report Generation (`html_report_generator.py`)

**Enhanced Filter Display:**
- **Enable Status**: Shows ✓ Enabled (green) or ✗ Disabled (red)
- **Visibility Status**: Shows ✓ Visible (green) or ✗ Hidden (red)
- **Graphic Overrides**: Shows detailed override settings

**New Method:** `_create_filter_summary()`
- Creates formatted summaries for the enhanced filter data structure
- Uses color-coded indicators for enable/visibility status
- Includes graphic override details when present

## API Methods Used

Based on the [Revit API documentation](https://www.revitapidocs.com/2021.1/0643b3a4-2f3e-e7ca-9070-a3f2c67b22e9.htm):

1. **`GetIsFilterEnabled(ElementId filterElementId)`** - Returns true if the filter is enabled in the view
2. **`GetFilterVisibility(ElementId filterElementId)`** - Returns the visibility state of the filter
3. **`GetFilterOverrides(ElementId filterElementId)`** - Returns the graphic override settings

## Benefits

1. **Complete Filter Analysis**: Now captures all three aspects of filter configuration
2. **Better Comparison**: Identifies differences in enable/visibility status that were previously missed
3. **Improved Reporting**: Clear visual indicators for filter status in HTML reports
4. **Enhanced Debugging**: Better understanding of filter behavior across templates

## Usage

The enhanced functionality is automatically available when running the view template comparison tool. No changes to the user interface are required - the tool will now capture and display the additional filter information.

## Example Output

In the HTML report, filter entries now show:
```
✓ Enabled
✓ Visible  
Graphic Overrides:
  Lines: Override...
  Patterns: Override...
  Transparency: 50%
```

Or for disabled/hidden filters:
```
✗ Disabled
✗ Hidden
```

## Compatibility

- Works with Revit 2021.1 and later (when `GetIsFilterEnabled` was introduced)
- Backward compatible with existing comparison logic
- No breaking changes to existing functionality
