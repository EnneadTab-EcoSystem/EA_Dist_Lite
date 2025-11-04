# SPARC Model Opening Failures - Analysis

## Test Run Summary (Nov 4, 2025)

**Total Models**: 18  
**Successful**: 6 (33%)  
**Failed**: 12 (67%)

## Successful Models ✅

| Model | Discipline | Time | Notes |
|-------|------------|------|-------|
| SPARC_A_EA_CUNY_Building | Architecture | 220s | Largest Architecture model |
| SPARC_A_EA_Shell | Architecture | 50s | |
| SPARC_A_EA_Building Levels & Datum | Architecture | 70s | |
| SPARC_A_EA_ULURP Building | Architecture | 50s | |
| 2412_SPARC-A_Building | Architecture | 70s | |
| SPARC_A_DA_Site & Infrastructure | Architecture | 175s | |

**Pattern**: ✅ **All Architecture models opened successfully**

## Failed Models ❌

### MEP Models (6 failed)
| Model | project_guid | Time | Error |
|-------|--------------|------|-------|
| SPARC_E_EA_CUNY | d92aaa44... | 30s | Failed to open |
| SPARC_M_EA_CUNY | d92aaa44... | 30s | Failed to open |
| SPARC_MEP_EA_Systems | d92aaa44... | 30s | Failed to open |
| SPARC_E_SE_NYCPS_Building | **a15d8c47...** | 30s | Failed to open |
| SPARC_M_SE_NYCPS_Building | d92aaa44... | 35s | Failed to open |
| 2412_SPARC-LGT_Lighting | d92aaa44... | 30s | Failed to open |

### Other Disciplines (6 failed)
| Model | Discipline | Time | Error |
|-------|------------|------|-------|
| SPARC_S_LE_BUILDING | Structural | 35s | Failed to open |
| SPARC_FP_SE_Building | Fire Protection | 35s | Failed to open |
| SPARC_P_SE_Building | Plumbing | 30s | Failed to open |
| SPARC_TECH_SM&W_CUNY_BUILDING | Technology | 30s | Failed to open |
| SPARC_LP_JA_Lab | Lab Planning | 50s | Failed to open |
| DA_2410_SPARC_Site | Site | 950s | **Hung for 15+ minutes** |

## Key Observations

### 1. Discipline Pattern
- ✅ **100% Architecture success** (6/6)
- ❌ **0% MEP/Other success** (0/12)

### 2. Failure Times
- Most MEP models fail in **30-50 seconds** (very fast)
- DA_2410_SPARC_Site **hung for 950 seconds** (15.8 min) before failing
- Fast failures suggest **permission/access issues**
- Slow failure suggests **corrupted or problematic model**

### 3. GUIDs Analysis
- All models have **valid GUIDs** in config
- All failed models **exist in guid_cache.json** (RevitSlave has seen them)
- SPARC_E_SE_NYCPS_Building uses **different project_guid** (a15d8c47...)
- Most models share **same project_guid** (d92aaa44...)

## Hypotheses for Failures

### Hypothesis 1: Permissions/Access Control 🔒
**Most Likely**

**Evidence**:
- Fast failures (30s) suggest authentication/permission denial
- All MEP/consultant models failed
- All Architecture models succeeded
- Pattern matches "owner vs. consultant" model access

**Test**: 
- Check ACC project permissions for current user
- Verify if MEP models are in different ACC folder
- Check if models require special permissions

### Hypothesis 2: Different Project/Hub 🏢
**Possible**

**Evidence**:
- SPARC_E_SE_NYCPS_Building has different project_guid
- Some models might be in consultant hubs
- RevitSlave might have different ACC access than SparcHealth

**Test**:
- Verify all models are in same ACC project
- Check if consultant models are shared links

### Hypothesis 3: Model Format/Version Issues 🔧
**Less Likely**

**Evidence**:
- All are configured as Revit 2024
- RevitSlave has accessed these models before (in guid_cache)
- DA_2410_SPARC_Site hanging suggests possible corruption

**Test**:
- Check if models can be opened manually in Revit
- Verify model versions match

### Hypothesis 4: Workset/Link Dependencies 🔗
**Less Likely**

**Evidence**:
- MEP models typically have many links
- Fast failures don't match workset loading times

## Recommended Actions

### Immediate Actions

1. **Check ACC Permissions** ⭐ Priority 1
   ```
   - Log into ACC web interface
   - Navigate to 2412_SPARC project
   - Check permissions for current user
   - Verify access to MEP/consultant folders
   ```

2. **Test Manual Open** ⭐ Priority 2
   ```
   - Try opening SPARC_E_EA_CUNY manually in Revit 2024
   - Note: any authentication dialogs
   - Check: if model opens at all
   ```

3. **Compare with RevitSlave3** ⭐ Priority 3
   ```
   - Check if RevitSlave3 successfully opened these models
   - Review RevitSlave3 logs for these models
   - Compare authentication methods
   ```

### Investigation Scripts

#### Check RevitSlave3 History
```powershell
Get-ChildItem "C:\Users\szhang\Documents\EnneadTab Ecosystem\Dump\RevitSlaveDatabase\task_output\2412_SPARC" -Recurse -Filter "*.sexyDuck" | Where-Object { $_.Directory.Name -like "*SPARC_E_EA_CUNY*" -or $_.Directory.Name -like "*SPARC_M_EA_CUNY*" } | Select-Object FullName, LastWriteTime
```

#### Check Journal Files
```powershell
# Look for Revit journal entries about failed models
Get-Content "C:\Users\szhang\AppData\Local\Temp\*\journal.*.txt" -ErrorAction SilentlyContinue | Select-String "SPARC_E_EA_CUNY|Failed|Error" | Select-Object -First 20
```

## Workarounds

### Option 1: Use RevitSlave3 Instead
RevitSlave3 appears to have successfully opened many of these models. Use RevitSlave3 with SPARC filter for complete coverage.

### Option 2: Request Permissions
Contact ACC project admin to grant full read access to all SPARC models.

### Option 3: Process in Batches
- Process Architecture models with SparcHealth (working)
- Process MEP/consultant models separately when permissions resolved

### Option 4: Add Detailed Error Logging
Enhance error logging to capture specific Revit error messages:
- Authentication failures
- File not found errors
- Permission denied messages
- Network timeout errors

## Next Steps

1. ✅ Update SparcHealth to use RevitSlave3 hierarchical structure (DONE)
2. ⬜ Check ACC permissions for current user
3. ⬜ Test manual open of failed models
4. ⬜ Review RevitSlave3 logs for these models
5. ⬜ Add detailed error logging in SparcHealth
6. ⬜ Document actual root cause once identified

## Status: Investigation Required 🔍

The failures are **systematic** (all MEP/consultant models) and **consistent** (fast failures), suggesting an **access/permission issue** rather than code bugs. Architecture models work perfectly, confirming the health check logic is sound.

