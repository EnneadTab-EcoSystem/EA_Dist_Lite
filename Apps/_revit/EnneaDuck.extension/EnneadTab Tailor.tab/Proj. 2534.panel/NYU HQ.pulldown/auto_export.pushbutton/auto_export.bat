@echo off
REM Auto Export Batch File - Runs pyRevit script to open model and export
REM This script opens Revit 2026 in zero-doc mode, opens the NYU HQ model, exports, and closes

REM Lock file to prevent multiple instances
set LOCK_FILE="%~dp0auto_export.lock"

REM Check if lock file exists (another instance is running)
if exist %LOCK_FILE% (
    echo ================================================
    echo NYU HQ Auto Export - ALREADY RUNNING
    echo ================================================
    echo.
    echo Another auto export is already running.
    echo Please wait for it to complete before starting a new one.
    echo.
    echo Lock file: %LOCK_FILE%
    echo.
    echo Press any key to close this window...
    pause > nul
    exit /b 1
)

REM Create lock file
echo %DATE% %TIME% > %LOCK_FILE%

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

REM Determine paths (developer vs distribution)
set DEV_ROOT=C:\Users\%USERNAME%\github\EnneadTab-OS
set DIST_ROOT=C:\Users\%USERNAME%\Documents\EnneadTab Ecosystem\EA_Dist

if exist "%DEV_ROOT%\Apps\_revit\KingDuck.lib" (
    set SCRIPT_PATH=%DEV_ROOT%\Apps\_revit\EnneaDuck.extension\EnneadTab Tailor.tab\Proj. 2534.panel\NYU HQ.pulldown\auto_export.pushbutton\auto_export_script.py
    set EMPTY_DOC=%DEV_ROOT%\Apps\_revit\DuckMaker.extension\EnneadTab.tab\Magic.panel\misc.pulldown\auto_upgrade.pushbutton\empty_doc_2026.rvt
    set IMPORT_PATH=%DEV_ROOT%\Apps\_revit\KingDuck.lib
) else (
    set SCRIPT_PATH=%DIST_ROOT%\Apps\_revit\EnneaDuck.extension\EnneadTab Tailor.tab\Proj. 2534.panel\NYU HQ.pulldown\auto_export.pushbutton\auto_export_script.py
    set EMPTY_DOC=%DIST_ROOT%\Apps\_revit\DuckMaker.extension\EnneadTab.tab\Magic.panel\misc.pulldown\auto_upgrade.pushbutton\empty_doc_2026.rvt
    set IMPORT_PATH=%DIST_ROOT%\Apps\_revit\KingDuck.lib
)

pyrevit run "%SCRIPT_PATH%" "%EMPTY_DOC%" --revit=2026 --purge --import="%IMPORT_PATH%"

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

REM Clean up lock file
if exist %LOCK_FILE% del %LOCK_FILE%

REM Wait for user input before closing
echo Press any key to close this window...
pause > nul