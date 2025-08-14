@echo off
setlocal enabledelayedexpansion

REM EnneadTab InDesign Repather Launcher
REM This batch file checks Python installation and starts the application

echo ============================================================
echo 🔍 EnneadTab InDesign Repather - Python Installation Checker
echo ============================================================

REM Check if PowerShell is available
powershell -Command "exit" >nul 2>&1
if %errorlevel% neq 0 (
    echo ❌ PowerShell is not available. Please install PowerShell and try again.
    pause
    exit /b 1
)

REM Run PowerShell script to check Python installation
echo Checking Python installation...
powershell -ExecutionPolicy Bypass -File "%~dp0check_python.ps1" -Silent
if %errorlevel% neq 0 (
    echo.
    echo ❌ Python installation check failed.
    echo.
    echo 🔧 TROUBLESHOOTING:
    echo    1. Make sure Python is installed from python.org or Microsoft Store
    echo    2. Install pywin32: pip install pywin32
    echo    3. Make sure InDesign is installed on your system
    echo    4. Run this script as administrator if you have permission issues
    echo    5. Check your firewall settings if network access fails
    echo.
    echo Press any key to open the launcher page for detailed instructions...
    pause >nul
    
    REM Open launcher page in default browser
    start "" "%~dp0launcher.html"
    exit /b 1
)

echo ✅ Python installation check passed!
echo.
echo 🚀 Starting InDesign Repather...
echo.

REM Try to start the Python server
python "%~dp0generate_web_app.py"
if %errorlevel% neq 0 (
    echo ❌ Failed to start the Python server.
    echo.
    echo This might be due to:
    echo    - Missing Python dependencies
    echo    - Port 8080 already in use
    echo    - Permission issues
    echo.
    echo Press any key to open the launcher page for troubleshooting...
    pause >nul
    start "" "%~dp0launcher.html"
    exit /b 1
)

echo ✅ Application started successfully!
echo 🌐 Opening in your default browser...
echo.

REM Wait a moment for the server to start
timeout /t 2 /nobreak >nul

REM Open the main application in default browser
start "" "http://127.0.0.1:8080/IndesignRepather.html"

echo.
echo 💡 The application is now running at http://127.0.0.1:8080
echo 💡 Keep this window open while using the application
echo 💡 Press Ctrl+C to stop the server when you're done
echo.

REM Keep the batch file running to maintain the server
pause
