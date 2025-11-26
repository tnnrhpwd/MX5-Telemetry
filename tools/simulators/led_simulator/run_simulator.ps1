# ============================================================================
# MX5-Telemetry LED Simulator Launcher (PowerShell)
# ============================================================================
# Alternative launcher using PowerShell for Windows users
# ============================================================================

Write-Host "====================================" -ForegroundColor Cyan
Write-Host "MX5-Telemetry LED Simulator" -ForegroundColor Green
Write-Host "====================================" -ForegroundColor Cyan
Write-Host ""

# Check for Python
try {
    $pythonVersion = python --version 2>&1
    Write-Host "[OK] Python found: $pythonVersion" -ForegroundColor Green
}
catch {
    Write-Host "[ERROR] Python not found!" -ForegroundColor Red
    Write-Host ""
    Write-Host "Please install Python 3.7+ from: https://www.python.org/downloads/" -ForegroundColor Yellow
    Write-Host "Make sure to check 'Add Python to PATH' during installation." -ForegroundColor Yellow
    Write-Host ""
    Read-Host "Press Enter to exit"
    exit 1
}

Write-Host ""

# Check if we're in the right directory
if (-not (Test-Path "tools\LED_Simulator\led_simulator_v2.1.py")) {
    Write-Host "[ERROR] Must run from project root directory" -ForegroundColor Red
    Write-Host ""
    Write-Host "Current directory: $PWD" -ForegroundColor Yellow
    Write-Host "Expected: MX5-Telemetry root folder" -ForegroundColor Yellow
    Write-Host ""
    Read-Host "Press Enter to exit"
    exit 1
}

Write-Host "[OK] Found LED Simulator" -ForegroundColor Green
Write-Host ""
Write-Host "Launching LED Simulator..." -ForegroundColor Cyan
Write-Host ""
Write-Host "CONTROLS:" -ForegroundColor Yellow
Write-Host "  Arrow Up     : Gas Pedal" -ForegroundColor White
Write-Host "  Arrow Down   : Brake" -ForegroundColor White
Write-Host "  Arrow Right  : Shift Up" -ForegroundColor White
Write-Host "  Arrow Left   : Shift Down" -ForegroundColor White
Write-Host "  Shift Key    : Clutch" -ForegroundColor White
Write-Host "  ESC          : Quit" -ForegroundColor White
Write-Host ""
Write-Host "Window will open shortly..." -ForegroundColor Green
Write-Host ""

# Launch the simulator
python tools\LED_Simulator\led_simulator_v2.1.py

Write-Host ""
Write-Host "Simulator closed." -ForegroundColor Cyan
Write-Host ""
Read-Host "Press Enter to exit"
