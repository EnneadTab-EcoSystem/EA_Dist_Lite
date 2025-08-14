@echo off
title EnneadTab InDesign Writer Helper
echo ========================================
echo   EnneadTab InDesign Writer Helper
echo   Professional Text Management Tool
echo ========================================
echo.

REM Check if Python is installed on the system
python --version >nul 2>&1
if errorlevel 1 (
    echo [ERROR] Python is not installed on your computer
    echo.
    echo Please install Python 3.13 from the Microsoft Store:
    echo https://www.microsoft.com/store/apps/9PJPW5LDXLZ5
    echo.
    echo After installing Python, restart this application.
    pause
    exit /b 1
)

REM Check if Python 3.13 is available in the _engine directory
set PYTHON_PATH=%~dp0..\..\_engine\python.exe
if not exist "%PYTHON_PATH%" (
    echo [INFO] Python found on system, but not in _engine directory
    echo [INFO] Using system Python installation
    set PYTHON_PATH=python
) else (
    echo [INFO] Using Python from _engine directory
)

echo [INFO] Python found at %PYTHON_PATH%, checking modules...
cd /d "%~dp0src"

REM Check and install required modules
"%PYTHON_PATH%" check_modules.py
if errorlevel 1 (
    echo [ERROR] Failed to check/install required modules
    pause
    exit /b 1
)

echo.
echo [INFO] Starting InDesign Writer Helper...
echo [INFO] Opening browser with user-friendly interface...
echo.

REM Start the web server on port 8081 for a more professional look
start "EnneadTab InDesign Writer Helper" /min "%PYTHON_PATH%" simple_server.py

REM Wait a moment for server to start
timeout /t 2 /nobreak >nul

REM Open browser with custom title and user-friendly URL
echo [INFO] Launching application interface...
start "" "http://localhost:8081/"

echo.
echo [SUCCESS] InDesign Writer Helper is now running!
echo.
echo Application Features:
echo • Auto-detect InDesign and open documents
echo • View all text frames in your document
echo • Navigate between text frames and pages
echo • Preview text content in a large text box
echo • Future: AI-powered text suggestions and modifications
echo.
echo The application will open in your default browser.
echo Close this window when you're done using the application.
echo.
pause
