<#
    EnneadTab_AutoUpdate_Doctor.ps1

    ONE-SHOT diagnostic + repair for a Cannon machine where the auto-update
    scheduled task (EnneadTab_OS_Installer_Task) "just isn't there".

    Ships and runs AS-IS -- no exe recompile.

    It does three things and writes EVERYTHING to a report file next to itself
    (so if you run it from a synced OneDrive/SharePoint folder, the report syncs
    straight back to you):

      1. INSPECT  -- machine/user/privilege, OneDrive redirect env, every
                     candidate installer path, current task state.
      2. PROBE    -- can Task Scheduler create a task AT ALL on this machine?
                     (creates a trivial throwaway task, captures the exact
                     error, deletes it.) This is what separates a GPO/policy
                     block from a wrong-path bug.
      3. REPAIR   -- register EnneadTab_OS_Installer_Task correctly and VERIFY
                     it exists. Loud on failure.

    Read-only until step 3, and step 3 only ever ADDS the intended task.
#>

$TaskName        = 'EnneadTab_OS_Installer_Task'
$ProbeTaskName   = 'EnneadTab_TaskSchedulerProbe'
$IntervalMinutes = 45
$RelInstaller    = 'EnneadTab Ecosystem\EA_Dist\Apps\lib\ExeProducts\EnneadTab_OS_Installer.exe'

# --- report file next to this script (falls back to TEMP if that dir is RO) ---
$scriptDir = Split-Path -Parent $MyInvocation.MyCommand.Path
if (-not $scriptDir) { $scriptDir = $env:TEMP }
$stamp   = (Get-Date).ToString('yyyyMMdd_HHmmss')
$reportName = "EnneadTab_AutoUpdate_Report_{0}_{1}_{2}.txt" -f $env:COMPUTERNAME, $env:USERNAME, $stamp
$reportPath = Join-Path $scriptDir $reportName
try {
    Start-Transcript -Path $reportPath -Force | Out-Null
    $transcriptOn = $true
} catch {
    $reportPath = Join-Path $env:TEMP $reportName
    Start-Transcript -Path $reportPath -Force | Out-Null
    $transcriptOn = $true
}

function Line { Write-Host ('-' * 70) }
function Section($t) { Write-Host ''; Line; Write-Host "  $t"; Line }

Write-Host ''
Write-Host '  EnneadTab :: auto-update task DOCTOR'
Write-Host "  report -> $reportPath"

# ------------------------------------------------------------- 1. INSPECT
Section '1. MACHINE / USER / PRIVILEGE'
Write-Host "  computer     : $env:COMPUTERNAME"
Write-Host "  user         : $env:USERDOMAIN\$env:USERNAME"
Write-Host "  UTC now      : $((Get-Date).ToUniversalTime().ToString('u'))"
try {
    $id = [Security.Principal.WindowsPrincipal][Security.Principal.WindowsIdentity]::GetCurrent()
    $isAdmin = $id.IsInRole([Security.Principal.WindowsBuiltInRole]::Administrator)
    Write-Host "  elevated     : $isAdmin"
} catch { Write-Host "  elevated     : (could not determine) $($_.Exception.Message)" }
Write-Host "  PS version   : $($PSVersionTable.PSVersion)"

Section '2. ONEDRIVE / KNOWN-FOLDER REDIRECT'
Write-Host "  USERPROFILE          : $env:USERPROFILE"
Write-Host "  OneDrive             : $env:OneDrive"
Write-Host "  OneDriveCommercial   : $env:OneDriveCommercial"
try { Write-Host "  MyDocuments (shell)  : $([Environment]::GetFolderPath('MyDocuments'))" } catch {}
Get-ChildItem -LiteralPath $env:USERPROFILE -Directory -Filter 'OneDrive*' -ErrorAction SilentlyContinue |
    ForEach-Object { Write-Host "  profile OneDrive dir : $($_.FullName)" }

# ------------------------------------------------ resolve installer candidates
Section '3. INSTALLER PATH CANDIDATES'
$docRoots = @(
    (Join-Path $env:USERPROFILE 'Documents'),
    [Environment]::GetFolderPath('MyDocuments')
)
if ($env:OneDrive)           { $docRoots += (Join-Path $env:OneDrive 'Documents') }
if ($env:OneDriveCommercial) { $docRoots += (Join-Path $env:OneDriveCommercial 'Documents') }
Get-ChildItem -LiteralPath $env:USERPROFILE -Directory -Filter 'OneDrive*' -ErrorAction SilentlyContinue |
    ForEach-Object { $docRoots += (Join-Path $_.FullName 'Documents') }
$docRoots = $docRoots | Where-Object { $_ } | Select-Object -Unique

$installer = $null
foreach ($root in $docRoots) {
    $candidate = Join-Path $root $RelInstaller
    $exists = Test-Path -LiteralPath $candidate
    Write-Host ("  [{0}] {1}" -f $(if ($exists) { 'FOUND  ' } else { 'missing' }), $candidate)
    if ($exists -and -not $installer) { $installer = $candidate }
}
if (-not $installer) {
    Write-Host ''
    Write-Host '  none of the expected roots held the exe -- searching profile for any copy...'
    $found = Get-ChildItem -LiteralPath $env:USERPROFILE -Recurse -File -Filter 'EnneadTab_OS_Installer.exe' -ErrorAction SilentlyContinue |
             Select-Object -First 5
    if ($found) {
        foreach ($f in $found) { Write-Host "  stray copy -> $($f.FullName)" }
        $installer = $found[0].FullName
        Write-Host "  will register against first stray copy above."
    } else {
        Write-Host '  NO EnneadTab_OS_Installer.exe anywhere under the profile.'
        Write-Host '  => EA_Dist is not installed. The task would have no program to run.'
    }
}

Section '4. CURRENT STATE OF THE AUTO-UPDATE TASK'
$existing = Get-ScheduledTask -TaskName $TaskName -ErrorAction SilentlyContinue
if ($existing) {
    $ei = Get-ScheduledTaskInfo -TaskName $TaskName -ErrorAction SilentlyContinue
    Write-Host "  task present : YES  state=$($existing.State)"
    Write-Host "  runs         : $($existing.Actions[0].Execute)"
    Write-Host "  last run     : $($ei.LastRunTime)   result=0x$('{0:X}' -f $ei.LastTaskResult)"
    Write-Host "  next run     : $($ei.NextRunTime)"
} else {
    Write-Host "  task present : NO  (this is the reported symptom)"
}

# --------------------------------------------------------------- 2. PROBE
Section '5. TASK-SCHEDULER CAPABILITY PROBE (can we create ANY task?)'
$probeOk = $false
try {
    $pAction  = New-ScheduledTaskAction -Execute 'C:\Windows\System32\cmd.exe' -Argument '/c exit'
    $pTrigger = New-ScheduledTaskTrigger -Once -At (Get-Date).AddHours(1)
    $pPrin    = New-ScheduledTaskPrincipal -UserId "$env:USERDOMAIN\$env:USERNAME" -LogonType Interactive -RunLevel Limited
    Register-ScheduledTask -TaskName $ProbeTaskName -Action $pAction -Trigger $pTrigger -Principal $pPrin -Force -ErrorAction Stop | Out-Null
    if (Get-ScheduledTask -TaskName $ProbeTaskName -ErrorAction SilentlyContinue) {
        $probeOk = $true
        Write-Host '  RESULT: SUCCESS -- this machine CAN create per-user scheduled tasks.'
        Write-Host '          => a missing task is a path/registration bug, not a policy block.'
    } else {
        Write-Host '  RESULT: registration returned but task absent -- silent rejection (AV/policy).'
    }
} catch {
    Write-Host '  RESULT: BLOCKED -- Task Scheduler creation FAILED. Exact error:'
    Write-Host "          $($_.Exception.Message)"
    Write-Host "          HRESULT/category: $($_.FullyQualifiedErrorId)"
    Write-Host '          => If this is Access denied / 0x80070005, Cannon GROUP POLICY'
    Write-Host '             blocks task creation. That is an IT ticket, not a code fix.'
} finally {
    Unregister-ScheduledTask -TaskName $ProbeTaskName -Confirm:$false -ErrorAction SilentlyContinue
}

# -------------------------------------------------------------- 3. REPAIR
Section '6. REPAIR -- register EnneadTab_OS_Installer_Task'
if (-not $installer) {
    Write-Host '  SKIPPED: no installer exe to point the task at (see section 3).'
    Write-Host '  Fix: run the EnneadTab OS installer on this machine, then re-run this doctor.'
} elseif (-not $probeOk) {
    Write-Host '  SKIPPED: capability probe shows task creation is blocked (see section 5).'
    Write-Host '  Registering the real task would fail the same way; not attempting.'
} else {
    try {
        $action = New-ScheduledTaskAction -Execute $installer   # spaces handled natively
        $trigger = New-ScheduledTaskTrigger -Once -At (Get-Date).AddMinutes(1)
        $rep = (New-ScheduledTaskTrigger -Once -At (Get-Date) `
            -RepetitionInterval (New-TimeSpan -Minutes $IntervalMinutes)).Repetition
        $rep.Duration = $null            # empty duration = repeat indefinitely
        $trigger.Repetition = $rep
        $principal = New-ScheduledTaskPrincipal -UserId "$env:USERDOMAIN\$env:USERNAME" `
            -LogonType Interactive -RunLevel Limited
        $settings = New-ScheduledTaskSettingsSet -AllowStartIfOnBatteries `
            -DontStopIfGoingOnBatteries -StartWhenAvailable -MultipleInstances IgnoreNew
        Register-ScheduledTask -TaskName $TaskName -Action $action -Trigger $trigger `
            -Principal $principal -Settings $settings -Force -ErrorAction Stop | Out-Null

        $t = Get-ScheduledTask -TaskName $TaskName -ErrorAction SilentlyContinue
        if ($t) {
            $ti = Get-ScheduledTaskInfo -TaskName $TaskName -ErrorAction SilentlyContinue
            Write-Host "  SUCCESS: task registered and VERIFIED present."
            Write-Host "  state    : $($t.State)"
            Write-Host "  runs     : $($t.Actions[0].Execute)"
            Write-Host "  every    : $IntervalMinutes minutes (indefinite)"
            Write-Host "  next run : $($ti.NextRunTime)"
        } else {
            Write-Host '  FAIL: Register returned without error but the task is NOT present.'
            Write-Host '        Something (AV/policy) silently rejected it.'
        }
    } catch {
        Write-Host '  FAIL: registration threw. Exact error (previously swallowed by the exe):'
        Write-Host "        $($_.Exception.Message)"
        Write-Host "        $($_.FullyQualifiedErrorId)"
    }
}

Section 'DONE'
Write-Host "  Full report written to:"
Write-Host "    $reportPath"
Write-Host "  Copy that file back to the shared folder / paste it to DesignTech."
Write-Host ''

if ($transcriptOn) { try { Stop-Transcript | Out-Null } catch {} }
