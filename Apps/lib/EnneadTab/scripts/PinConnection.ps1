# Helper function to get EnneadTab DB folder path
function Get-EnneadTabDBFolder {
    $currentDate = Get-Date
    $cutoffDate = Get-Date -Year 2025 -Month 7 -Day 15
    $currentUser = $env:USERNAME
    
    if ($currentDate -ge $cutoffDate -or $currentUser -eq "szhang") {
        return "L:\4b_Design Technology\05_EnneadTab-DB"
    } else {
        return "L:\4b_Applied Computing\EnneadTab-DB"
    }
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