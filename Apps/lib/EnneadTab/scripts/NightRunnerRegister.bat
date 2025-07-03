@echo off
REM Remove any existing task with the same name (ignore errors)
schtasks /delete /tn "NightRunner" /f >nul 2>&1

REM Date-based logic for DB_FOLDER
for /f "tokens=1-3 delims=/ " %%a in ('date /t') do (
    set "CURRENT_DATE=%%c%%a%%b"
)
set "CURRENT_USER=%USERNAME%"

if "%CURRENT_DATE%" geq "20250715" (
    set "DB_FOLDER=L:\4b_Design Technology\05_EnneadTab-DB"
) else if "%CURRENT_USER%"=="szhang" (
    set "DB_FOLDER=L:\4b_Design Technology\05_EnneadTab-DB"
) else (
    set "DB_FOLDER=L:\4b_Applied Computing\EnneadTab-DB"
)

REM Register the new task to run every day at midnight
schtasks /create ^
  /tn "NightRunner" ^
  /tr "powershell.exe -ExecutionPolicy Bypass -File \"%DB_FOLDER%\Stand Alone Tools\NightRunner.ps1\"" ^
  /sc daily ^
  /st 00:00 ^
  /rl LIMITED ^
  /f ^
  /ru %USERNAME% >nul 2>&1

REM Remove any existing hourly pin connection task
schtasks /delete /tn "PinConnection" /f >nul 2>&1

REM Register the new hourly task
schtasks /create ^
  /tn "PinConnection" ^
  /tr "powershell.exe -ExecutionPolicy Bypass -File \"%DB_FOLDER%\PinConnection.ps1\"" ^
  /sc hourly ^
  /rl LIMITED ^
  /f ^
  /ru %USERNAME% >nul 2>&1

echo All register suscefful. You may close this window
pause