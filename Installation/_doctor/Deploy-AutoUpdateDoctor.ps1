<#
    Deploy-AutoUpdateDoctor.ps1   (operator tool -- YOU run this, not end users)

    The fan-out half of the drop-folder loop for the auto-update fix:

      -Stage    copy EnneadTab_AutoUpdate_Doctor.{ps1,bat} INTO a shared/drop
                folder so affected users can run the .bat from their synced copy.
      -Collect  read every EnneadTab_AutoUpdate_Report_*.txt that has come BACK
                into that folder and aggregate them into one machine-by-machine
                table + a summary .txt. Run it again whenever new reports land.

    Default (no switch) does both: stage, then collect whatever is already there.

    Example:
      .\Deploy-AutoUpdateDoctor.ps1 -Folder "C:\Users\me\OneDrive - CannonDesign\Desktop\old EA communication folder via one drive online"

    This does NOT remote-execute anything (Cannon lock-down makes that a non-
    starter). It stages the fix and harvests results through the folder both
    sides already share.
#>
[CmdletBinding()]
param(
    [Parameter(Mandatory = $true)]
    [string]$Folder,
    [switch]$Stage,
    [switch]$Collect
)

# no switch given -> do both
if (-not $Stage -and -not $Collect) { $Stage = $true; $Collect = $true }

$srcDir = Split-Path -Parent $MyInvocation.MyCommand.Path
$pair   = @('EnneadTab_AutoUpdate_Doctor.ps1', 'EnneadTab_AutoUpdate_Doctor.bat')

if (-not (Test-Path -LiteralPath $Folder)) {
    Write-Host "  FAIL: target folder does not exist: $Folder" -ForegroundColor Red
    exit 1
}

if ($Stage) {
    Write-Host ''
    Write-Host "  STAGE -> $Folder" -ForegroundColor Cyan
    foreach ($f in $pair) {
        $src = Join-Path $srcDir $f
        if (-not (Test-Path -LiteralPath $src)) { Write-Host "  missing beside me: $f" -ForegroundColor Red; continue }
        Copy-Item -LiteralPath $src -Destination $Folder -Force
        Write-Host "  copied: $f" -ForegroundColor Green
    }
    Write-Host '  Tell affected users: open the folder, double-click' -ForegroundColor Gray
    Write-Host '  EnneadTab_AutoUpdate_Doctor.bat, let it finish, leave the report .txt.' -ForegroundColor Gray
}

if ($Collect) {
    Write-Host ''
    Write-Host "  COLLECT <- $Folder" -ForegroundColor Cyan
    $reports = Get-ChildItem -LiteralPath $Folder -Filter 'EnneadTab_AutoUpdate_Report_*.txt' -ErrorAction SilentlyContinue
    if (-not $reports) { Write-Host '  no report files back yet.' -ForegroundColor Yellow; return }

    $rows = foreach ($r in $reports) {
        $t = Get-Content -LiteralPath $r.FullName -Raw

        $computer = if ($t -match 'computer\s*:\s*(\S+)') { $matches[1] } else { '?' }
        $before   = if ($t -match 'task present\s*:\s*(YES|NO)') { $matches[1] } else { '?' }

        $probe =
            if     ($t -match 'RESULT:\s*SUCCESS') { 'CAN-CREATE' }
            elseif ($t -match 'RESULT:\s*BLOCKED') { 'GPO-BLOCKED' }
            elseif ($t -match 'silent rejection')  { 'AV/POLICY-SILENT' }
            else                                   { '?' }

        # section 6 REPAIR outcome (grab the block after the REPAIR header)
        $repair = '?'
        $idx = $t.IndexOf('6. REPAIR')
        if ($idx -ge 0) {
            $tail = $t.Substring($idx)
            if     ($tail -match 'SUCCESS:\s*task registered') { $repair = 'FIXED' }
            elseif ($tail -match 'SKIPPED')                     { $repair = 'SKIPPED' }
            elseif ($tail -match 'FAIL')                        { $repair = 'FAILED' }
        }

        [pscustomobject]@{
            Machine    = $computer
            TaskBefore = $before
            CanCreate  = $probe
            Repair     = $repair
            Report     = $r.Name
        }
    }

    $rows = $rows | Sort-Object Machine -Unique
    $rows | Format-Table Machine, TaskBefore, CanCreate, Repair -AutoSize | Out-Host

    $fixed   = @($rows | Where-Object { $_.Repair -eq 'FIXED' }).Count
    $blocked = @($rows | Where-Object { $_.CanCreate -eq 'GPO-BLOCKED' }).Count
    $noExe   = @($rows | Where-Object { $_.Repair -eq 'SKIPPED' }).Count
    Write-Host ("  machines: {0}   fixed: {1}   GPO-blocked (need IT): {2}   skipped/no-exe: {3}" -f `
        $rows.Count, $fixed, $blocked, $noExe) -ForegroundColor White

    $stamp = (Get-Date).ToString('yyyyMMdd_HHmmss')
    $summaryPath = Join-Path $Folder ("_AutoUpdate_FleetSummary_{0}.txt" -f $stamp)
    $rows | Format-Table Machine, TaskBefore, CanCreate, Repair, Report -AutoSize |
        Out-File -FilePath $summaryPath -Encoding utf8
    Write-Host "  summary written: $summaryPath" -ForegroundColor Green
}
