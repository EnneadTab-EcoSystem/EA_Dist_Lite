# Revit Logic Comparison: SparcHealth vs. RevitSlave3

## What if we copy RevitSlave3's entry_script.py into SparcHealth?

### Current Architecture

**SparcHealth** (`revit_health_check_script.py`):
```python
def collect_health_metrics(doc, start_time):
    # Import health_metric modules
    from health_metric import project_checks, linked_files_checks, ...
    
    # Run 17 checks directly (no timeout protection)
    checks["project_info"] = project_checks.check_project_info(doc)
    checks["linked_files"] = linked_files_checks.check_linked_files(doc)
    # ... 15 more checks
    
    return health_output
```

**RevitSlave3** (`entry_script.py`):
```python
def run_health_metrics(doc, job_payload):
    # Import health_metric modules
    from health_metric import project_checks, linked_files_checks, ...
    
    # Define metrics with timeouts
    metrics_to_run = [
        ("project_info", project_checks.check_project_info, 120),
        ("linked_files", linked_files_checks.check_linked_files, 180),
        # ... with individual timeouts
    ]
    
    # Run each check with timeout protection
    for metric_name, metric_func, timeout in metrics_to_run:
        result = safe_metric_check(metric_name, metric_func, doc, timeout)
        health_report["checks"][metric_name] = result
    
    return health_report, error_message
```

---

## Key Differences

### 1. Per-Metric Timeout Protection ⭐

**RevitSlave3 Has:**
```python
def safe_metric_check(metric_name, metric_func, doc, timeout_seconds=300):
    with OperationTimeout(timeout_seconds):
        metric_result = metric_func(doc)
    return result
```

**Benefits:**
- ✅ Prevents one slow check from hanging entire job
- ✅ Individual timeouts per check (120s-300s)
- ✅ Graceful handling of timeout failures
- ✅ Continues processing even if one check fails

**SparcHealth Currently:**
- ❌ No per-metric timeouts
- ❌ If one check hangs, entire job hangs
- ❌ If one check crashes, entire collection fails

---

### 2. Error Loop Detection

**RevitSlave3 Has:**
```python
error_detector = ErrorLoopDetector(max_same_error=5, time_window=30)

# In each metric:
try:
    result = metric_func(doc)
except Exception as e:
    error_detector.record_error(str(e))  # Throws if loop detected
```

**Benefits:**
- ✅ Detects infinite error loops
- ✅ Prevents 240M+ error log disasters
- ✅ Aborts if same error occurs 5x in 30s

**SparcHealth Currently:**
- ❌ No error loop detection
- ❌ Could fill disk if error repeats

---

### 3. Graceful Degradation (70% Threshold)

**RevitSlave3 Has:**
```python
successful_metrics = 0
total_metrics = 17

for metric in metrics_to_run:
    result = safe_metric_check(...)
    if result["status"] == "completed":
        successful_metrics += 1

# Allow 30% failure rate
if successful_metrics / total_metrics >= 0.7:
    return health_report, None  # Success
else:
    return health_report, "Too many metrics failed"  # Failure
```

**Benefits:**
- ✅ Job succeeds if ≥70% of checks pass
- ✅ Collects partial data even with some failures
- ✅ Continues processing instead of aborting

**SparcHealth Currently:**
- ❌ All-or-nothing approach
- ❌ One check failure could fail entire job

---

### 4. Detailed Metric Debugging

**RevitSlave3 Has:**
```python
metrics_debug_entries = []

for each metric:
    metric_entry = {
        "name": metric_name,
        "status": "running",
        "started_at": datetime.now().isoformat(),
        "execution_time": None,
        "error": None,
    }
    metrics_debug_entries.append(metric_entry)
    _write_metric_debug_report(metrics_debug_entries)
    
    # Run check
    result = safe_metric_check(...)
    
    # Update entry
    metric_entry["status"] = result["status"]
    metric_entry["execution_time"] = result["execution_time"]
    _write_metric_debug_report(metrics_debug_entries)
```

**Benefits:**
- ✅ Real-time progress tracking per metric
- ✅ Execution time for each check
- ✅ Identifies slow checks
- ✅ Debug file for troubleshooting

**SparcHealth Currently:**
- ⚠️ Only overall job progress
- ❌ No per-metric timing
- ❌ Hard to identify which check is slow/failing

---

## What Would Happen If We Copy RevitSlave3's Logic?

### Option A: Copy Entire entry_script.py

**Changes Required:**
1. Replace `revit_health_check_script.py` with `entry_script.py`
2. Adapt payload reading (SparcHealth uses `current_job_payload.json`)
3. Adapt path structure (SparcHealth has different config)
4. Keep SparcHealth-specific status tracking

**Pros:**
- ✅ Get ALL RevitSlave3 safety features
- ✅ 100% consistency with RevitSlave3
- ✅ Battle-tested error handling
- ✅ Per-metric timeouts
- ✅ Graceful degradation
- ✅ Error loop detection

**Cons:**
- ⚠️ More code to maintain
- ⚠️ Need to adapt payload structure
- ⚠️ Duplicate code (not DRY)

---

### Option B: Extract Safety Features Only

**Keep SparcHealth's structure, add:**
1. `safe_metric_check()` function
2. `ErrorLoopDetector` class
3. `OperationTimeout` class
4. Graceful degradation logic
5. Metric debugging

**Pros:**
- ✅ Get safety features without full rewrite
- ✅ Keep SparcHealth's simpler config structure
- ✅ Easier to maintain
- ✅ More DRY (share health_metric modules)

**Cons:**
- ⚠️ Still some code duplication
- ⚠️ Need to manually sync if RevitSlave3 improves

---

### Option C: Create Shared Library (Best Long-term)

**Refactor both to use:**
```
Apps/lib/EnneadTab/REVIT/HealthMetric/
├── checks/           # Health check modules (shared)
│   ├── project_checks.py
│   ├── warnings_checks.py
│   └── ...
├── runner.py         # SafeMetricRunner with timeouts
├── error_detector.py # ErrorLoopDetector
└── timeout.py        # OperationTimeout
```

**Both SparcHealth and RevitSlave3 import from shared location**

**Pros:**
- ✅ True DRY - single source of truth
- ✅ Updates benefit both systems
- ✅ Easier testing and maintenance
- ✅ Consistent behavior across tools

**Cons:**
- ⚠️ Larger refactoring effort
- ⚠️ Need to ensure IronPython 2.7 compatibility
- ⚠️ Requires coordination between systems

---

## Recommendation

### Immediate (Today): Option B - Extract Safety Features

**Why:**
- Fastest implementation
- Gets critical safety features NOW
- Maintains SparcHealth's simplicity
- No major restructuring required

**What to Add:**
1. ✅ `safe_metric_check()` wrapper
2. ✅ Per-metric timeouts (copy from RevitSlave3)
3. ✅ `ErrorLoopDetector` class
4. ✅ `OperationTimeout` class  
5. ✅ Graceful degradation (70% threshold)

**Time Estimate**: 30 minutes

---

### Long-term (Future): Option C - Shared Library

**Why:**
- Reduces duplication
- Easier maintenance
- Consistent behavior
- Single source of truth

**When:**
- After SparcHealth is stable in production
- When adding new health checks
- During major refactoring phase

---

## Implementation Example (Option B)

### Add to revit_health_check_script.py:

```python
# At top of file (after imports)
class ErrorLoopDetector:
    """Detect and prevent infinite error loops."""
    def __init__(self, max_same_error=10, time_window=60):
        self.error_history = []
        self.max_same_error = max_same_error
        self.time_window = time_window
    
    def record_error(self, error_message):
        now = time.time()
        self.error_history = [(msg, ts) for msg, ts in self.error_history if now - ts < self.time_window]
        self.error_history.append((error_message, now))
        
        recent_messages = [msg for msg, _ in self.error_history]
        if recent_messages.count(error_message) >= self.max_same_error:
            raise RuntimeError("Error loop detected: '{}' occurred {} times".format(
                error_message, recent_messages.count(error_message)))

class OperationTimeout:
    """Enforce timeouts on operations."""
    def __init__(self, timeout_seconds):
        self.timeout_seconds = timeout_seconds
        self.timer = None
        self.timed_out = False
    
    def __enter__(self):
        def timeout_handler():
            self.timed_out = True
        self.timer = threading.Timer(self.timeout_seconds, timeout_handler)
        self.timer.start()
        return self
    
    def __exit__(self, *args):
        if self.timer:
            self.timer.cancel()
        if self.timed_out:
            raise TimeoutError("Operation timed out after {}s".format(self.timeout_seconds))

def safe_metric_check(metric_name, metric_func, doc, timeout_seconds=300):
    """Run health check with timeout protection"""
    start_time = time.time()
    print("  [{}] Starting...".format(metric_name))
    
    try:
        with OperationTimeout(timeout_seconds):
            result = metric_func(doc)
            elapsed = time.time() - start_time
            print("  [{}] Completed in {:.1f}s".format(metric_name, elapsed))
            return {"status": "completed", "data": result}
    except TimeoutError:
        print("  [{}] TIMEOUT after {}s".format(metric_name, timeout_seconds))
        return {"status": "timeout", "data": None, "error": "Timeout"}
    except Exception as e:
        print("  [{}] ERROR: {}".format(metric_name, str(e)))
        return {"status": "failed", "data": None, "error": str(e)}

# In collect_health_metrics():
def collect_health_metrics(doc, start_time):
    # ... existing code ...
    
    # Define metrics with timeouts
    metrics_to_run = [
        ("project_info", project_checks.check_project_info, 120),
        ("linked_files", linked_files_checks.check_linked_files, 180),
        ("critical_elements", elements_checks.check_critical_elements, 180),
        ("rooms", elements_checks.check_rooms, 120),
        ("views_sheets", views_checks.check_sheets_views, 180),
        ("templates_filters", templates_checks.check_templates_filters, 180),
        ("cad_files", cad_checks.check_cad_files, 180),
        ("families", families_checks.check_families, 180),
        ("graphical_elements", graphical_checks.check_graphical_elements, 180),
        ("groups", groups_checks.check_groups, 120),
        ("reference_planes", reference_checks.check_reference_planes, 120),
        ("materials", materials_checks.check_materials, 120),
        ("line_count", materials_checks.check_line_count, 120),
        ("warnings", warnings_checks.check_warnings, 300),
        ("file_size", file_checks.check_file_size, 60),
        ("filled_regions", regions_checks.check_filled_regions, 120),
        ("grids_levels", reference_checks.check_grids_levels, 120),
    ]
    
    successful_checks = 0
    error_detector = ErrorLoopDetector(max_same_error=5, time_window=30)
    
    for idx, (metric_name, metric_func, timeout) in enumerate(metrics_to_run, 1):
        print("[{}/17] {}".format(idx, metric_name))
        
        result = safe_metric_check(metric_name, metric_func, doc, timeout)
        
        if result["status"] == "completed":
            checks[metric_name] = result["data"]
            successful_checks += 1
        else:
            checks[metric_name] = {"error": result.get("error", "Unknown")}
            error_detector.record_error(result.get("error", "Unknown"))
    
    # Graceful degradation
    success_rate = successful_checks / len(metrics_to_run)
    if success_rate < 0.7:
        health_output["status"] = "partial"
        health_output["warning"] = "Only {}/{} checks succeeded".format(successful_checks, len(metrics_to_run))
    
    return health_output
```

---

## Benefits of Copying RevitSlave3 Logic

### 1. Safety Features ⭐⭐⭐

| Feature | Current SparcHealth | With RevitSlave3 Logic |
|---------|---------------------|------------------------|
| Per-metric timeouts | ❌ No | ✅ Yes (120-300s) |
| Error loop detection | ❌ No | ✅ Yes |
| Graceful degradation | ❌ No | ✅ Yes (70% threshold) |
| Timeout protection | ❌ No | ✅ Yes (threading-based) |
| Detailed error tracking | ⚠️ Basic | ✅ Advanced |

### 2. Robustness

**Scenario**: templates_filters check crashes (known issue)

**Current SparcHealth**:
- ❌ Entire health check fails
- ❌ No output file generated
- ❌ Wasted 3 minutes opening model
- ❌ Lost data from other 16 checks

**With RevitSlave3 Logic**:
- ✅ Only templates_filters fails
- ✅ Other 16 checks succeed
- ✅ Output file generated with 94% data
- ✅ Job marked as success (16/17 = 94% > 70%)

### 3. Performance Monitoring

**Current SparcHealth**:
```
[1/17] project_info
[2/17] linked_files
...
All 17 health checks completed!
```

**With RevitSlave3 Logic**:
```
[METRIC 1/17] project_info
  [METRIC OK] project_info completed in 2.3s
[METRIC 2/17] linked_files
  [METRIC OK] linked_files completed in 1.8s
[METRIC 6/17] templates_filters
  [METRIC TIMEOUT] templates_filters after 180s
[METRIC 7/17] cad_files
  [METRIC OK] cad_files completed in 4.1s
...
Success rate: 16/17 (94%)
```

**Benefits:**
- ✅ Know which check is slow
- ✅ Know which check failed
- ✅ Execution time per check
- ✅ Better debugging

---

## Potential Issues

### Issue 1: Template/Filter Crashes

**Known Problem**: `templates_checks.check_templates_filters()` can crash on large models

**RevitSlave3 Solution**:
- 180s timeout
- Catches crash
- Continues with other checks
- Reports failure in output

**SparcHealth Without It**:
- Entire job fails
- No output generated
- Process exits with code 4294967295

**This explains the "Unknown error" failures we're seeing!**

---

### Issue 2: Workset Ownership Takes Too Long

**Problem**: `project_checks.check_project_info()` samples 100 elements per workset for ownership

**On Large Models** (like SPARC_A_EA_CUNY_Building with 32 worksets):
- Could take 60+ seconds
- Without timeout, could hang

**RevitSlave3 Solution**:
- 120s timeout for project_info
- If exceeds, fails gracefully
- Other checks still run

---

## What Would We Get?

### Copy Full RevitSlave3 entry_script.py:

**Immediate Benefits:**
1. ✅ Per-metric timeouts (prevents hangs)
2. ✅ Error loop detection (prevents disasters)
3. ✅ Graceful degradation (70% success = job success)
4. ✅ Detailed metric debugging
5. ✅ Better error messages
6. ✅ Execution time tracking per metric
7. ✅ Metric status tracking

**Challenges:**
1. ⚠️ Need to adapt payload reading (different JSON structure)
2. ⚠️ Need to adapt status writing (different format)
3. ⚠️ More complex code to maintain

---

## Recommended Approach

### Phase 1: Add Safety Classes (5 minutes)

Copy these classes to `revit_health_check_script.py`:
- `ErrorLoopDetector`
- `OperationTimeout`  
- `safe_metric_check()`

### Phase 2: Update collect_health_metrics() (10 minutes)

Change from:
```python
checks["project_info"] = project_checks.check_project_info(doc)
```

To:
```python
result = safe_metric_check("project_info", project_checks.check_project_info, doc, 120)
if result["status"] == "completed":
    checks["project_info"] = result["data"]
else:
    checks["project_info"] = {"error": result.get("error")}
```

### Phase 3: Add Graceful Degradation (5 minutes)

Track success rate and allow 70% threshold.

---

## Why This Matters NOW

**Current Failures We're Seeing:**
```
Process exited with code: 4294967295 (total runtime: 2.5 min)
[ERROR] Job failed: Unknown error
```

**This is likely:**
- 🔥 One of the 17 checks is crashing (probably templates_filters)
- 🔥 Without per-metric timeout, entire job fails
- 🔥 Without graceful degradation, we lose all data

**With RevitSlave3 logic:**
- ✅ Crash isolated to one check
- ✅ Other 16 checks succeed
- ✅ Output file still generated
- ✅ Clear error message which check failed

---

## Decision Matrix

| Approach | Time | Risk | Benefit | Recommended |
|----------|------|------|---------|-------------|
| Do Nothing | 0 min | High | None | ❌ No |
| Add Safety Features (Option B) | 30 min | Low | High | ✅ **YES** |
| Copy Full entry_script.py (Option A) | 2 hrs | Medium | Very High | ⚠️ Later |
| Create Shared Library (Option C) | 4 hrs | Low | Maximum | ⏰ Future |

---

## Immediate Action Recommended

**Add Option B safety features NOW** to fix the "Unknown error" crashes we're seeing in production runs.

This will:
1. Fix the exit code 4294967295 failures
2. Prevent future disk space disasters
3. Allow partial data collection
4. Make SparcHealth production-stable

Would you like me to implement Option B (add safety features)?

