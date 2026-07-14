@echo off
REM Remove any existing task with the same name (ignore errors)
schtasks /delete /tn "NightRunner" /f >nul 2>&1

REM Resolve DB_FOLDER (#2360). Batch cannot parse JSON, so it honours only the
REM EA_SHARED_ROOT environment variable and otherwise falls back to the legacy
REM L: path. At cutover, set EA_SHARED_ROOT machine-wide (GPO / setx) and
REM re-run this registrar; the Python and PowerShell resolvers additionally
REM read Apps/lib/EnneadTab/shared_root.json.
if defined EA_SHARED_ROOT (
    set "DB_FOLDER=%EA_SHARED_ROOT%\05_EnneadTab-DB"
) else (
    set "DB_FOLDER=L:\4b_Design Technology\05_EnneadTab-DB"
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