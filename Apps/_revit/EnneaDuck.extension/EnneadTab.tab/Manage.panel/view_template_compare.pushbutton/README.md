# View Template Comparison Tool

## Overview

The View Template Comparison tool is a comprehensive Revit utility that allows users to compare multiple view templates and identify differences in their settings. It generates an interactive HTML report highlighting inconsistencies and potential issues.

## Features

### **Comprehensive Comparison**
- **Category Overrides**: Line weight, color, patterns, halftone, transparency
- **Category Visibility**: On/Off settings for all categories and subcategories
- **Workset Visibility**: User workset visibility settings
- **View Parameters**: Controlled vs uncontrolled parameter analysis
- **Filter Usage**: Applied filters and their graphic overrides

### **Danger Detection**
- **Uncontrolled Parameters**: Identifies parameters not marked as included in templates
- **Visual Warnings**: Dark orange highlighting for uncontrolled parameters
- **Risk Assessment**: Clear warnings about potential inconsistencies

### **Interactive HTML Report**
- **Collapsible Sections**: Organized by comparison type
- **Color-Coded Results**: Visual indicators for differences
- **Summary Statistics**: Quick overview of findings
- **Responsive Design**: Easy to read and navigate

## Key Improvements

### 1. **Enhanced Error Handling**
- Replaced silent try-catch blocks with `ERROR_HANDLE.print_note()`
- Detailed error logging with specific context
- Pre-validation checks for category capabilities
- Summary reporting of skipped items

### 2. **Uncontrolled Parameter Priority**
- **Priority Detection**: Uncontrolled parameters take precedence over normal comparison
- **Visual Highlighting**: Dark orange background (`#FF8C00`) for uncontrolled items
- **Consistent Display**: All templates show "UNCONTROLLED" when any template has uncontrolled parameters

### 3. **Improved Data Collection**
- **Sorted Categories**: Alphabetical sorting of categories and subcategories
- **Pattern Names**: Readable pattern names instead of IDs
- **Color Formatting**: RGB color strings for better readability
- **Comprehensive Coverage**: All Revit categories and subcategories

### 4. **Modular Code Structure**
- **Simple Entry Point**: Clean 238-line PyRevit script
- **Modular Components**: Complex logic separated into focused modules
- **Clear Separation**: Data collection, comparison, and report generation
- **Reusable Components**: Each module can be used independently

## Usage

### 1. **Launch the Tool**
- Navigate to **EnneadTab → Manage → View Template Compare**
- The tool will prompt for template selection

### 2. **Select Templates**
- Choose at least 2 view templates to compare
- Multiple selection is supported
- Templates are validated before processing

### 3. **Review Results**
- HTML report opens automatically
- Console displays summary and warnings
- Uncontrolled parameters are highlighted in dark orange

## Technical Details

### **Comparison Logic Priority**
1. **First**: Check if parameter is uncontrolled in any template
2. **If uncontrolled**: Mark as "UNCONTROLLED" for all templates (dark orange highlight)
3. **If controlled**: Perform normal value comparison

### **Error Handling Strategy**
- **Pre-validation**: Check category capabilities before operations
- **Specific Logging**: Include category/parameter names in error messages
- **Summary Reporting**: Show counts and examples of skipped items
- **Graceful Degradation**: Continue processing even with errors

### **Data Structure**
```python
comparison_data = {
    'template_name': {
        'name': str,
        'category_overrides': dict,
        'category_visibility': dict,
        'workset_visibility': dict,
        'view_parameters': list,  # controlled
        'uncontrolled_parameters': list,  # uncontrolled
        'filters': dict
    }
}
```

## Output Examples

### **Console Output**
```
# View Template Comparison

## Analyzing Templates...

## Summary
**Templates compared:** 3
**Total differences found:** 15
**Processing time:** 2.34 seconds
**Report saved to:** C:\Users\...\ViewTemplate_Comparison_20241201_143022.html

## DANGER: Uncontrolled Parameters Found
**5 parameters are uncontrolled across templates.**
These parameters are NOT marked as included when the view is used as a template.
This can cause **inconsistent behavior** across views using the same template.
**Review these parameters in the HTML report and consider controlling them if needed.**
```

### **HTML Report Features**
- **Header**: Generation timestamp and template list
- **Summary Section**: Statistics and overview
- **Collapsible Sections**: Each comparison type in its own section
- **Color Coding**:
  - **Green**: Same values across templates
  - **Yellow**: Different values
  - **Dark Orange**: Uncontrolled parameters
  - **Red**: Danger warnings

## Benefits

### **For Users**
- **Quick Identification**: Spot inconsistencies across templates
- **Risk Assessment**: Identify dangerous uncontrolled parameters
- **Visual Clarity**: Color-coded results for easy interpretation
- **Comprehensive Coverage**: All template settings are analyzed

### **For Developers**
- **Modular Architecture**: Clean separation of concerns across 4 focused modules
- **Maintainable Code**: Each module has single responsibility and clear interfaces
- **Robust Error Handling**: No silent failures, detailed logging with `ERROR_HANDLE.print_note()`
- **Extensible Design**: Easy to add new comparison types and features
- **Well Documented**: Comprehensive docstrings, comments, and architecture documentation
- **Reusable Components**: Individual modules can be used independently
- **Easy Debugging**: Issues can be isolated to specific modules

## File Structure

```
view_template_compare.pushbutton/
├── view_template_compare_script.py    # Main entry point (PyRevit script)
├── template_data_collector.py         # Data collection module
├── template_comparison_engine.py      # Comparison logic module
├── html_report_generator.py           # HTML report generation module
├── view_template_compare_script.py    # Main entry point (PyRevit script)
├── icon.png                           # Button icon
├── README.md                          # This documentation
└── MODULAR_ARCHITECTURE.md            # Modular architecture documentation
```

## Dependencies

- **PyRevit**: Forms and script utilities
- **EnneadTab**: Error handling, logging, notifications
- **Revit API**: View templates, categories, worksets
- **Standard Library**: File I/O, datetime, HTML generation

## Future Enhancements

- **Export Options**: CSV, Excel, or PDF formats
- **Template Synchronization**: Auto-fix inconsistencies
- **Batch Processing**: Compare multiple template sets
- **Custom Filters**: Focus on specific comparison types
- **Performance Optimization**: Parallel processing for large datasets 