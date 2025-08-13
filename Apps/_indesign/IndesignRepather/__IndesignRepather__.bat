@echo off
title InDesign Repather - Single Entry Point
color 0A
echo ========================================
echo    InDesign Repather Application
echo ========================================
echo.

REM Check if Python is installed (try multiple Python commands)
set PYTHON_CMD=
python --version >nul 2>&1
if not errorlevel 1 (
    set PYTHON_CMD=python
    goto :python_found
)

python3 --version >nul 2>&1
if not errorlevel 1 (
    set PYTHON_CMD=python3
    goto :python_found
)

py --version >nul 2>&1
if not errorlevel 1 (
    set PYTHON_CMD=py
    goto :python_found
)

REM Try Microsoft Store Python 3.13 specifically
py -3.13 --version >nul 2>&1
if not errorlevel 1 (
    set PYTHON_CMD=py -3.13
    goto :python_found
)

REM Python not found - provide detailed instructions
echo ERROR: Python is not installed or not in PATH
echo.
echo Please install Python using one of these methods:
echo.
echo 1. Microsoft Store (Recommended):
echo    - Open Microsoft Store
echo    - Search for "Python 3.13"
echo    - Install "Python 3.13" by Python Software Foundation
echo.
echo 2. Official Website:
echo    - Go to https://python.org/downloads/
echo    - Download and install Python 3.13
echo    - Make sure to check "Add Python to PATH" during installation
echo.
echo 3. After installation, restart this application
echo.
pause
exit /b 1

:python_found
echo Python found: %PYTHON_CMD%
%PYTHON_CMD% --version
echo.

echo Checking and installing required dependencies...
echo.

REM Check if module checker script exists
if not exist "src\check_modules.py" (
    echo ERROR: Module checker script not found
    echo Please ensure check_modules.py is in the src directory
    echo.
    pause
    exit /b 1
)

REM Use the Python module checker script
%PYTHON_CMD% src\check_modules.py
if errorlevel 1 (
    echo.
    echo ERROR: Failed to install required dependencies
    echo Please check the errors above and try again
    echo.
    pause
    exit /b 1
)

echo.
echo All dependencies are ready!
echo.

REM Check if InDesign is available
echo Checking InDesign availability...
%PYTHON_CMD% -c "import sys; sys.path.append('src'); from get_indesign_version import InDesignVersionDetector; detector = InDesignVersionDetector(); result = detector.get_available_indesign_versions(); print(f'Found {result[\"total_found\"]} InDesign version(s)'); [print(f'  - {v[\"version\"]}') for v in result['versions']]"
if errorlevel 1 (
    echo WARNING: Could not detect InDesign versions
    echo The application may still work if InDesign is installed
    echo.
)

echo.
echo Starting web server...
echo The application will open in your browser automatically.
echo Keep this window open while using the app.
echo.
echo To stop the server, press Ctrl+C
echo.
echo ========================================
echo.

REM Start the web application
%PYTHON_CMD% src\generate_web_app.py

echo.
echo Server stopped. Press any key to exit...
pause >nul
