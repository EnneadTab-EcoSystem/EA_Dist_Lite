@echo off
REM SparcHealth Launcher
REM Activates .venv Python environment and runs the orchestrator

echo ========================================
echo SparcHealth Orchestrator
echo ========================================
echo.

REM Navigate to script directory
cd /d "%~dp0"

REM Activate .venv Python environment
echo Activating Python environment...
call "%~dp0..\..\..\..\..\..\..\.venv\Scripts\activate.bat"

REM Run orchestrator
echo.
echo Starting orchestrator...
echo.
python "%~dp0orchestrator.py"

echo.
echo ========================================
echo Orchestrator finished
echo ========================================
pause

