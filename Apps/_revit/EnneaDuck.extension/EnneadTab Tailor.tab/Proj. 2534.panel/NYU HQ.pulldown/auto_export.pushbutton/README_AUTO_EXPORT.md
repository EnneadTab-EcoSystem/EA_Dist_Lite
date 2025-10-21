# NYU HQ Auto Export - User Guide

## Overview
This tool automatically opens the NYU HQ Revit model, exports sheets to PDF/DWG/JPG formats, and sends email notifications when complete.

## Features
- ✅ **Automated Document Opening**: Opens cloud model detached with worksets preserved
- ✅ **Smart Sheet Filtering**: Exports only sheets marked for publishing
- ✅ **Multi-Format Export**: PDF, DWG, JPG in one run
- ✅ **Organized Output**: Weekly folders with dated subfolders
- ✅ **Email Notifications**: Automatic email with export summary
- ✅ **Lock Mechanism**: Prevents multiple instances from running
- ✅ **Detailed Logging**: Heartbeat log tracks every step

## How to Use

### Step 1: Mark Sheets for Export in Revit
1. Open the NYU HQ model in Revit
2. Find the sheets you want to export
3. Set the parameter `Sheet_$Issue_AutoPublish` to any non-empty value:
   - Use "X" or "●" or any character
   - Leave empty or "None" for sheets you DON'T want to export

### Step 2: Run the Auto Export
1. Double-click `auto_export.bat` or run from command line
2. Revit will launch automatically (no user interaction needed)
3. Wait for the process to complete (~1-2 minutes)
4. Check the output folder for exported files

### Step 3: Verify Results
- **Output Location**: `C:\Users\%USERNAME%\DC\ACCDocs\Ennead Architects LLP\2534_NYUL Long Island HQ\Project Files\[EXTERNAL] File Exchange Hub\B-10_Architecture_EA\EA Auto Publish\YYYY-MM-DD\`
- **Heartbeat Log**: `heartbeat\heartbeat_YYYYMMDD.log`
- **Email**: Sent to configured recipients if files were exported

## Configuration

### Filter Parameter
- **Parameter Name**: `Sheet_$Issue_AutoPublish`
- **Location**: `export_logic.py` line 17
- **Valid Values**: Any non-empty string (except "None")
- **Empty Values**: "" (empty string) or "None" (case-insensitive)

### DWG Export Setting
- **Setting Name**: `to NYU dwg`
- **Location**: `export_logic.py` line 18
- **Note**: Must exist in the Revit model's DWG export settings

### PDF Color Control
- **Parameter**: `Print_In_Color`
- **Location**: `export_logic.py` line 19
- **Behavior**: Non-empty value = color, empty = grayscale

### Filename Format
- **Format**: `{PIM_Number}-{SheetNumber}_{SheetName}.{extension}`
- **Example**: `2534-A-100_Site Plan.pdf`

### Email Recipients
- **Configure**: Edit `post_export_logic.py` lines 14-18
- **Current Recipients**:
  - `project.manager@ennead.com`
  - `architect.lead@ennead.com`
  - `client.contact@nyu.edu`

## Output Structure
```
EA Auto Publish/
├── 2025-10-21/
│   ├── pdf/
│   │   ├── 2534-A-100_Site Plan.pdf
│   │   └── 2534-A-101_Floor Plan.pdf
│   ├── dwg/
│   │   ├── 2534-A-100_Site Plan.dwg
│   │   └── 2534-A-101_Floor Plan.dwg
│   └── jpg/
│       ├── 2534-A-100_Site Plan.jpg
│       └── 2534-A-101_Floor Plan.jpg
└── 2025-10-22/
    └── ...
```

## Troubleshooting

### No Sheets Exported
- **Cause**: All sheets have `Sheet_$Issue_AutoPublish` = empty or "None"
- **Solution**: Set the parameter to "X" or any other value for sheets to export

### Lock File Error
- **Cause**: Previous instance didn't clean up properly
- **Solution**: Delete `auto_export.lock` file manually

### DWG Export Failed
- **Cause**: DWG export setting "to NYU dwg" doesn't exist
- **Solution**: Create the export setting in Revit or update `DWG_SETTING_NAME` in `export_logic.py`

### Email Not Sent
- **Cause 1**: No files exported (0 successful exports)
- **Cause 2**: EnneadTab email service error
- **Solution**: Check heartbeat log for details

## Technical Details

### Files
- `auto_export_script.py`: Main orchestration script
- `export_logic.py`: Core export functionality
- `post_export_logic.py`: Email notifications
- `auto_export.bat`: Launch script with lock mechanism

### Model Configuration
- **Model**: `2534_A_EA_NYU HQ_Shell`
- **Project GUID**: `51bdf270-659d-4299-9fe0-0eb024873dc2`
- **Model GUID**: `e8392a95-51dd-49b1-ad35-d2b66e3a8cbf`
- **Region**: US
- **Revit Version**: 2026

### Logging
- **Heartbeat Log**: Step-by-step execution tracking
- **Location**: `heartbeat/heartbeat_YYYYMMDD.log`
- **Format**: `[timestamp] [step] [status] message`

## Support
For issues or questions, contact the EnneadTab development team.

---

**Last Updated**: 2025-10-21
**Version**: 1.0 (Production Ready)

