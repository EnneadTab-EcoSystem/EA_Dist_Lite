# Output Format Comparison: RevitSlave3 vs. SparcHealth

## Current SparcHealth Format ❌

### Directory Structure
```
C:\Users\{username}\Documents\EnneadTab Ecosystem\Dump\SparcHealth\
├── SPARC_A_EA_CUNY_Building_20251104_130218.json
├── SPARC_A_EA_Shell_20251104_130318.json
├── SPARC_A_EA_Building Levels & Datum_20251104_130421.json
└── ...
```

**Issues:**
- ❌ **Flat structure** - all models in one folder
- ❌ **No project organization** - mixed projects in same folder
- ❌ **Filename collision risk** - if run multiple times per day
- ❌ **Hard to find specific model history**
- ❌ Uses `.json` extension (inconsistent with RevitSlave)

## RevitSlave3 Format ✅ (Target)

### Directory Structure
```
C:\Users\{username}\Documents\EnneadTab Ecosystem\Dump\RevitSlaveDatabase\
└── task_output\
    └── 2412_SPARC\                              # Project folder
        ├── SPARC Coordinates Model.rvt\         # Model folder
        │   ├── job_20251028_004330_327.sexyDuck
        │   ├── job_20251029_104520_412.sexyDuck
        │   └── job_20251030_154210_598.sexyDuck
        ├── SPARC_A_EA_CUNY_Building.rvt\
        │   ├── job_20251104_130218_101.sexyDuck
        │   └── job_20251104_145830_102.sexyDuck
        └── SPARC_A_EA_Shell.rvt\
            └── job_20251104_130318_103.sexyDuck
```

**Benefits:**
- ✅ **Hierarchical organization** - Project → Model → Jobs
- ✅ **Multi-run support** - Each run gets unique job file
- ✅ **Easy to browse history** - All runs for a model in one folder
- ✅ **Scalable** - Works across multiple projects
- ✅ Uses `.sexyDuck` extension (consistent with RevitSlave ecosystem)

### Filename Format

**RevitSlave3:**
```
job_{YYYYMMDD_HHMMSS}_{sequential_id}.sexyDuck
```

Example: `job_20251028_004330_327.sexyDuck`

**SparcHealth (current):**
```
{model_name}_{YYYYMMDD_HHMMSS}.json
```

Example: `SPARC_A_EA_CUNY_Building_20251104_130218.json`

## File Content Format

Both use the same JSON structure (RevitSlave-3.0 format):

```json
{
  "status": "completed",
  "job_metadata": {
    "job_id": "job_20251028_004330_327",
    "project_name": "2412_SPARC",
    "model_name": "SPARC Coordinates Model.rvt",
    "hub_name": "Ennead Architects LLP",
    "revit_version": 2024,
    "model_file_size_bytes": 0,
    "model_file_size_readable": "Unknown",
    "timestamp": "2025-10-28T01:37:39.864000",
    "execution_time_seconds": 10.49,
    "execution_time_readable": "10.5s"
  },
  "health_metric_result": {
    "version": "v2",
    "timestamp": "2025-10-28T01:37:39.571000",
    "document_title": "SPARC Coordinates Model",
    "is_EnneadTab_Available": false,
    "checks": {
      "project_info": {...},
      "linked_files": {...},
      "critical_elements": {...},
      "rooms": {...},
      "views_sheets": {...},
      "families": {...},
      "materials": {...},
      "warnings": {...},
      ...
    }
  },
  "export_data": null
}
```

## Implementation Plan for SparcHealth

### Phase 1: Update Output Path Structure

**Current:**
```python
output_path = "{base_path}/{model_name}_{timestamp}.json"
```

**Target:**
```python
output_path = "{base_path}/task_output/{project_name}/{model_name}.rvt/job_{timestamp}_{job_id}.sexyDuck"
```

### Phase 2: Update write_health_output()

```python
def write_health_output(health_output):
    """Write health data to hierarchical output folder (RevitSlave3 format)"""
    # Get base paths
    output_base = OUTPUT_SETTINGS.get('base_path', '')
    project_name = PROJECT_INFO.get('project_name', 'Unknown')
    model_name = MODEL_DATA.get('name', 'Unknown')
    job_id = JOB_ID
    
    # Build hierarchical path: {base}/task_output/{project}/{model}.rvt/
    task_output_dir = os.path.join(output_base, "task_output")
    project_dir = os.path.join(task_output_dir, project_name)
    model_dir = os.path.join(project_dir, model_name + ".rvt")
    
    # Ensure directories exist
    if not os.path.exists(model_dir):
        os.makedirs(model_dir)
    
    # Generate filename: job_{timestamp}_{id}.sexyDuck
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    output_filename = "job_{}_{}.sexyDuck".format(timestamp, job_id.split("_")[-1])
    output_path = os.path.join(model_dir, output_filename)
    
    # Write JSON file
    with open(output_path, 'w') as f:
        json.dump(health_output, f, indent=2)
    
    return output_path
```

### Phase 3: Update config.json

**Current:**
```json
"output": {
  "base_path": "C:\\Users\\{username}\\Documents\\EnneadTab Ecosystem\\Dump\\SparcHealth",
  "date_format": "%Y%m%d_%H%M%S"
}
```

**Target:**
```json
"output": {
  "base_path": "C:\\Users\\{username}\\Documents\\EnneadTab Ecosystem\\Dump\\RevitSlaveDatabase",
  "date_format": "%Y%m%d_%H%M%S",
  "use_hierarchical_structure": true
}
```

## Benefits of Migration

1. **Consistency** - Matches RevitSlave3 format exactly
2. **Organization** - Easy to find model history
3. **Scalability** - Works across multiple projects
4. **Multi-run** - No filename collisions
5. **Integration** - Can be processed by same tools as RevitSlave3
6. **Future-proof** - Standard format for all health checking

## Migration Notes

- Existing files in `SparcHealth/` can remain for historical reference
- New runs will use the hierarchical structure
- Update any consuming scripts to look in new location
- Consider creating a migration script to move old files to new structure

## Example Comparison

### Before (SparcHealth)
```
C:\...\Dump\SparcHealth\
├── SPARC_A_EA_CUNY_Building_20251104_130218.json  (2,597 bytes)
└── SPARC_A_EA_Shell_20251104_130318.json          (1,614 bytes)
```

### After (RevitSlave3 format)
```
C:\...\Dump\RevitSlaveDatabase\task_output\
└── 2412_SPARC\
    ├── SPARC_A_EA_CUNY_Building.rvt\
    │   └── job_20251104_130218_001.sexyDuck       (2,597 bytes)
    └── SPARC_A_EA_Shell.rvt\
        └── job_20251104_130318_002.sexyDuck       (1,614 bytes)
```

## Next Steps

1. ✅ Document the differences (this file)
2. ⬜ Update `write_health_output()` function
3. ⬜ Update `config.json` with new base path
4. ⬜ Test with single model
5. ⬜ Deploy to all SPARC models
6. ⬜ Update any consuming/reporting scripts

