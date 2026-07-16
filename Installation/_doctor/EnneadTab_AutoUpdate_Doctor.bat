@echo off
REM ============================================================================
REM  EnneadTab auto-update DOCTOR -- double-click this on the Cannon machine.
REM  It inspects, probes, and repairs the EnneadTab_OS_Installer_Task, and
REM  writes a full report file into THIS SAME FOLDER. Copy that report back.
REM  Keep this .bat and EnneadTab_AutoUpdate_Doctor.ps1 together.
REM ============================================================================
setlocal
set "PS1=%~dp0EnneadTab_AutoUpdate_Doctor.ps1"

if not exist "%PS1%" (
    echo.
    echo   FAIL  EnneadTab_AutoUpdate_Doctor.ps1 not found next to this .bat
    echo         Keep both files in the same folder.
    echo.
    pause
    exit /b 1
)

powershell -NoProfile -ExecutionPolicy Bypass -File "%PS1%"
set "RC=%ERRORLEVEL%"

echo.
echo   ==========================================================
echo   A report .txt was written into this folder. Copy it back.
echo   ==========================================================
echo.
pause
exit /b %RC%
