# SparcHealth

Automated health check system for Sparc project models.

## Overview

SparcHealth is an automated tool that:
1. Opens each Sparc project model sequentially
2. Collects health metrics (currently: timestamp and document title)
3. Saves results to OneDrive Dump folder
4. Closes Revit cleanly
5. Processes the next model

## Architecture

- **CPython Orchestrator** (`orchestrator.py`): Runs outside Revit, coordinates the health check process
- **IronPython Script** (`revit_health_check_script.py`): Runs inside Revit to perform actual health checks
- **Config Loader** (`config_loader.py`): Shared utility for loading configuration
- **Configuration** (`config.json`): Single config file with all Sparc models

## How It Works

1. **User clicks SparcHealth button** in Revit → Launches `SparcHealth_script.py`
2. **Launcher script** executes `run_SparcHealth.bat` in new console window
3. **Batch file** activates `.venv` Python and runs `orchestrator.py`
4. **Orchestrator**:
   - Loads all models from `config.json`
   - Validates configuration
   - For each model:
     - Writes payload file with model info
     - Launches Revit via `pyrevit run revit_health_check_script.py`
     - Monitors progress via status file and heartbeat logs
     - Waits for completion (20 min timeout, activity-based)
     - Cleans up Revit processes
5. **Revit script**:
   - Reads payload to get current model info
   - Opens model (detached, closed worksets, no audit)
   - Collects health metrics
   - Writes JSON output to OneDrive Dump folder
   - Updates status file
   - Closes Revit
6. **Process repeats** for next model
7. **Summary logged** when all models complete

## Configuration

Edit `config.json` to add/remove models:

```json
{
  "models": [
    {
      "name": "SPARC_A_EA_CUNY_Building",
      "model_guid": "0be7efb0-d2a0-43bd-8fa0-67be15d54f94",
      "project_guid": "d92aaa44-5ca0-46fb-9426-ce3d64ebece9",
      "region": "US",
      "revit_version": "2024"
    }
  ]
}
```

## Output Location

Health check results are saved to:
```
C:\Users\{username}\OneDrive - Ennead Architects\Documents\EnneadTab Ecosystem\Dump\SparcHealth\
```

Each file is named: `{model_name}_{timestamp}.json`

Example: `SPARC_A_EA_CUNY_Building_20251104_143022.json`

## Output Format

```json
{
  "job_id": "20251104_143022_SPARC_A_EA_CUNY_Building",
  "timestamp": "2025-11-04 14:32:15",
  "model_name": "SPARC_A_EA_CUNY_Building",
  "doc_title": "SPARC_A_EA_CUNY_Building",
  "project_name": "2412_SPARC",
  "revit_version": "2024",
  "status": "success"
}
```

## Logs

- **Orchestrator logs**: `orchestrator_logs/orchestrator_{timestamp}.log`
- **Heartbeat logs**: `heartbeat/heartbeat_{date}.log` and `heartbeat/orchestrator_heartbeat_{date}.log`
- **Status file**: `current_job_status.json` (updated in real-time)

## Timeout & Error Handling

- **Activity-based timeout**: 20 minutes (configurable in `config.json`)
- Timeout only triggers if NO progress is detected (no status/heartbeat updates)
- Long-running jobs can continue as long as they make progress
- Process cleanup between jobs (kills Revit.exe and RevitWorker.exe only)
- Continues to next model even if one fails

## Future Enhancements

The current implementation collects placeholder metrics (timestamp + doc title).

Future health metrics to add:
- Element counts (walls, doors, windows, etc.)
- Warning counts and types
- View counts (sheets, schedules, 3D views)
- Workset information
- File size
- Link status
- Family counts
- Annotation counts
- Performance metrics

## File Structure

```
SparcHealth.pushbutton/
├── SparcHealth_script.py       # pyRevit button launcher
├── run_SparcHealth.bat         # Batch file to activate .venv and run orchestrator
├── orchestrator.py             # CPython orchestrator (main coordinator)
├── revit_health_check_script.py # IronPython script (runs in Revit)
├── config_loader.py            # Configuration loader utility
├── config.json                 # Configuration with all models
├── icon.png                    # Button icon
├── README.md                   # This file
├── orchestrator_logs/          # Orchestrator execution logs (created at runtime)
├── heartbeat/                  # Heartbeat logs (created at runtime)
├── current_job_payload.json    # Current job info (created at runtime)
└── current_job_status.json     # Current job status (created at runtime)
```

## Troubleshooting

**Button doesn't appear:**
- Reload pyRevit extensions
- Check that folder is named `SparcHealth.pushbutton`
- Check that `SparcHealth_script.py` exists

**Orchestrator doesn't start:**
- Check `.venv` Python environment exists at workspace root
- Verify pyRevit CLI is installed and in PATH
- Check orchestrator logs for errors

**Model won't open:**
- Verify GUIDs are correct in `config.json`
- Check Revit version matches
- Check ACC/BIM360 connectivity
- Review heartbeat logs for error messages

**Health check times out:**
- Check heartbeat logs for last activity
- Increase timeout in `config.json` → `orchestrator.timeout_minutes`
- Check if Revit is stuck on a dialog

**Output not created:**
- Verify output path exists or can be created
- Check OneDrive is syncing
- Review status file for errors

## Based On

This implementation is modeled after the AutoExporter system with similar architecture:
- `Apps/_revit/EnneaDuck.extension/EnneadTab.tab/ACE.panel/AutoExporter.pushbutton/`

Key differences:
- Single config file (vs. multiple config files)
- Processes models array (vs. config files array)
- Health checks only (vs. PDF/DWG exports)
- Opens with closed worksets (vs. all worksets)
- No audit on open (faster)

