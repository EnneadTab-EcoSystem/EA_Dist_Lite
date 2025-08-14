@echo off
title EnneadTab InDesign Repather
echo ========================================
echo   EnneadTab InDesign Repather
echo   Professional Link Management Tool
echo ========================================
echo.

echo [INFO] Redirecting to the new launcher...
echo [INFO] Please use start_repather.bat as the main entry point.
echo.

REM Redirect to the new launcher
cd /d "%~dp0src"
start "" "%~dp0src\start_repather.bat"

echo.
echo [INFO] The new launcher should open automatically.
echo [INFO] If it doesn't, please run start_repather.bat manually.
echo.
pause
