# Helper function to get EnneadTab DB folder path (#2360).
# Mirrors ENVIRONMENT._resolve_shared_root precedence:
#   EA_SHARED_ROOT env var > per-user shared_root.json > EA_Dist shared_root.json
#   > legacy L: path.
function Get-EnneadTabDBFolder {
    if ($env:EA_SHARED_ROOT -and $env:EA_SHARED_ROOT.Trim() -and $env:EA_SHARED_ROOT.Trim().ToUpper() -ne "OFFLINE") {
        return (Join-Path $env:EA_SHARED_ROOT.Trim() "05_EnneadTab-DB")
    }

    $ecoSys = Join-Path $env:USERPROFILE "Documents\EnneadTab Ecosystem"
    $candidates = @(
        (Join-Path $ecoSys "shared_root.json"),
        (Join-Path $ecoSys "EA_Dist\Apps\lib\EnneadTab\shared_root.json")
    )
    foreach ($candidate in $candidates) {
        if (-not (Test-Path $candidate)) { continue }
        try {
            $config = Get-Content $candidate -Raw | ConvertFrom-Json
            if ($config.db_folder) { return $config.db_folder }
            if ($config.shared_root) { return (Join-Path $config.shared_root "05_EnneadTab-DB") }
        } catch {
            continue
        }
    }

    return "L:\4b_Design Technology\05_EnneadTab-DB"
}

$sharedFolder = Join-Path (Get-EnneadTabDBFolder) "Shared Data Dump"
$user = $env:USERNAME
$pc = $env:COMPUTERNAME
$file = "PINCONNECTION_${user}_${pc}.DuckPin"
$date = Get-Date -Format "yyyy-MM-dd HH:mm:ss"
$content = "Last check-in: $date"

try {
    Set-Content -Path (Join-Path $sharedFolder $file) -Value $content -ErrorAction Stop
}
catch {
    Add-Type -AssemblyName PresentationFramework
    [System.Windows.MessageBox]::Show("Your L drive is disconnected, please reconnect.", "Network Connection Error", "OK", "Error")
} 