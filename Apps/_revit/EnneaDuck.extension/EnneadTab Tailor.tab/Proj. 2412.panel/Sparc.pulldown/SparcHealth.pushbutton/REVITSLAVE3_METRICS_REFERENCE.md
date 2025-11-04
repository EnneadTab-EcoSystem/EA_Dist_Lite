# RevitSlave-3.0 Health Metrics Reference

Reference document for SparcHealth based on RevitSlave-3.0 health metrics system.

## Output Structure

```json
{
  "job_metadata": {
    "job_id": "string",
    "hub_name": "string",
    "project_name": "string",
    "model_name": "string",
    "model_file_size_bytes": 0,
    "model_file_size_readable": "string",
    "revit_version": "string",
    "timestamp": "ISO8601",
    "execution_time_seconds": 0.0,
    "execution_time_readable": "string"
  },
  "health_metric_result": {
    "version": "v2",
    "timestamp": "ISO8601",
    "document_title": "string",
    "is_EnneadTab_Available": false,
    "checks": {
      "project_info": {},
      "linked_files": {},
      "critical_elements": {},
      "rooms": {},
      "views_sheets": {},
      "templates_filters": {},
      "cad_files": {},
      "families": {},
      "graphical_elements": {},
      "groups": {},
      "reference_planes": {},
      "materials": {},
      "line_count": {},
      "warnings": {},
      "file_size": {},
      "filled_regions": {},
      "grids_levels": {}
    }
  },
  "status": "completed"
}
```

## Metrics Collected (17 Checks)

### 1. project_info (120s timeout)
- project_name, project_number, client_name
- project_phases[]
- is_workshared
- **worksets**: detailed workset info
  - total_worksets, user_worksets
  - workset_names[]
  - workset_details[] (name, kind, id, is_open, is_editable, owner, creator, last_editor)
  - workset_element_counts{}
  - workset_element_ownership{} (creators, last_editors, current_owners)

### 2. linked_files (180s timeout)
- linked_files[] (linked_file_name, instance_name, loaded_status, pinned_status)
- linked_files_count

### 3. critical_elements (180s timeout)
- total_elements
- purgeable_elements
- warning_count
- **warning_details[]** (description, severity, element_ids[], elements_info[])
- **warning_creators{}** (user -> count)
- **warning_last_editors{}** (user -> count)
- critical_warning_count
- critical_warning_details[]

### 4. rooms (120s timeout)
- total_rooms
- unplaced_rooms (count)
- unbounded_rooms (count)
- **unplaced_room_details[]** (id, name, number, level)
- **unbounded_room_details[]** (id, name, number, level, area)
- unplaced_percentage
- unbounded_percentage

### 5. views_sheets (180s timeout)
- total_sheets
- total_views
- views_not_on_sheets
- schedules_not_on_sheets
- copied_views
- **view_count_by_type{}** (all views)
- **view_count_by_type_non_template{}**
- **view_count_by_type_template{}**

### 6. templates_filters (180s timeout)
- View templates and filter analysis

### 7. cad_files (180s timeout)
- CAD import analysis

### 8. families (180s timeout)
- Family metrics

### 9. graphical_elements (180s timeout)
- Detail components and annotations

### 10. groups (120s timeout)
- Group analysis

### 11. reference_planes (120s timeout)
- Reference plane counts

### 12. materials (120s timeout)
- Material usage analysis

### 13. line_count (120s timeout)
- Line pattern counts

### 14. warnings (300s timeout)
- warning_count
- critical_warning_count (using GUID list)
- **warning_categories{}** (warning text -> count)
- **warning_count_per_user{}** (by_creator{}, by_last_editor{})
- **warning_details_per_creator{}** (user -> {warning -> count})
- **warning_details_per_last_editor{}** (user -> {warning -> count})

### 15. file_size (60s timeout)
- File size metrics

### 16. filled_regions (120s timeout)
- Filled region analysis

### 17. grids_levels (120s timeout)
- Grid and level analysis

## Safety Features

### Error Loop Detection
```python
ErrorLoopDetector(max_same_error=5, time_window=30)
```

### Operation Timeout
```python
OperationTimeout(timeout_seconds=300)
```

### Graceful Degradation
- 70% success rate threshold
- Per-metric timeout protection
- Continued execution if individual metrics fail

## Key Patterns

### Worksharing Info Tracking
```python
info = DB.WorksharingUtils.GetWorksharingTooltipInfo(doc, element_id)
creator = info.Creator
last_editor = info.LastChangedBy
owner = info.Owner
```

### Element Count by Category
```python
count = DB.FilteredElementCollector(doc)\
    .OfCategory(bic)\
    .WhereElementIsNotElementType()\
    .GetElementCount()
```

### Warning Analysis with User Tracking
- Track creators and last editors for all warnings
- Group warnings by description
- Identify critical warnings using GUID list
- Calculate warning percentages per user

## File Naming Convention
```
{timestamp}_{project_name}_{model_name}_health_metric.json
```

## Next Steps for SparcHealth

1. ✅ Add comprehensive metrics (already started)
2. ⬜ Match output structure (job_metadata + health_metric_result)
3. ⬜ Add per-metric timeout protection
4. ⬜ Add worksharing user tracking (creator/last_editor)
5. ⬜ Add advanced warning analysis
6. ⬜ Add file size metrics
7. ⬜ Add execution time tracking
8. ⬜ Add graceful degradation (70% threshold)

