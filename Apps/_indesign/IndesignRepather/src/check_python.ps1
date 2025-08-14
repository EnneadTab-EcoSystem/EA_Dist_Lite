# Simple PowerShell script to check Python installation
param([switch]$Silent)

if (-not $Silent) {
    Write-Host "Checking Python installation..."
}

# Try to run python --version
try {
    $result = python --version 2>&1
    if ($LASTEXITCODE -eq 0) {
        if (-not $Silent) {
            Write-Host "Python found: $result" -ForegroundColor Green
        }
        exit 0
    }
} catch {
    # Continue to next check
}

# Try python3 --version
try {
    $result = python3 --version 2>&1
    if ($LASTEXITCODE -eq 0) {
        if (-not $Silent) {
            Write-Host "Python3 found: $result" -ForegroundColor Green
        }
        exit 0
    }
} catch {
    # Continue to next check
}

# Check common installation paths
$paths = @(
    "C:\Python*",
    "C:\Program Files\Python*",
    "C:\Program Files (x86)\Python*"
)

foreach ($path in $paths) {
    $pythonDirs = Get-ChildItem -Path $path -Directory -ErrorAction SilentlyContinue
    foreach ($dir in $pythonDirs) {
        $pythonExe = Join-Path $dir.FullName "python.exe"
        if (Test-Path $pythonExe) {
            try {
                $version = & $pythonExe --version 2>&1
                if ($LASTEXITCODE -eq 0) {
                    if (-not $Silent) {
                        Write-Host "Python found at: $pythonExe" -ForegroundColor Green
                        Write-Host "Version: $version" -ForegroundColor Green
                    }
                    exit 0
                }
            } catch {
                # Continue to next path
            }
        }
    }
}

# Check Windows Store Python
try {
    $storePython = Get-AppxPackage -Name "PythonSoftwareFoundation.Python*" -ErrorAction SilentlyContinue
    if ($storePython) {
        if (-not $Silent) {
            Write-Host "Python found in Microsoft Store: $($storePython.Name)" -ForegroundColor Green
        }
        exit 0
    }
} catch {
    # Continue
}

if (-not $Silent) {
    Write-Host "Python is not installed or not accessible from PATH" -ForegroundColor Red
    Write-Host ""
    Write-Host "TROUBLESHOOTING:"
    Write-Host "1. Install Python from python.org or Microsoft Store"
    Write-Host "2. Ensure Python is added to your system PATH"
    Write-Host "3. Try restarting your computer after installation"
}

exit 1 
