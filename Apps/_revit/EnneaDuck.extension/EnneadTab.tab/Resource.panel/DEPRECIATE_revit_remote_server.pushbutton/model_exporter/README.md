# Model Exporter Module

## Overview

The Model Exporter is a standalone, resilient export system for Revit models integrated with RevitSlave-2.0. It exports the first 10 sheets from a print-set (or fallback to first 10 sheets) to JPG, PDF, and DWG formats with comprehensive error handling and reporting.

## Key Features

### 1. **Complete Error Isolation**
- Health metrics run first and complete before exports
- Export failures NEVER affect health metric results
- Separate `export_data` field in output for export results
- Status field reflects health metrics only

### 2. **Fixed Export Settings**
All exports use the same hardcoded settings (no configuration needed):
- **Images**: 150 DPI, 1920px width, JPG format
- **PDFs**: Individual per sheet (not combined), standard settings
- **DWGs**: AutoCAD 2018 format, AIA layer standard
- **Max Sheets**: 10 (from print-set or fallback)

### 3. **Robust Error Handling**
- **Error Classification**: Timeout, access denied, file locked, memory error, API error, validation failed
- **Retry Logic**: Up to 2 retries for transient failures (file locked, memory errors)
- **Validation**: Checks file existence and minimum size after export
- **Cleanup**: Removes corrupt/partial files on failure
- **Timeout Tracking**: Warnings for exports exceeding thresholds (60s/image, 120s/PDF, 180s/DWG)

### 4. **Sequential Processing**
- All exports are sequential (one sheet at a time)
- Revit API does not support batch/parallel exports
- Periodic garbage collection every 5 sheets to prevent memory buildup
- Each sheet exports to all 3 formats before moving to next sheet

### 5. **Detailed Reporting**
Per-sheet success/failure tracking:
```json
{
  "export_status": "completed",
  "summary": {
    "total_sheets": 10,
    "successful_sheets": 8,
    "failed_sheets": 1,
    "partial_failures": 1
  },
  "sheets": [
    {
      "sheet_name": "First Floor Plan",
      "sheet_number": "A101",
      "exports": {
        "image": {"status": "success", "path": "...", "duration": 2.3},
        "pdf": {"status": "success", "path": "...", "duration": 4.1},
        "dwg": {"status": "failed", "error": "...", "error_class": "timeout"}
      },
      "overall_status": "partial"
    }
  ],
  "performance": {
    "total_duration_seconds": 125.4,
    "average_time_per_sheet": 12.5
  }
}
```

### 6. **Smart Sheet Selection**
1. **Primary**: First 10 sheets from print-set
2. **Fallback**: First 10 sheets from document (if print-set unavailable)
3. **Error Handling**: Clear messages if no sheets available

## Module Structure

```
model_exporter/
├── __init__.py           # Main ModelExporter class
├── export_helpers.py     # Validation and utility functions
├── image_exporter.py     # JPG export functionality
├── pdf_exporter.py       # PDF export functionality
├── dwg_exporter.py       # DWG export functionality
└── README.md            # This file
```

## Integration with RevitSlave-2.0

### Job File Configuration

To enable exports, add `export_settings` to the job file:

```json
{
  "job_id": "job_001",
  "model_path": "C:\\path\\to\\model.rvt",
  "export_settings": {
    "enabled": true
  }
}
```

If `export_settings.enabled` is `false` or not present, exports are skipped.

### Output Structure

The output file (`*.sexyDuck`) now has two separate data sections:

```json
{
  "job_metadata": {
    "job_id": "...",
    "hub_name": "...",
    "project_name": "...",
    "model_name": "...",
    "timestamp": "..."
  },
  "health_metric_result": {
    // Health metrics data (unchanged)
  },
  "export_data": {
    // Export metadata and results
    // null if exports disabled or failed to initialize
  },
  "status": "completed"
}
```

### Error Isolation Rules

1. **Health metrics always run first** - complete before exports start
2. **Export failures are caught** - wrapped in try/except at top level
3. **Status reflects health metrics only** - not affected by export failures
4. **Export errors logged separately** - in `export_data` field
5. **Output always written** - even if exports completely fail
6. **No exception propagation** - from exports to health metrics layer

## Usage Example

```python
from model_exporter import ModelExporter

# Create exporter instance
exporter = ModelExporter(doc, output_base_path)

# Run all exports
report = exporter.export_all()

# Check results
print("Status: {}".format(report["export_status"]))
print("Successful: {}/{}".format(
    report["summary"]["successful_sheets"],
    report["summary"]["total_sheets"]
))
```

## Output Directory Structure

```
task_output_dir/
└── exports/
    ├── images/
    │   ├── A101_First_Floor_Plan.jpg
    │   ├── A102_Second_Floor_Plan.jpg
    │   └── ...
    ├── pdfs/
    │   ├── A101_First_Floor_Plan.pdf
    │   ├── A102_Second_Floor_Plan.pdf
    │   └── ...
    └── dwgs/
        ├── A101_First_Floor_Plan.dwg
        ├── A102_Second_Floor_Plan.dwg
        └── ...
```

## Error Classification

The system classifies errors into categories for better debugging:

- **`timeout`**: Export exceeded time threshold
- **`access_denied`**: Permission issues
- **`file_locked`**: File in use by another process (retryable)
- **`memory_error`**: Out of memory (retryable)
- **`revit_api_error`**: Generic Revit API errors
- **`validation_failed`**: File created but failed validation
- **`no_printset`**: Print-set not available
- **`no_sheets`**: No sheets found in document

## Performance Characteristics

Typical export times (per sheet):
- **Image (JPG)**: 2-5 seconds
- **PDF**: 4-8 seconds
- **DWG**: 10-20 seconds

Total time for 10 sheets: **~2-5 minutes**

Memory: Periodic garbage collection every 5 sheets prevents buildup.

## Troubleshooting

### Export Failed - No Sheets Available

**Cause**: Print-set is empty and fallback found no sheets  
**Solution**: Ensure document has viewable sheets (not placeholders)

### Validation Failed - File Too Small

**Cause**: Export completed but file is corrupt/empty  
**Solution**: Check Revit version compatibility, sheet content, and available memory

### File Locked Error

**Cause**: Previous export hasn't released file handle  
**Solution**: System automatically retries (up to 2 times with 2s delay)

### Memory Error

**Cause**: Large complex sheets exhausting available memory  
**Solution**: System automatically retries; consider reducing sheet complexity

### Export Succeeds But Health Metrics Fail

**Cause**: These are isolated - check `health_metric_result` separately  
**Solution**: Health metrics failure is independent; exports still valid

## Future Enhancements

Potential improvements (not currently implemented):
- Resume capability for interrupted exports
- Export queue prioritization (e.g., cover sheet first)
- Configurable settings per project
- Export preview thumbnails
- Format-specific validation (PDF page count, DWG layer validation)

## Testing Recommendations

1. Test with empty print-set (should fallback to first N sheets)
2. Test with projects >10 sheets (should limit to 10)
3. Test with large complex sheets (memory pressure)
4. Test with locked files (retry logic)
5. Test error isolation (force export failure, verify health metrics succeed)
6. Test timeout warnings (very complex sheets)

## Notes

- **IronPython 2.7 Compatible**: Uses Python 2.7 syntax throughout
- **No External Dependencies**: Only uses Revit API and Python stdlib
- **No EnneadTab Dependency**: Standalone module like health_metric
- **Thread-Safe**: No threading used (Revit API limitation)
- **Cross-Version**: Works with all Revit versions supported by RevitSlave-2.0

