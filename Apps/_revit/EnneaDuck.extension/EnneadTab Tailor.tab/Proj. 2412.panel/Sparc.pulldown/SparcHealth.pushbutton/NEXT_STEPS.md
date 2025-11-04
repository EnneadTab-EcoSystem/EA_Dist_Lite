# SparcHealth Next Steps - RevitSlave-3.0 Integration

## Completed ✅

1. **Config Enhancement**
   - Added 18 SPARC models (Architecture, MEP, Structural, Fire Protection, Plumbing, Lighting, etc.)
   - Added discipline field to each model
   - Changed output path to local Documents folder (from OneDrive)

2. **Git Configuration**
   - Added runtime files to .gitignore (payloads, status, locks, logs, heartbeat)
   - Added global `*.lock` exclusion

3. **Enhanced Metrics Collection (Partial)**
   - ✅ Total element counts
   - ✅ Element counts by category
   - ✅ Warning counts with severity
   - ✅ View counts by type
   - ✅ Sheet counts
   - ✅ Workset information (names, counts)
   - ✅ Linked model counts and names
   - ✅ Family counts
   - ✅ Project info parameters
   - ✅ Design options

4. **Documentation**
   - Created REVITSLAVE3_METRICS_REFERENCE.md with comprehensive format guide
   - Created this NEXT_STEPS.md tracking document

## In Progress 🔨

1. **Output Format Migration**
   - Started converting to RevitSlave-3.0 format (job_metadata + health_metric_result)
   - Added helper functions: `format_time()`, `get_file_size_info()`
   - Need to complete the migration (see below)

## Remaining Work ⬜

### Phase 1: Complete Output Format Migration
**File**: `revit_health_check_script.py`

1. **Fix collect_health_metrics() function**
   - Change all `health_data[...]` references to use `checks[...]` dictionary
   - Store each metric group in checks (e.g., `checks["critical_elements"]`, `checks["views_sheets"]`)
   - Return `health_output` instead of `health_data`

2. **Update function call in health_check()**
   - Add `start_time = time.time()` at function start
   - Pass start_time to `collect_health_metrics(doc, start_time)`

3. **Update write_health_output()**
   - Ensure it correctly writes the new format
   - Test output file structure

### Phase 2: Advanced Metrics (Match RevitSlave-3.0)

1. **Worksharing User Tracking**
   ```python
   # For warnings and elements
   info = DB.WorksharingUtils.GetWorksharingTooltipInfo(doc, element_id)
   creator = info.Creator
   last_editor = info.LastChangedBy
   owner = info.Owner
   ```

2. **Enhanced Warning Analysis**
   - warning_categories{} (warning text -> count)
   - warning_creators{} (user -> count)
   - warning_last_editors{} (user -> count)
   - warning_details_per_creator{} (user -> {warning -> count})
   - warning_details_per_last_editor{} (user -> {warning -> count})
   - Critical warnings using GUID list

3. **Workset Details** (expand existing)
   - workset_details[] (name, kind, id, is_open, is_editable, owner, creator, last_editor)
   - workset_element_counts{}
   - workset_element_ownership{} (creators, last_editors, current_owners)

4. **Room Analysis**
   - unplaced_room_details[] (id, name, number, level)
   - unbounded_room_details[] (id, name, number, level, area)
   - unplaced_percentage
   - unbounded_percentage

5. **View/Sheet Analysis**
   - views_not_on_sheets
   - schedules_not_on_sheets
   - view_count_by_type_template{}
   - view_count_by_type_non_template{}

6. **Additional Checks**
   - CAD files check
   - Graphical elements check
   - Groups check
   - Reference planes check
   - Materials check
   - Line count check
   - Filled regions check
   - Grids/levels check

### Phase 3: Safety & Performance

1. **Per-Metric Timeout Protection**
   ```python
   def safe_metric_check(metric_name, metric_func, doc, timeout_seconds=300):
       with OperationTimeout(timeout_seconds):
           return metric_func(doc)
   ```

2. **Error Loop Detection**
   ```python
   error_detector = ErrorLoopDetector(max_same_error=5, time_window=30)
   ```

3. **Graceful Degradation**
   - 70% success rate threshold
   - Continue if individual metrics fail
   - Track successful vs failed metrics

### Phase 4: Testing & Validation

1. Test with multiple SPARC models
2. Verify output format matches RevitSlave-3.0
3. Test error handling and timeout scenarios
4. Validate file size calculations
5. Test worksharing info collection
6. Performance testing (execution time < 10 min target)

## Quick Win Priorities

Focus on these high-value, low-effort improvements first:

1. ✅ Complete output format migration (Phase 1) - **DO THIS FIRST**
2. ✅ Add worksharing user tracking for warnings
3. ✅ Add enhanced workset details
4. ✅ Add room analysis with details
5. ⬜ Per-metric timeout protection

## Migration Strategy

**Recommended Approach**:
1. Create backup of current `revit_health_check_script.py`
2. Complete Phase 1 (output format) - test immediately
3. Add Phase 2 metrics incrementally - test after each addition
4. Add Phase 3 safety features
5. Final testing with all 18 SPARC models

## References

- [REVITSLAVE3_METRICS_REFERENCE.md](./REVITSLAVE3_METRICS_REFERENCE.md) - Complete format guide
- [RevitSlave-3.0 entry_script.py](../../../../../DarkSide/exes/source code/RevitSlave-3.0/revit_logic/entry_script.py)
- [RevitSlave-3.0 health_metric/](../../../../../DarkSide/exes/source code/RevitSlave-3.0/revit_logic/health_metric/)

## Success Criteria

SparcHealth is fully migrated when:
- ✅ Output format matches RevitSlave-3.0 exactly
- ✅ All 17 health checks are implemented
- ✅ Worksharing user tracking works
- ✅ Per-metric timeouts prevent hangs
- ✅ Graceful degradation (70% threshold)
- ✅ Execution time < 10 minutes per model
- ✅ All 18 SPARC models process successfully

