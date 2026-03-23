@echo off
setlocal
set "REPO_ROOT=%~dp0..\..\..\"
set "SCRIPT=%REPO_ROOT%DarkSide\exes\source code\MonitorDriveDecoderSilent.py"
set "VENV_PY=%REPO_ROOT%.venv\Scripts\python.exe"
if exist "%VENV_PY%" ( "%VENV_PY%" "%SCRIPT%" ) else ( python "%SCRIPT%" 2>/dev/null )
