@echo off
REM InDesign Repather Launcher
REM Tries .venv Python first, falls back to system Python

echo ========================================
echo InDesign Repather Launcher
echo ========================================
echo.

REM Get the workspace root (3 levels up from this script)
set WORKSPACE_ROOT=%~dp0..\..\..
pushd "%WORKSPACE_ROOT%"

REM Check if .venv Python exists
if exist ".venv\Scripts\python.exe" (
    echo [INFO] Using .venv Python environment
    set PYTHON_EXE=%WORKSPACE_ROOT%\.venv\Scripts\python.exe
) else (
    echo [WARNING] .venv not found, falling back to system Python
    set PYTHON_EXE=python
)

REM Return to the IndesignRepather directory
popd

echo [INFO] Python: %PYTHON_EXE%
echo [INFO] Running IndesignRepather...
echo.

REM Run the application
"%PYTHON_EXE%" "%~dp0__main__.py"

REM Check exit code
if %ERRORLEVEL% neq 0 (
    echo.
    echo [ERROR] Application exited with error code: %ERRORLEVEL%
    pause
) else (
    echo.
    echo [SUCCESS] Application completed successfully
)

