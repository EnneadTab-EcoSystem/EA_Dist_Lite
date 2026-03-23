@echo off
REM MonitorDriveDecoder — Aggregate drive reports into trend charts
setlocal
set "REPO_ROOT=%~dp0..\..\..\"
set "SCRIPT=%REPO_ROOT%DarkSide\exes\source code\MonitorDriveDecoder.py"
set "VENV_PY=%REPO_ROOT%.venv\Scripts\python.exe"

if exist "%VENV_PY%" (
    "%VENV_PY%" "%SCRIPT%"
    exit /b
)
where python >/dev/null 2>&1 && (
    python "%SCRIPT%"
    exit /b
)
echo Python not found. Contact Design Technology.
pause
