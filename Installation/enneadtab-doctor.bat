@echo off
REM ===================================================================
REM  EnneadTab Doctor - user-facing diagnostic script
REM  Version: 1.0.0   Released: 2026-04-27
REM
REM  Run this when EnneadTab is misbehaving in Revit/Rhino. It checks
REM  the most common issues, prints a friendly report, and saves a copy
REM  to your Desktop you can attach to a support email.
REM
REM  This script does NOT change anything. It only looks at your setup.
REM  It runs as YOU (no admin required).
REM
REM  Usage:
REM     Double-click enneadtab-doctor.bat
REM     enneadtab-doctor.bat --self-test   (developer test, forces failures)
REM ===================================================================

setlocal enabledelayedexpansion

set "DOCTOR_VERSION=1.0.0"
set "DOCTOR_RELEASE=2026-04-27"

REM Resolve "this script's folder" once. Trailing backslash matters.
set "DOCTOR_DIR=%~dp0"

REM Pass-through self-test flag.
set "SELF_TEST="
if /I "%~1"=="--self-test" set "SELF_TEST=1"

REM Build a safe timestamp (sortable, no spaces, no colons, no slashes).
REM Uses PowerShell so we don't depend on regional date format.
for /f "usebackq delims=" %%T in (`powershell -NoProfile -Command "Get-Date -Format yyyyMMdd-HHmmss"`) do set "DOCTOR_TS=%%T"

REM Desktop report destination. We try OneDrive Desktop first because most
REM Ennead users have OneDrive-Ennead Architects redirected; fall back to
REM the classic local Desktop if the OneDrive path is missing.
set "REPORT_DIR=%USERPROFILE%\OneDrive - Ennead Architects\Desktop"
if not exist "%REPORT_DIR%" set "REPORT_DIR=%USERPROFILE%\Desktop"
set "REPORT_FILE=%REPORT_DIR%\enneadtab-doctor-%DOCTOR_TS%.txt"

REM Locate the PowerShell helper. It must sit next to this .bat file.
set "PS_HELPER=%DOCTOR_DIR%_doctor\run-checks.ps1"

if not exist "%PS_HELPER%" (
    echo.
    echo [FAIL] Internal error: cannot find diagnostic helper at:
    echo        %PS_HELPER%
    echo.
    echo This .bat file was probably copied without the _doctor folder
    echo next to it. Please re-run the EnneadTab installer to refresh
    echo your Installation folder, or email designtech@ennead.com and
    echo include this message.
    echo.
    pause
    exit /b 2
)

REM Pass --self-test through to the helper if requested.
set "PS_ARGS="
if defined SELF_TEST set "PS_ARGS=-SelfTest"

REM Run PowerShell with the helper. We avoid `2>&1` on the .bat side per
REM the project memory feedback_powershell_string_not_c_string and
REM Windows PowerShell 5.1 native-stderr quirk - the helper handles its
REM own output and tee'ing to the desktop report file.
powershell -NoProfile -ExecutionPolicy Bypass -File "%PS_HELPER%" -ReportFile "%REPORT_FILE%" -DoctorVersion "%DOCTOR_VERSION%" -DoctorRelease "%DOCTOR_RELEASE%" %PS_ARGS%
set "PS_EXIT=%ERRORLEVEL%"

echo.
echo -------------------------------------------------------------------
echo  Report saved to:
echo     %REPORT_FILE%
echo.
echo  If you need help, email designtech@ennead.com and attach that
echo  file. You may close this window after reading the summary above.
echo -------------------------------------------------------------------
echo.
pause

endlocal & exit /b %PS_EXIT%
