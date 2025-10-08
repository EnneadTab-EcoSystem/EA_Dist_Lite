@echo off
REM RevitSlave EXE Runner with Debug Output
REM This launcher shows all output and waits for user interaction

REM Enable ANSI color support in Windows Console
REM This allows color codes to render properly instead of showing as raw text
chcp 65001 > nul 2>&1
set ENABLE_VIRTUAL_TERMINAL_PROCESSING=1

set SCRIPT_DIR=%~dp0
cd /d "%SCRIPT_DIR%"

echo ================================================================================
echo RevitSlave EXE Launcher - Debug Mode
echo ================================================================================
echo Working Directory: %CD%
echo EXE Path: %SCRIPT_DIR%RevitSlave.exe
echo.

REM Check if EXE exists
if not exist "RevitSlave.exe" (
    echo [ERROR] RevitSlave.exe not found in current directory
    echo Expected location: %SCRIPT_DIR%RevitSlave.exe
    echo.
    echo Window will auto-close in 5 hours or press any key to close now...
    timeout /t 18000 > nul
    exit /b 1
)

REM Run the EXE
echo [INFO] Starting RevitSlave.exe...
echo.
echo ================================================================================
echo EXE OUTPUT:
echo ================================================================================
RevitSlave.exe %*

REM Capture exit code
set EXIT_CODE=%ERRORLEVEL%

echo.
echo ================================================================================
echo EXE EXECUTION COMPLETE
echo ================================================================================

REM Report status
if %EXIT_CODE% neq 0 (
    echo [ERROR] RevitSlave.exe failed with exit code %EXIT_CODE%
    echo.
    echo Common issues:
    echo   - Missing dependencies (check if all required DLLs are present)
    echo   - File permissions (try running as administrator)
    echo   - Antivirus blocking execution
    echo   - Corrupted EXE file (try rebuilding)
) else (
    echo [SUCCESS] RevitSlave.exe completed successfully (exit code 0)
)

echo.
echo Window will auto-close in 5 hours or press any key to close now...
timeout /t 18000 > nul
exit /b %EXIT_CODE%

