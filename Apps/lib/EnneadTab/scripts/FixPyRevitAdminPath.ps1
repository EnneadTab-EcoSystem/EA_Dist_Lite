#Requires -Version 3.0
<#
.SYNOPSIS
    Fixes pyRevit.addin files by replacing Administrator paths with current user paths.
    
.DESCRIPTION
    This script automatically requests admin elevation and fixes pyRevit.addin files 
    across all Revit versions in ProgramData by replacing Administrator AppData paths 
    with the current logged-in user's AppData path.
    
    Only modifies files named exactly "pyRevit.addin" (case-sensitive).
    Skips files that are already using the correct path.
    
.PARAMETER None
    
.EXAMPLE
    .\FixPyRevitAdminPath.ps1
    Double-click the script or run from PowerShell. UAC prompt will appear if not admin.
#>

# Set error action preference
$ErrorActionPreference = "Continue"

# Get current username
$currentUsername = $env:USERNAME

# Check if current user is Administrator (would cause infinite loop)
if ($currentUsername -eq "Administrator") {
    Write-Host "`nWARNING: Current user is 'Administrator'. No replacement needed." -ForegroundColor Yellow
    Write-Host "Press any key to exit..."
    $null = $Host.UI.RawUI.ReadKey("NoEcho,IncludeKeyDown")
    exit 0
}

# Function to check if running as administrator
function Test-Administrator {
    $currentUser = [Security.Principal.WindowsIdentity]::GetCurrent()
    $principal = New-Object Security.Principal.WindowsPrincipal($currentUser)
    return $principal.IsInRole([Security.Principal.WindowsBuiltInRole]::Administrator)
}

# Function to elevate script if not running as admin
function Request-AdminElevation {
    if (-not (Test-Administrator)) {
        Write-Host "`nThis script requires administrator privileges to modify files in ProgramData." -ForegroundColor Yellow
        Write-Host "Requesting elevation..." -ForegroundColor Yellow
        
        try {
            # Re-launch script with admin privileges
            $scriptPath = $MyInvocation.PSCommandPath
            $processInfo = New-Object System.Diagnostics.ProcessStartInfo
            $processInfo.FileName = "powershell.exe"
            $processInfo.Arguments = "-ExecutionPolicy Bypass -NoProfile -File `"$scriptPath`""
            $processInfo.Verb = "runas"
            $processInfo.UseShellExecute = $true
            
            $process = [System.Diagnostics.Process]::Start($processInfo)
            exit 0
        }
        catch {
            Write-Host "`nERROR: Failed to elevate privileges. Please run this script as Administrator manually." -ForegroundColor Red
            Write-Host "Right-click the script and select 'Run as administrator'" -ForegroundColor Yellow
            Write-Host "`nPress any key to exit..."
            $null = $Host.UI.RawUI.ReadKey("NoEcho,IncludeKeyDown")
            exit 1
        }
    }
}

# Request admin elevation if needed
Request-AdminElevation

# Verify we're now running as admin
if (-not (Test-Administrator)) {
    Write-Host "`nERROR: Still not running as administrator. Exiting." -ForegroundColor Red
    Write-Host "Press any key to exit..."
    $null = $Host.UI.RawUI.ReadKey("NoEcho,IncludeKeyDown")
    exit 1
}

Write-Host "`n========================================" -ForegroundColor Cyan
Write-Host "  Fix PyRevit Admin Path Script" -ForegroundColor Cyan
Write-Host "========================================" -ForegroundColor Cyan
Write-Host "Running as Administrator: Yes" -ForegroundColor Green
Write-Host "Current User: $currentUsername" -ForegroundColor Green
Write-Host ""

# Define paths
$addinsBasePath = "C:\ProgramData\Autodesk\Revit\Addins"
$targetFileName = "pyRevit.addin"  # Exact match, case-sensitive

# Check if Addins folder exists
if (-not (Test-Path $addinsBasePath)) {
    Write-Host "ERROR: Addins folder not found: $addinsBasePath" -ForegroundColor Red
    Write-Host "Press any key to exit..."
    $null = $Host.UI.RawUI.ReadKey("NoEcho,IncludeKeyDown")
    exit 1
}

# Get all version folders
$versionFolders = Get-ChildItem -Path $addinsBasePath -Directory -ErrorAction SilentlyContinue | 
    Where-Object { $_.Name -match '^\d{4}$' } | 
    Sort-Object Name

if ($versionFolders.Count -eq 0) {
    Write-Host "No Revit version folders found in: $addinsBasePath" -ForegroundColor Yellow
    Write-Host "Press any key to exit..."
    $null = $Host.UI.RawUI.ReadKey("NoEcho,IncludeKeyDown")
    exit 0
}

Write-Host "Found $($versionFolders.Count) Revit version folder(s)" -ForegroundColor Cyan
Write-Host ""

# Statistics
$filesFound = 0
$filesFixed = 0
$filesSkipped = 0
$filesError = 0
$processedFiles = @()

# Patterns for matching and replacement
$adminPathPattern = "C:\\Users\\Administrator\\AppData"
$adminPathPatternCaseInsensitive = [regex]::Escape("C:\Users\Administrator\AppData")
$currentUserPath = "C:\Users\$currentUsername\AppData"
$currentUserPathPattern = [regex]::Escape("C:\Users\$currentUsername\AppData")

# Function to check if file is already fixed
function Test-FileAlreadyFixed {
    param([string]$fileContent)
    
    # Check if file already contains current username path (case-insensitive)
    if ($fileContent -match $currentUserPathPattern -and $fileContent -notmatch $adminPathPatternCaseInsensitive) {
        return $true
    }
    return $false
}

# Function to safely read file with retry
function Read-FileWithRetry {
    param(
        [string]$filePath,
        [int]$maxRetries = 3
    )
    
    for ($attempt = 1; $attempt -le $maxRetries; $attempt++) {
        try {
            # Try to read the file
            $content = Get-Content -Path $filePath -Raw -Encoding UTF8 -ErrorAction Stop
            return $content
        }
        catch {
            if ($attempt -lt $maxRetries) {
                $delay = [math]::Pow(2, $attempt - 1)  # Exponential backoff: 1s, 2s, 4s
                Write-Host "  File locked (attempt $attempt/$maxRetries), retrying in $delay seconds..." -ForegroundColor Yellow
                Start-Sleep -Seconds $delay
            }
            else {
                throw
            }
        }
    }
}

# Function to safely write file with retry
function Write-FileWithRetry {
    param(
        [string]$filePath,
        [string]$content,
        [int]$maxRetries = 3
    )
    
    for ($attempt = 1; $attempt -le $maxRetries; $attempt++) {
        try {
            # Remove read-only attribute if present
            if (Test-Path $filePath) {
                $fileItem = Get-Item $filePath
                if ($fileItem.IsReadOnly) {
                    Set-ItemProperty -Path $filePath -Name IsReadOnly -Value $false -ErrorAction SilentlyContinue
                }
            }
            
            # Write file with UTF-8 encoding (no BOM to match original)
            $utf8NoBom = New-Object System.Text.UTF8Encoding $false
            [System.IO.File]::WriteAllText($filePath, $content, $utf8NoBom)
            return $true
        }
        catch {
            if ($attempt -lt $maxRetries) {
                $delay = [math]::Pow(2, $attempt - 1)  # Exponential backoff
                Write-Host "  File locked (attempt $attempt/$maxRetries), retrying in $delay seconds..." -ForegroundColor Yellow
                Start-Sleep -Seconds $delay
            }
            else {
                throw
            }
        }
    }
}

# Process each version folder
foreach ($versionFolder in $versionFolders) {
    $versionPath = $versionFolder.FullName
    $targetFile = Join-Path $versionPath $targetFileName
    
    Write-Host "Checking: $($versionFolder.Name)" -ForegroundColor Cyan
    
    # Check if pyRevit.addin exists (exact match, case-sensitive)
    if (-not (Test-Path $targetFile)) {
        Write-Host "  -> pyRevit.addin not found, skipping" -ForegroundColor Gray
        continue
    }
    
    $filesFound++
    Write-Host "  -> Found pyRevit.addin" -ForegroundColor Green
    
    try {
        # Read file content with retry
        $fileContent = Read-FileWithRetry -FilePath $targetFile
        
        # Check if file is already fixed
        if (Test-FileAlreadyFixed -fileContent $fileContent) {
            Write-Host "  -> Already using correct path ($currentUsername), skipping" -ForegroundColor Yellow
            $filesSkipped++
            $processedFiles += [PSCustomObject]@{
                Version = $versionFolder.Name
                File = $targetFile
                Status = "Skipped (already fixed)"
            }
            continue
        }
        
        # Check if file contains Administrator path (case-insensitive)
        if ($fileContent -notmatch $adminPathPatternCaseInsensitive) {
            Write-Host "  -> No Administrator path found, skipping" -ForegroundColor Yellow
            $filesSkipped++
            $processedFiles += [PSCustomObject]@{
                Version = $versionFolder.Name
                File = $targetFile
                Status = "Skipped (no Administrator path)"
            }
            continue
        }
        
        # Perform replacement (case-insensitive, replace all occurrences)
        $originalContent = $fileContent
        $newContent = $fileContent -replace [regex]::Escape($adminPathPattern), $currentUserPath
        
        # Verify replacement occurred
        if ($newContent -eq $originalContent) {
            Write-Host "  -> Replacement pattern not matched, skipping" -ForegroundColor Yellow
            $filesSkipped++
            $processedFiles += [PSCustomObject]@{
                Version = $versionFolder.Name
                File = $targetFile
                Status = "Skipped (pattern not matched)"
            }
            continue
        }
        
        # Write file with retry
        Write-FileWithRetry -FilePath $targetFile -Content $newContent
        
        Write-Host "  -> Fixed: Replaced Administrator path with $currentUsername path" -ForegroundColor Green
        $filesFixed++
        $processedFiles += [PSCustomObject]@{
            Version = $versionFolder.Name
            File = $targetFile
            Status = "Fixed"
        }
    }
    catch {
        Write-Host "  -> ERROR: $($_.Exception.Message)" -ForegroundColor Red
        $filesError++
        $processedFiles += [PSCustomObject]@{
            Version = $versionFolder.Name
            File = $targetFile
            Status = "Error: $($_.Exception.Message)"
        }
    }
    
    Write-Host ""
}

# Summary
Write-Host "========================================" -ForegroundColor Cyan
Write-Host "  Summary" -ForegroundColor Cyan
Write-Host "========================================" -ForegroundColor Cyan
Write-Host "Files found:        $filesFound" -ForegroundColor White
Write-Host "Files fixed:        $filesFixed" -ForegroundColor Green
Write-Host "Files skipped:      $filesSkipped" -ForegroundColor Yellow
Write-Host "Files with errors:  $filesError" -ForegroundColor $(if ($filesError -gt 0) { "Red" } else { "White" })
Write-Host ""

if ($processedFiles.Count -gt 0) {
    Write-Host "Detailed Results:" -ForegroundColor Cyan
    $processedFiles | Format-Table -AutoSize
}

Write-Host ""
Write-Host "Script completed. Press any key to exit..." -ForegroundColor Cyan
$null = $Host.UI.RawUI.ReadKey("NoEcho,IncludeKeyDown")

