# ============================================================================
# MX5-Telemetry LED simulator launcher (PowerShell)
# ============================================================================

$here = Split-Path -Parent $MyInvocation.MyCommand.Path
$venvPython = Join-Path $here "..\..\..\venv\Scripts\python.exe"

if (Test-Path $venvPython) {
    $python = (Resolve-Path $venvPython).Path
} else {
    $candidate = Get-Command python -ErrorAction SilentlyContinue
    if (-not $candidate) {
        Write-Host "[X] Python not found." -ForegroundColor Red
        Write-Host "    Install Python 3.8+ from https://www.python.org/downloads/" -ForegroundColor Yellow
        Write-Host "    and tick 'Add Python to PATH', or create the venv:  py -m venv venv" -ForegroundColor Yellow
        Read-Host "Press Enter to exit"
        exit 1
    }
    $python = $candidate.Source
}

Write-Host "MX5-Telemetry LED simulator" -ForegroundColor Cyan
Write-Host "  Up/Down 100 rpm - PgUp/PgDn 500 rpm - Space sweeps - S/M/E - T/I - Esc" -ForegroundColor DarkGray
Write-Host ""

$script = Join-Path $here "led_simulator_v3.py"
& $python $script @args
if ($LASTEXITCODE -ne 0) { Read-Host "Press Enter to exit" }
