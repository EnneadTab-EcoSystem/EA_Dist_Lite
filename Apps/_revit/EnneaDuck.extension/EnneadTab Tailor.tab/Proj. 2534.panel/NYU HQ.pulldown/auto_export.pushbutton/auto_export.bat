@echo off
REM Auto Export Batch File - Runs pyRevit script to open model and export
REM This script opens Revit 2026 in zero-doc mode, opens the NYU HQ model, exports, and closes

echo ================================================
echo NYU HQ Auto Export
echo ================================================
echo.
echo Starting pyRevit to run auto_export_script.py...
echo This will:
echo   1. Open Revit 2026 (zero-doc mode)
echo   2. Open and activate 2534_A_EA_NYU HQ_Shell (detached)
echo   3. Run export operations
echo   4. Close Revit
echo.
echo ================================================

REM Run pyRevit script with Revit 2026 using empty document
REM Note: Using empty_doc_2026.rvt as placeholder, script will open actual cloud model
REM Import KingDuck.lib (contains proDUCKtion), script will manually add lib path if needed
pyrevit run "C:\Users\szhang\github\EnneadTab-OS\Apps\_revit\EnneaDuck.extension\EnneadTab Tailor.tab\Proj. 2534.panel\NYU HQ.pulldown\auto_export.pushbutton\auto_export_script.py" "C:\Users\szhang\github\EnneadTab-OS\Apps\_revit\DuckMaker.extension\EnneadTab.tab\Magic.panel\misc.pulldown\auto_upgrade.pushbutton\empty_doc_2026.rvt" --revit=2026 --purge --import="C:\Users\szhang\github\EnneadTab-OS\Apps\_revit\KingDuck.lib"

REM Capture exit code
set EXIT_CODE=%ERRORLEVEL%

echo.
echo ================================================
if %EXIT_CODE% neq 0 (
    echo [ERROR] Auto export failed with exit code %EXIT_CODE%
) else (
    echo [SUCCESS] Auto export completed successfully
)
echo ================================================
echo.

REM Wait for user input before closing
echo Press any key to close this window...
pause > nul