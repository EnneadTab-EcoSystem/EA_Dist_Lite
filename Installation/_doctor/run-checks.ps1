# ===================================================================
#  EnneadTab Doctor - PowerShell check engine
#  Invoked by Installation\enneadtab-doctor.bat
#
#  Design rules (do not relax without reading the comments):
#    * No auto-fix. Diagnostic only.
#    * No UAC elevation. Stay user-mode (per memory
#      feedback_uac_elevation_loses_user).
#    * Side-effect verification, not exit codes (per memory
#      feedback_exit_code_not_proof_of_success).
#    * If a check is skipped because a precondition is missing,
#      report it as SKIPPED with a reason -- never silent no-op
#      (per memory feedback_files_skipped_is_not_success).
#    * Plain English. Audience is architects, not developers.
#    * Tags only: [OK] [WARN] [FAIL] [SKIP]. No emoji.
#    * Tee everything to the desktop report file the .bat created.
#    * Never use [regex]::Escape on a hand-built escape string;
#      use [regex]::Escape() once on the literal source per memory
#      feedback_powershell_string_not_c_string.
# ===================================================================

[CmdletBinding()]
param(
    [Parameter(Mandatory=$true)] [string] $ReportFile,
    [Parameter(Mandatory=$true)] [string] $DoctorVersion,
    [Parameter(Mandatory=$true)] [string] $DoctorRelease,
    [switch] $SelfTest
)

$ErrorActionPreference = 'Continue'   # we handle our own errors per check

# --- Output helpers ------------------------------------------------------

# Console + report tee. We keep the report file UTF-8 (no BOM) so a
# support engineer can paste it into a ticket without mojibake.
$script:ReportLines = New-Object System.Collections.Generic.List[string]

function Write-Line {
    param([string]$Text = '', [ConsoleColor]$Color = 'Gray')
    Write-Host $Text -ForegroundColor $Color
    $script:ReportLines.Add($Text) | Out-Null
}

function Write-Header {
    param([string]$Text)
    Write-Line ''
    Write-Line ('=' * 67) Cyan
    Write-Line $Text Cyan
    Write-Line ('=' * 67) Cyan
}

# Each check returns a hashtable: @{ Status; Title; Detail; NextStep }
# Status is one of OK / WARN / FAIL / SKIP.

$script:CheckResults = New-Object System.Collections.Generic.List[hashtable]
$script:CheckIndex   = 0

function Add-Result {
    param(
        [Parameter(Mandatory=$true)] [string] $Title,
        [Parameter(Mandatory=$true)] [ValidateSet('OK','WARN','FAIL','SKIP')] [string] $Status,
        [string] $Detail = '',
        [string] $NextStep = ''
    )
    $script:CheckIndex++
    $idx = '{0,2}' -f $script:CheckIndex

    $color = switch ($Status) {
        'OK'   { 'Green' }
        'WARN' { 'Yellow' }
        'FAIL' { 'Red' }
        'SKIP' { 'DarkGray' }
    }

    $tag = "[$Status]".PadRight(7)
    Write-Line ("{0}. {1} {2}" -f $idx, $tag, $Title) $color
    if ($Detail) {
        foreach ($l in ($Detail -split "`r?`n")) {
            Write-Line ("       {0}" -f $l) DarkGray
        }
    }
    if ($Status -ne 'OK' -and $NextStep) {
        Write-Line "       Next: $NextStep" Magenta
    }

    $script:CheckResults.Add(@{
        Index    = $script:CheckIndex
        Title    = $Title
        Status   = $Status
        Detail   = $Detail
        NextStep = $NextStep
    }) | Out-Null
}

# --- Environment basics --------------------------------------------------

# Resolve to the user's actual profile, never an admin profile (per memory
# feedback_uac_elevation_loses_user). We are launched non-elevated by
# design but we still pin the path explicitly.
$UserProfile = $env:USERPROFILE
if (-not $UserProfile) { $UserProfile = [Environment]::GetFolderPath('UserProfile') }

$EcoSysFolder = Join-Path $UserProfile 'Documents\EnneadTab Ecosystem'
$EaDistFolder = Join-Path $EcoSysFolder 'EA_Dist'
$AppsFolder   = Join-Path $EaDistFolder 'Apps'
$LibFolder    = Join-Path $AppsFolder  'lib'
$CoreFolder   = Join-Path $LibFolder   'EnneadTab'
$ExeFolder    = Join-Path $LibFolder   'ExeProducts'
$EngineFolder = Join-Path $AppsFolder  '_engine'
$DumpFolder   = Join-Path $EcoSysFolder 'Dump'

$ComputerName = $env:COMPUTERNAME
$UserName     = $env:USERNAME

# --- Header --------------------------------------------------------------

$now = Get-Date -Format 'yyyy-MM-dd HH:mm:ss'
Write-Header "EnneadTab Doctor v$DoctorVersion (released $DoctorRelease)"
Write-Line "Run at:        $now"
Write-Line "Computer:      $ComputerName"
Write-Line "User:          $UserName"
Write-Line "Report file:   $ReportFile"
if ($SelfTest) { Write-Line "Mode:          SELF-TEST (forced failures, do not interpret as real)" Yellow }
Write-Line ''
Write-Line "What this is:  a quick health check of your EnneadTab install." DarkGray
Write-Line "What this is NOT: a fixer. Nothing here changes your machine." DarkGray
Write-Line ''
Write-Line ('-' * 67) Cyan
Write-Line "Running checks..." Cyan
Write-Line ('-' * 67) Cyan

# --- Check 1: EnneadTab core folder exists -------------------------------

if ($SelfTest) {
    Add-Result -Title "EnneadTab folder is in place" -Status FAIL `
        -Detail "SELF-TEST: simulating missing core folder" `
        -NextStep "Re-run the EnneadTab OS Installer (Installation\EnneadTab_OS_Installer.exe)."
} else {
    if (Test-Path -LiteralPath $CoreFolder) {
        $coreFiles = @(Get-ChildItem -LiteralPath $CoreFolder -File -ErrorAction SilentlyContinue)
        if ($coreFiles.Count -ge 10) {
            Add-Result -Title "EnneadTab folder is in place" -Status OK `
                -Detail "Found $CoreFolder (with $($coreFiles.Count) library files)."
        } else {
            Add-Result -Title "EnneadTab folder is in place" -Status FAIL `
                -Detail "Folder $CoreFolder exists but only has $($coreFiles.Count) files (expected dozens)." `
                -NextStep "Run Installation\EnneadTab_OS_Installer.exe to refresh the install."
        }
    } else {
        Add-Result -Title "EnneadTab folder is in place" -Status FAIL `
            -Detail "Cannot find $CoreFolder. EnneadTab is not installed for this user." `
            -NextStep "Run Installation\EnneadTab_OS_Installer.exe to install EnneadTab."
    }
}

# --- Check 2: How recently the install was refreshed ---------------------
# The OS installer drops a "<timestamp>.duck" marker into the Ecosystem
# folder each time it copies a fresh EA_Dist. If the newest marker is more
# than 7 days old, the auto-updater hasn't run successfully recently.

if ($SelfTest) {
    Add-Result -Title "EnneadTab is up to date (auto-updater ran recently)" -Status WARN `
        -Detail "SELF-TEST: simulating stale install (newest marker 30 days old)" `
        -NextStep "Open Task Scheduler and look for EnneadTab_OS_Installer_Task. Right-click it and choose Run."
} elseif (-not (Test-Path -LiteralPath $EcoSysFolder)) {
    Add-Result -Title "EnneadTab is up to date (auto-updater ran recently)" -Status SKIP `
        -Detail "Skipped because the EnneadTab Ecosystem folder is missing (see check above)." `
        -NextStep "Fix the missing folder first, then re-run this doctor."
} else {
    $duckMarkers = @(Get-ChildItem -LiteralPath $EcoSysFolder -Filter '*.duck' -File -ErrorAction SilentlyContinue |
                    Sort-Object LastWriteTime -Descending)
    if ($duckMarkers.Count -eq 0) {
        Add-Result -Title "EnneadTab is up to date (auto-updater ran recently)" -Status WARN `
            -Detail "No update markers (*.duck) found in $EcoSysFolder. The auto-updater has never recorded a successful sync on this machine." `
            -NextStep "Open Task Scheduler, find EnneadTab_OS_Installer_Task, and right-click > Run."
    } else {
        $newest = $duckMarkers[0]
        $age = (Get-Date) - $newest.LastWriteTime
        $ageStr = if ($age.TotalDays -ge 1) { "{0:N1} days ago" -f $age.TotalDays } else { "{0:N1} hours ago" -f $age.TotalHours }
        if ($age.TotalDays -gt 7) {
            Add-Result -Title "EnneadTab is up to date (auto-updater ran recently)" -Status WARN `
                -Detail "Newest update marker is $ageStr ($($newest.Name)). EnneadTab updates roughly every few hours, so this is unusually stale." `
                -NextStep "Check Task Scheduler for EnneadTab_OS_Installer_Task. Right-click > Run. If it errors, email designtech@ennead.com."
        } else {
            Add-Result -Title "EnneadTab is up to date (auto-updater ran recently)" -Status OK `
                -Detail "Newest update marker is $ageStr ($($newest.Name))."
        }
    }
}

# --- Check 3: pyRevit installed and master clone exists ------------------

if ($SelfTest) {
    Add-Result -Title "pyRevit is installed" -Status FAIL `
        -Detail "SELF-TEST: simulating missing pyrevit.exe" `
        -NextStep "Install pyRevit from https://pyrevitlabs.io/, then run Installation\EnneadTab_For_Revit_Installer.exe."
} else {
    $pyrevitCli = Join-Path $env:APPDATA 'pyRevit-Master\bin\pyrevit.exe'
    if (Test-Path -LiteralPath $pyrevitCli) {
        Add-Result -Title "pyRevit is installed" -Status OK `
            -Detail "Found pyRevit CLI at $pyrevitCli."
    } else {
        Add-Result -Title "pyRevit is installed" -Status FAIL `
            -Detail "pyRevit CLI not found at $pyrevitCli. EnneadTab for Revit cannot work without pyRevit." `
            -NextStep "Install pyRevit from https://pyrevitlabs.io/, then run Installation\EnneadTab_For_Revit_Installer.exe."
    }
}

# --- Check 4: EnneadTab Revit extension is registered with pyRevit -------

if ($SelfTest) {
    Add-Result -Title "EnneadTab Revit extension is registered" -Status FAIL `
        -Detail "SELF-TEST: simulating extension not registered" `
        -NextStep "Run Installation\EnneadTab_For_Revit_Installer.exe."
} else {
    # pyRevit registers EnneadTab as an extension SEARCH PATH (not a copied
    # folder) inside %APPDATA%\pyRevit\pyRevit_config.ini under
    #     [core] userextensions = ["...path..."]
    # On a normal user machine the path points at EA_Dist\Apps\_revit; on a
    # developer machine it points at the repo. We check that the line is
    # present AND that the path on disk has EnneaDuck.extension.
    $configIni = Join-Path $env:APPDATA 'pyRevit\pyRevit_config.ini'
    $pyrevitCli = Join-Path $env:APPDATA 'pyRevit-Master\bin\pyrevit.exe'
    if (-not (Test-Path -LiteralPath $pyrevitCli)) {
        Add-Result -Title "EnneadTab Revit extension is registered" -Status SKIP `
            -Detail "Skipped because pyRevit CLI is missing (see check above)." `
            -NextStep "Install pyRevit first."
    } elseif (-not (Test-Path -LiteralPath $configIni)) {
        Add-Result -Title "EnneadTab Revit extension is registered" -Status FAIL `
            -Detail "pyRevit config file not found at $configIni. pyRevit has never been launched against this user profile, or the config was deleted." `
            -NextStep "Open Revit once to let pyRevit initialize its config, then run Installation\EnneadTab_For_Revit_Installer.exe."
    } else {
        $iniText = Get-Content -LiteralPath $configIni -Raw -ErrorAction SilentlyContinue
        # Match userextensions = [...] - capture the bracketed list.
        # The list contains one or more JSON-style quoted Windows paths with
        # double-backslash escapes. We look for a path that ends in _revit
        # (the EnneadTab pyRevit extensions root) regardless of which prefix
        # (EA_Dist or a developer repo).
        $registered = $false
        $registeredPath = ''
        if ($iniText -and $iniText -match '(?ms)^\s*userextensions\s*=\s*(\[[^\]]*\])') {
            $listRaw = $matches[1]
            # Pull each quoted entry out. PowerShell regex on a literal -
            # we are matching a literal double-quote in a quoted PS string,
            # so the backtick-quote escape is correct here.
            $entries = [regex]::Matches($listRaw, '"([^"]+)"') | ForEach-Object {
                # Convert escaped \\ back to single \ for filesystem checks.
                $_.Groups[1].Value -replace '\\\\', '\'
            }
            foreach ($entry in $entries) {
                $candidate = Join-Path $entry 'EnneaDuck.extension'
                if (Test-Path -LiteralPath $candidate) {
                    $registered     = $true
                    $registeredPath = $entry
                    break
                }
            }
        }
        if ($registered) {
            Add-Result -Title "EnneadTab Revit extension is registered" -Status OK `
                -Detail "pyRevit_config.ini lists EnneadTab extension search path: $registeredPath"
        } else {
            $eaDistExt = Join-Path $AppsFolder '_revit\EnneaDuck.extension'
            $detail = "No EnneadTab extension search path found in pyRevit_config.ini."
            if (Test-Path -LiteralPath $eaDistExt) {
                $detail += " The extension folder exists at $eaDistExt but pyRevit is not pointing at it."
            }
            Add-Result -Title "EnneadTab Revit extension is registered" -Status FAIL `
                -Detail $detail `
                -NextStep "Run Installation\EnneadTab_For_Revit_Installer.exe to re-register the extension."
        }
    }
}

# --- Check 5: Critical Task Scheduler entries are healthy ----------------
# We use schtasks /query (ships with Windows, no module needed) and parse
# the CSV output rather than the human-readable form.

# These task names match Apps/lib/EnneadTab/SYSTEM.py APPS list (active=True
# only). Split into "core" and "recent": recent-additions get WARN instead
# of FAIL on missing, because users whose EA_Dist hasn't synced lately won't
# have them yet (the auto-updater check will already flag that).
$expectedTasksCore = @(
    'EnneadTab_OS_Installer_Task',
    'EnneadTab_Rhino8RuiUpdater_Task',
    'WhatTheLunch_Daily'
)
$expectedTasksRecent = @(
    'EnneadTab_InfraWatch_Collect_Task'
)
$expectedTasks = $expectedTasksCore + $expectedTasksRecent

if ($SelfTest) {
    Add-Result -Title "Background tasks are scheduled" -Status WARN `
        -Detail "SELF-TEST: simulating 1 missing task and 1 task that has not run in 3 days" `
        -NextStep "Open Task Scheduler. Look for entries starting with EnneadTab_. Right-click > Run any that show 'Never run'."
} else {
    try {
        $csv = & schtasks.exe /query /fo CSV /v 2>$null
    } catch { $csv = $null }

    if (-not $csv) {
        Add-Result -Title "Background tasks are scheduled" -Status SKIP `
            -Detail "Could not query Task Scheduler (schtasks returned nothing). This sometimes means policy restricts schtasks for this user." `
            -NextStep "Email designtech@ennead.com and mention 'schtasks blocked'."
    } else {
        $tasks = $csv | ConvertFrom-Csv
        $missingCore   = New-Object System.Collections.Generic.List[string]
        $missingRecent = New-Object System.Collections.Generic.List[string]
        $stale         = New-Object System.Collections.Generic.List[string]
        $okList        = New-Object System.Collections.Generic.List[string]
        foreach ($name in $expectedTasks) {
            $t = $tasks | Where-Object { $_.TaskName -like "*\$name" -or $_.TaskName -eq $name } | Select-Object -First 1
            if (-not $t) {
                if ($expectedTasksRecent -contains $name) { $missingRecent.Add($name) }
                else { $missingCore.Add($name) }
                continue
            }
            $lastRun = $t.'Last Run Time'
            if (-not $lastRun -or $lastRun -match 'Never|N/A' -or $lastRun -eq '1999-11-30 0:00:00') {
                $stale.Add("$name (never run)")
                continue
            }
            try {
                $lastDt = [DateTime]::Parse($lastRun)
                $age = (Get-Date) - $lastDt
                if ($age.TotalDays -gt 3) {
                    $stale.Add("$name (last ran $([int]$age.TotalDays) days ago)")
                } else {
                    $okList.Add($name)
                }
            } catch {
                $stale.Add("$name (could not parse last-run time '$lastRun')")
            }
        }
        if ($missingCore.Count -eq 0 -and $missingRecent.Count -eq 0 -and $stale.Count -eq 0) {
            Add-Result -Title "Background tasks are scheduled" -Status OK `
                -Detail "All $($expectedTasks.Count) expected tasks are present and ran recently."
        } elseif ($missingCore.Count -gt 0) {
            $detail = "Missing core tasks: $($missingCore -join ', ')"
            if ($missingRecent.Count -gt 0) { $detail += "`nAlso missing (recently added): $($missingRecent -join ', ')" }
            if ($stale.Count -gt 0) { $detail += "`nStale tasks: $($stale -join ', ')" }
            Add-Result -Title "Background tasks are scheduled" -Status FAIL `
                -Detail $detail `
                -NextStep "Run Installation\EnneadTab_OS_Installer.exe (it re-registers all background tasks)."
        } elseif ($stale.Count -gt 0) {
            $detail = "Stale tasks: $($stale -join ', ')"
            if ($missingRecent.Count -gt 0) { $detail += "`nMissing (recently added): $($missingRecent -join ', ')" }
            Add-Result -Title "Background tasks are scheduled" -Status WARN `
                -Detail $detail `
                -NextStep "Open Task Scheduler. Right-click each stale task and choose Run. If they fail, email designtech@ennead.com with this report."
        } else {
            # Only recent tasks missing - almost certainly because auto-updater hasn't synced.
            Add-Result -Title "Background tasks are scheduled" -Status WARN `
                -Detail "Recently-added tasks not yet on this machine: $($missingRecent -join ', '). The OS installer will create them next time it runs." `
                -NextStep "If the auto-updater check above is OK, no action needed. Otherwise run Installation\EnneadTab_OS_Installer.exe."
        }
    }
}

# --- Check 6: enneadtab.com is reachable ---------------------------------
# EnneadTab uses enneadtab.com for AI features, error reporting,
# InfraWatch ingest, and auth. If the host is unreachable, those features
# silently degrade.

if ($SelfTest) {
    Add-Result -Title "enneadtab.com is reachable" -Status FAIL `
        -Detail "SELF-TEST: simulating no network reach" `
        -NextStep "Check your internet/VPN. Once back online, AI and cloud features will resume automatically."
} else {
    $reach = $false
    $detailMsg = ''
    try {
        # Test-NetConnection is rich but slow; a Test-Connection ping is faster
        # and good enough for "is the host responding". HTTPS check follows
        # only if ping succeeds.
        $resp = Invoke-WebRequest -Uri 'https://enneadtab.com' -Method Head -TimeoutSec 8 -UseBasicParsing -ErrorAction Stop
        if ($resp.StatusCode -ge 200 -and $resp.StatusCode -lt 500) {
            $reach = $true
            $detailMsg = "HTTPS HEAD returned $($resp.StatusCode)."
        } else {
            $detailMsg = "HTTPS HEAD returned unexpected status $($resp.StatusCode)."
        }
    } catch {
        $detailMsg = "HTTPS to enneadtab.com failed: $($_.Exception.Message)"
    }
    if ($reach) {
        Add-Result -Title "enneadtab.com is reachable" -Status OK -Detail $detailMsg
    } else {
        Add-Result -Title "enneadtab.com is reachable" -Status WARN `
            -Detail $detailMsg `
            -NextStep "Check internet/VPN. EnneadTab will keep working in offline mode but AI and cloud features will be unavailable until you reconnect."
    }
}

# --- Check 7: Dump folder is writable (offline-mode safety net) ----------

if ($SelfTest) {
    Add-Result -Title "Local cache folder is writable" -Status FAIL `
        -Detail "SELF-TEST: simulating non-writable Dump folder" `
        -NextStep "Email designtech@ennead.com. Mention disk permissions on $DumpFolder."
} else {
    if (-not (Test-Path -LiteralPath $DumpFolder)) {
        Add-Result -Title "Local cache folder is writable" -Status WARN `
            -Detail "Dump folder $DumpFolder does not exist yet (it will be created next time EnneadTab runs)." `
            -NextStep "No action needed. If this persists after using EnneadTab, email designtech@ennead.com."
    } else {
        $probe = Join-Path $DumpFolder ('.doctor-write-probe-' + [guid]::NewGuid().ToString('N') + '.tmp')
        try {
            'probe' | Set-Content -LiteralPath $probe -Encoding ASCII -ErrorAction Stop
            Remove-Item -LiteralPath $probe -Force -ErrorAction SilentlyContinue
            Add-Result -Title "Local cache folder is writable" -Status OK `
                -Detail "Successfully wrote and removed a test file in $DumpFolder."
        } catch {
            Add-Result -Title "Local cache folder is writable" -Status FAIL `
                -Detail "Cannot write to $DumpFolder. Reason: $($_.Exception.Message)" `
                -NextStep "Email designtech@ennead.com. Mention disk permissions on $DumpFolder."
        }
    }
}

# --- Check 8: Recent error/journal logs are not enormous -----------------
# Per memory feedback_audit_gaps_ai_render_2026_04_22 - a 151 GB journal
# from an error-loop incident is a real failure mode. We sample journal
# folders under %TEMP% and pyRevit log folders.

if ($SelfTest) {
    Add-Result -Title "Error log size looks sane" -Status WARN `
        -Detail "SELF-TEST: simulating a 200 MB Revit journal file" `
        -NextStep "Close Revit. Delete the oversized journal file and restart Revit."
} else {
    $logCheckFindings = New-Object System.Collections.Generic.List[string]
    $logSizeWarnBytes = 100MB
    $logSizeFailBytes = 1GB

    # Revit journal files live under %LOCALAPPDATA%\Autodesk\Revit\Autodesk Revit <yr>\Journals\
    $revitJournalsRoot = Join-Path $env:LOCALAPPDATA 'Autodesk\Revit'
    if (Test-Path -LiteralPath $revitJournalsRoot) {
        $journals = @(Get-ChildItem -LiteralPath $revitJournalsRoot -Recurse -File `
                                   -Filter 'journal.*.txt' -ErrorAction SilentlyContinue |
                       Sort-Object Length -Descending | Select-Object -First 5)
        foreach ($j in $journals) {
            if ($j.Length -ge $logSizeWarnBytes) {
                $logCheckFindings.Add(("{0} ({1:N0} MB)" -f $j.FullName, ($j.Length/1MB)))
            }
        }
    }

    # pyRevit runner logs (PyRevitRunner*.txt and pyrevit*.log)
    $pyrevitLogs = @(Get-ChildItem -Path "$env:TEMP" -Filter 'PyRevitRunner*.txt' -File -ErrorAction SilentlyContinue) +
                  @(Get-ChildItem -Path "$env:TEMP" -Filter 'pyrevit*.log'        -File -ErrorAction SilentlyContinue)
    foreach ($l in $pyrevitLogs) {
        if ($l.Length -ge $logSizeWarnBytes) {
            $logCheckFindings.Add(("{0} ({1:N0} MB)" -f $l.FullName, ($l.Length/1MB)))
        }
    }

    if ($logCheckFindings.Count -eq 0) {
        Add-Result -Title "Error log size looks sane" -Status OK `
            -Detail "No oversized Revit journal or pyRevit log files found."
    } else {
        $maxFinding = $logCheckFindings |
            ForEach-Object {
                if ($_ -match '\(([\d,]+) MB\)') { [int]([regex]::Replace($matches[1], ',', '')) } else { 0 }
            } | Sort-Object -Descending | Select-Object -First 1
        $status = if ($maxFinding -ge 1000) { 'FAIL' } else { 'WARN' }
        $detail = "Oversized log files (>=100 MB):`n  - " + ($logCheckFindings -join "`n  - ")
        $next   = "Close Revit and delete the oversized files listed above. They usually mean a runaway error loop. If it returns, email designtech@ennead.com with this report."
        Add-Result -Title "Error log size looks sane" -Status $status -Detail $detail -NextStep $next
    }
}

# --- Check 9: Python engine venv is intact -------------------------------

if ($SelfTest) {
    Add-Result -Title "EnneadTab Python engine is intact" -Status FAIL `
        -Detail "SELF-TEST: simulating missing python.exe in _engine" `
        -NextStep "Run Installation\EnneadTab_OS_Installer.exe."
} else {
    if (-not (Test-Path -LiteralPath $EngineFolder)) {
        Add-Result -Title "EnneadTab Python engine is intact" -Status WARN `
            -Detail "Engine folder $EngineFolder is missing. Some EnneadTab features (mainly AI tooling) will not work." `
            -NextStep "Run Installation\EnneadTab_OS_Installer.exe."
    } else {
        $pyExe   = Join-Path $EngineFolder 'python.exe'
        $pyDll   = @(Get-ChildItem -LiteralPath $EngineFolder -Filter 'python3*.dll' -File -ErrorAction SilentlyContinue) | Select-Object -First 1
        if (-not (Test-Path -LiteralPath $pyExe)) {
            Add-Result -Title "EnneadTab Python engine is intact" -Status FAIL `
                -Detail "Engine folder exists but python.exe is missing at $pyExe." `
                -NextStep "Run Installation\EnneadTab_OS_Installer.exe."
        } elseif (-not $pyDll) {
            Add-Result -Title "EnneadTab Python engine is intact" -Status FAIL `
                -Detail "Engine folder has python.exe but no python3*.dll alongside. The runtime will fail to load." `
                -NextStep "Run Installation\EnneadTab_OS_Installer.exe."
        } else {
            Add-Result -Title "EnneadTab Python engine is intact" -Status OK `
                -Detail "Found python.exe and $($pyDll.Name) in $EngineFolder."
        }
    }
}

# --- Check 10: Shipped EXEs are present and not zero-byte ----------------
# We sample a small set of "must-have" EXEs that the SYSTEM.py APPS list
# relies on. We do not validate hashes against exe_hash.json - that is
# the installer's job. We just make sure the files are there and not
# truncated to zero bytes (a common interrupted-copy symptom).

if ($SelfTest) {
    Add-Result -Title "Background-task EXE files are present" -Status FAIL `
        -Detail "SELF-TEST: simulating one missing EXE and one 0-byte EXE" `
        -NextStep "Run Installation\EnneadTab_OS_Installer.exe."
} else {
    # Core EXEs that have been in EA_Dist for many months. Missing -> FAIL.
    $coreExes = @(
        'EnneadTab_OS_Installer.exe',
        'Rhino8RuiUpdater.exe',
        'ClearRevitRhinoCache.exe',
        'WhatTheLunch.exe',
        'Messenger.exe'
    )
    # Recently-added EXEs (post-2026-04-15). Missing -> WARN, because users
    # whose EA_Dist auto-updater hasn't synced lately legitimately won't
    # have these yet (the auto-updater check above will already flag that).
    $recentExes = @(
        'InfraWatch_Collect.exe'
    )
    if (-not (Test-Path -LiteralPath $ExeFolder)) {
        Add-Result -Title "Background-task EXE files are present" -Status FAIL `
            -Detail "ExeProducts folder $ExeFolder does not exist. EnneadTab background tasks cannot run." `
            -NextStep "Run Installation\EnneadTab_OS_Installer.exe."
    } else {
        $missingCore   = New-Object System.Collections.Generic.List[string]
        $missingRecent = New-Object System.Collections.Generic.List[string]
        $empty         = New-Object System.Collections.Generic.List[string]
        foreach ($e in $coreExes) {
            $p = Join-Path $ExeFolder $e
            if (-not (Test-Path -LiteralPath $p)) { $missingCore.Add($e); continue }
            $f = Get-Item -LiteralPath $p
            if ($f.Length -lt 10240) { $empty.Add("$e ($($f.Length) bytes)") }
        }
        foreach ($e in $recentExes) {
            $p = Join-Path $ExeFolder $e
            if (-not (Test-Path -LiteralPath $p)) { $missingRecent.Add($e); continue }
            $f = Get-Item -LiteralPath $p
            if ($f.Length -lt 10240) { $empty.Add("$e ($($f.Length) bytes)") }
        }
        if ($missingCore.Count -eq 0 -and $missingRecent.Count -eq 0 -and $empty.Count -eq 0) {
            $allCount = $coreExes.Count + $recentExes.Count
            Add-Result -Title "Background-task EXE files are present" -Status OK `
                -Detail "All $allCount sampled EXEs exist and are non-trivial in size."
        } elseif ($missingCore.Count -gt 0 -or $empty.Count -gt 0) {
            $detail = ''
            if ($missingCore.Count -gt 0)   { $detail += "Missing core EXEs: $($missingCore -join ', ')" }
            if ($missingRecent.Count -gt 0) {
                if ($detail) { $detail += "`n" }
                $detail += "Also missing (recently added): $($missingRecent -join ', ')"
            }
            if ($empty.Count -gt 0) {
                if ($detail) { $detail += "`n" }
                $detail += "Suspiciously small (<10 KB): $($empty -join ', ')"
            }
            Add-Result -Title "Background-task EXE files are present" -Status FAIL `
                -Detail $detail `
                -NextStep "Run Installation\EnneadTab_OS_Installer.exe."
        } else {
            # Only recently-added EXEs are missing. Almost certainly because
            # the auto-updater hasn't synced yet on this machine.
            Add-Result -Title "Background-task EXE files are present" -Status WARN `
                -Detail "Recently-added EXEs not yet on this machine: $($missingRecent -join ', '). The auto-updater will fetch them next time it syncs." `
                -NextStep "If the auto-updater check above is OK, no action needed - just wait. Otherwise run Installation\EnneadTab_OS_Installer.exe to force a sync."
        }
    }
}

# --- Check 11: OneDrive sync state of Documents (EnneadTab Ecosystem) ----
# OneDrive paused or in error state often blocks pyRevit imports because
# files become online-only placeholders. We don't try to control OneDrive,
# we just look for the official taskbar icon process and warn if its
# status is anything but RUNNING.

if ($SelfTest) {
    Add-Result -Title "OneDrive is healthy" -Status WARN `
        -Detail "SELF-TEST: simulating OneDrive paused" `
        -NextStep "Click the cloud icon in your taskbar > Resume sync."
} else {
    $oneDriveProc = Get-Process -Name 'OneDrive' -ErrorAction SilentlyContinue
    if (-not $oneDriveProc) {
        Add-Result -Title "OneDrive is healthy" -Status SKIP `
            -Detail "OneDrive process is not running. If you don't use OneDrive, this is expected and you can ignore." `
            -NextStep "Only act if you ARE supposed to be on OneDrive: open OneDrive from the Start menu and sign in."
    } else {
        # We can't programmatically read sync state without OneDrive's
        # internal RPC. The most reliable user-mode signal is "is the
        # ecosystem folder a placeholder?". If it is, the sync engine
        # has it as cloud-only, which breaks pyRevit imports.
        $isOk = $true
        $why = ''
        if (Test-Path -LiteralPath $EcoSysFolder) {
            $attr = (Get-Item -LiteralPath $EcoSysFolder -Force).Attributes.ToString()
            # Cloud-only placeholders carry the Offline flag in modern OneDrive.
            if ($attr -match 'Offline' -or $attr -match 'RecallOnDataAccess' -or $attr -match 'RecallOnOpen') {
                $isOk = $false
                $why = "EnneadTab Ecosystem folder is a OneDrive cloud-only placeholder (attributes: $attr). pyRevit will fail to import its files."
            }
        }
        if ($isOk) {
            Add-Result -Title "OneDrive is healthy" -Status OK `
                -Detail "OneDrive is running and the EnneadTab folder is fully on disk."
        } else {
            Add-Result -Title "OneDrive is healthy" -Status WARN `
                -Detail $why `
                -NextStep "Right-click the EnneadTab Ecosystem folder in File Explorer and choose 'Always keep on this device'."
        }
    }
}

# --- Summary -------------------------------------------------------------

Write-Line ''
Write-Line ('=' * 67) Cyan
Write-Line "Summary" Cyan
Write-Line ('=' * 67) Cyan

# Wrap Where-Object results in @(...) so .Count works on single-element
# result sets - PowerShell 5.1 unwraps a single hashtable and `.Count` on
# a hashtable returns the number of keys (5), not 1. Classic gotcha.
$pass = @($script:CheckResults | Where-Object { $_.Status -eq 'OK'   }).Count
$warn = @($script:CheckResults | Where-Object { $_.Status -eq 'WARN' }).Count
$fail = @($script:CheckResults | Where-Object { $_.Status -eq 'FAIL' }).Count
$skip = @($script:CheckResults | Where-Object { $_.Status -eq 'SKIP' }).Count

Write-Line ("Passed:   {0}" -f $pass) Green
if ($warn -gt 0) { Write-Line ("Warnings: {0}" -f $warn) Yellow } else { Write-Line "Warnings: 0" }
if ($fail -gt 0) { Write-Line ("Failed:   {0}" -f $fail) Red }    else { Write-Line "Failed:   0" }
if ($skip -gt 0) { Write-Line ("Skipped:  {0}" -f $skip) DarkGray } else { Write-Line "Skipped:  0" }

if ($fail -gt 0 -or $warn -gt 0) {
    Write-Line ''
    Write-Line "What to do next" Magenta
    Write-Line ('-' * 67) Magenta
    foreach ($r in $script:CheckResults) {
        if ($r.Status -eq 'FAIL' -or $r.Status -eq 'WARN') {
            Write-Line ("[{0}] {1}" -f $r.Status, $r.Title) Magenta
            if ($r.NextStep) { Write-Line ("  -> {0}" -f $r.NextStep) Magenta }
        }
    }
}

Write-Line ''
Write-Line "If you are emailing for help, attach this whole report file:" DarkGray
Write-Line "    $ReportFile" DarkGray
Write-Line "Send to: designtech@ennead.com" DarkGray
Write-Line ''

# --- Persist report ------------------------------------------------------
try {
    $reportDir = Split-Path -Parent $ReportFile
    if (-not (Test-Path -LiteralPath $reportDir)) {
        New-Item -ItemType Directory -Path $reportDir -Force | Out-Null
    }
    # Use System.IO so we get UTF-8 without BOM regardless of PS edition.
    $utf8NoBom = New-Object System.Text.UTF8Encoding($false)
    [System.IO.File]::WriteAllLines($ReportFile, $script:ReportLines, $utf8NoBom)
} catch {
    Write-Host "WARNING: could not save report to $ReportFile : $($_.Exception.Message)" -ForegroundColor Red
}

# --- Exit code ----------------------------------------------------------
# 0 when everything is OK or only WARN/SKIP. Non-zero only when at least
# one FAIL exists, so a wrapper script could detect "this user definitely
# needs help".
if ($fail -gt 0) { exit 1 } else { exit 0 }
