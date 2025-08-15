param(
    [switch]$Silent
)

# EnneadTab InDesign Writer Helper - Python Installation Checker
# This script checks if Python is properly installed and configured

function Write-Status {
    param(
        [string]$Message,
        [string]$Type = "INFO"
    )
    
    if (-not $Silent) {
        switch ($Type) {
            "ERROR" { Write-Host "❌ $Message" -ForegroundColor Red }
            "SUCCESS" { Write-Host "✅ $Message" -ForegroundColor Green }
            "WARNING" { Write-Host "⚠️ $Message" -ForegroundColor Yellow }
            default { Write-Host "ℹ️ $Message" -ForegroundColor Cyan }
        }
    }
}

function Test-PythonInstallation {
    try {
        # Try to get Python version
        $pythonVersion = python --version 2>&1
        if ($LASTEXITCODE -eq 0) {
            Write-Status "Python found: $pythonVersion" "SUCCESS"
            return $true
        }
    }
    catch {
        Write-Status "Python not found in PATH" "ERROR"
        return $false
    }
    
    # Try alternative Python commands
    $pythonCommands = @("python3", "py", "python.exe")
    foreach ($cmd in $pythonCommands) {
        try {
            $version = & $cmd --version 2>&1
            if ($LASTEXITCODE -eq 0) {
                Write-Status "Python found via '$cmd': $version" "SUCCESS"
                return $true
            }
        }
        catch {
            continue
        }
    }
    
    Write-Status "Python not found. Please install Python from python.org or Microsoft Store" "ERROR"
    return $false
}

function Test-PyWin32 {
    try {
        $pywin32Test = python -c "import win32com.client; print('pywin32 available')" 2>&1
        if ($LASTEXITCODE -eq 0) {
            Write-Status "pywin32 module is available" "SUCCESS"
            return $true
        }
    }
    catch {
        Write-Status "pywin32 module not found" "WARNING"
        return $false
    }
    
    Write-Status "pywin32 module not found. Install with: pip install pywin32" "WARNING"
    return $false
}

function Test-InDesign {
    try {
        # Check if InDesign is installed by looking for the executable
        $indesignPaths = @(
            "${env:ProgramFiles}\Adobe\Adobe InDesign*\Scripts\Support Scripts\app\InDesign.exe",
            "${env:ProgramFiles(x86)}\Adobe\Adobe InDesign*\Scripts\Support Scripts\app\InDesign.exe"
        )
        
        foreach ($path in $indesignPaths) {
            $found = Get-ChildItem -Path $path -ErrorAction SilentlyContinue
            if ($found) {
                Write-Status "InDesign found at: $($found.FullName)" "SUCCESS"
                return $true
            }
        }
        
        Write-Status "InDesign not found in standard locations" "WARNING"
        return $false
    }
    catch {
        Write-Status "Error checking InDesign installation" "WARNING"
        return $false
    }
}

# Main execution
if (-not $Silent) {
    Write-Host "🔍 Checking Python installation..." -ForegroundColor White
}

$pythonOk = Test-PythonInstallation
$pywin32Ok = Test-PyWin32
$indesignOk = Test-InDesign

if ($pythonOk -and $pywin32Ok) {
    if (-not $Silent) {
        Write-Host ""
        Write-Host "✅ All checks passed! Python is ready for InDesign Writer Helper." -ForegroundColor Green
    }
    exit 0
} else {
    if (-not $Silent) {
        Write-Host ""
        Write-Host "❌ Some checks failed. Please review the issues above." -ForegroundColor Red
    }
    exit 1
} 
