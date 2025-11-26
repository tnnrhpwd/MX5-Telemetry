# ============================================================================
# Arduino Actions Launcher - PowerShell Script
# ============================================================================
# Launches the Arduino Actions GUI tool for MX5-Telemetry control
# ============================================================================

Write-Host ""
Write-Host "========================================================================"
Write-Host "Arduino Actions - USB Command Interface"
Write-Host "========================================================================"
Write-Host ""

# Check if Python is installed
try {
    $pythonVersion = python --version 2>&1
    Write-Host "Found: $pythonVersion"
} catch {
    Write-Host "ERROR: Python is not installed or not in PATH" -ForegroundColor Red
    Write-Host "Please install Python 3.7+ from python.org"
    Write-Host ""
    Read-Host "Press Enter to exit"
    exit 1
}

# Check if pyserial is installed
Write-Host "Checking dependencies..."
try {
    python -c "import serial" 2>&1 | Out-Null
    if ($LASTEXITCODE -ne 0) {
        throw "pyserial not found"
    }
    Write-Host "✓ pyserial package found" -ForegroundColor Green
} catch {
    Write-Host "⚠ pyserial package not found, installing..." -ForegroundColor Yellow
    python -m pip install pyserial
    if ($LASTEXITCODE -ne 0) {
        Write-Host "ERROR: Failed to install pyserial" -ForegroundColor Red
        Write-Host "Please run manually: pip install pyserial"
        Write-Host ""
        Read-Host "Press Enter to exit"
        exit 1
    }
    Write-Host "✓ pyserial installed successfully" -ForegroundColor Green
}

# Launch Arduino Actions
Write-Host ""
Write-Host "Starting Arduino Actions..." -ForegroundColor Cyan
Write-Host ""

$scriptPath = Split-Path -Parent $MyInvocation.MyCommand.Path
$pythonScript = Join-Path $scriptPath "arduino_actions.py"

python $pythonScript

# Check exit code
if ($LASTEXITCODE -ne 0) {
    Write-Host ""
    Write-Host "Arduino Actions exited with error code $LASTEXITCODE" -ForegroundColor Red
    Read-Host "Press Enter to exit"
}
