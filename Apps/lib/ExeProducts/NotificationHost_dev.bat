@echo off
REM Lightweight launcher for NotificationHost.
REM locate_executable prefers .bat over .exe. Spawns host and exits immediately.
setlocal
set "SCRIPT=%~dp0..\..\..\DarkSide\exes\source code\NotificationHost\NotificationHost.py"
if not exist "%SCRIPT%" (
  set "SCRIPT=C:\Users\szhang\github\ennead-llp\EnneadTab-OS\DarkSide\exes\source code\NotificationHost\NotificationHost.py"
)
start "" /B pyw -3 "%SCRIPT%"
exit /b 0
