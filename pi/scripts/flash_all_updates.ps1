# Flash All Updates Script
# Flashes ESP32 display, Arduino, and Pi with recent changes

$ErrorActionPreference = "Stop"
$workspaceRoot = "c:\Users\tanne\Documents\Github\MX5-Telemetry"

Write-Host "================================================" -ForegroundColor Cyan
Write-Host "   MX5 Telemetry - Flash All Updates" -ForegroundColor Cyan
Write-Host "================================================" -ForegroundColor Cyan
Write-Host ""

# Function to prompt for continuation
function Prompt-Continue {
    param([string]$message)
    Write-Host ""
    Write-Host "$message" -ForegroundColor Yellow
    $response = Read-Host "Continue? (y/n)"
    if ($response -ne 'y') {
        Write-Host "Aborted by user." -ForegroundColor Red
        exit 1
    }
}

# ====================================
# 1. Connect to Pi and flash ESP32 remotely
# ====================================
Write-Host "[1/3] Flashing ESP32 Display (via Pi)..." -ForegroundColor Green
Write-Host "Changes: Updated display text rendering and gear estimation features" -ForegroundColor Gray
Write-Host ""

# Check if Pi is reachable
Write-Host "Checking Pi connection..." -ForegroundColor Cyan

# Try home network first (192.168.1.23 or mx5pi.local), then hotspot (10.62.26.67)
$piHosts = @("pi@mx5pi.local", "pi@192.168.1.23", "pi@10.62.26.67")
$piHost = $null

foreach ($hostAddress in $piHosts) {
    Write-Host "Trying $hostAddress..." -ForegroundColor Gray
    try {
        $testResult = ssh -o ConnectTimeout=3 -o StrictHostKeyChecking=no $hostAddress "echo Connected" 2>&1
        if ($LASTEXITCODE -eq 0) {
            $piHost = $hostAddress
            Write-Host "Connected to Pi at $piHost" -ForegroundColor Green
            break
        }
    } catch {
        # Try next host
    }
}

if (-not $piHost) {
    Write-Host "ERROR: Cannot connect to Pi" -ForegroundColor Red
    Write-Host "Tried: mx5pi.local (home), 192.168.1.23 (home), 10.62.26.67 (hotspot)" -ForegroundColor Yellow
    Write-Host "Make sure the Pi is powered on and connected to the network." -ForegroundColor Yellow
    exit 1
}

Write-Host ""
# Stop the display service first to free up serial port and prevent collision
Write-Host "Stopping display service to free serial port..." -ForegroundColor Cyan
ssh $piHost "sudo systemctl stop mx5-display.service"
Start-Sleep -Seconds 2  # Give serial port time to release

Write-Host "Building and uploading ESP32 firmware on Pi..." -ForegroundColor Cyan
ssh $piHost "cd ~/MX5-Telemetry && git pull && ~/.local/bin/pio run -d display --target upload"

$flashResult = $LASTEXITCODE
if ($flashResult -ne 0) {
    Write-Host "ERROR: ESP32 flash failed! Restarting display service..." -ForegroundColor Red
    ssh $piHost "sudo systemctl start mx5-display.service"
    exit 1
}

Write-Host "ESP32 Display flashed successfully!" -ForegroundColor Green
Write-Host ""
Prompt-Continue "Ready to update Pi service?"

# ====================================
# 2. Flash Arduino
# ====================================
Write-Host "[2/3] Flashing Arduino..." -ForegroundColor Green
Write-Host "Note: Arduino code hasn't changed in recent commits" -ForegroundColor Gray
Write-Host "Checking if flash is needed..." -ForegroundColor Gray
Write-Host ""

cd "$workspaceRoot\arduino"

# Check if Arduino code was modified in recent commits
$arduinoChanges = git log -4 --name-only --oneline | Select-String "arduino/src/"
if (-not $arduinoChanges) {
    Write-Host "Arduino code unchanged - skipping flash" -ForegroundColor Yellow
} else {
    Write-Host "Building Arduino firmware..." -ForegroundColor Cyan
    pio run
    
    if ($LASTEXITCODE -ne 0) {
        Write-Host "ERROR: Arduino build failed!" -ForegroundColor Red
        exit 1
    }
    
    Write-Host "Uploading to Arduino..." -ForegroundColor Cyan
    pio run --target upload
    
    if ($LASTEXITCODE -ne 0) {
        Write-Host "ERROR: Arduino upload failed!" -ForegroundColor Red
        exit 1
    }
    
    Write-Host "Arduino flashed successfully!" -ForegroundColor Green
}

Prompt-Continue "Ready to deploy to Raspberry Pi?"

# ====================================
# 3. Update Pi Service
# ====================================
Write-Host "[3/3] Updating Pi Service..." -ForegroundColor Green
Write-Host "Changes: Updated CAN handler, gear estimation, clutch detection" -ForegroundColor Gray
Write-Host ""

# Restart the display service
Write-Host "Restarting display service on Pi..." -ForegroundColor Cyan
ssh $piHost "sudo systemctl restart mx5-display.service"

if ($LASTEXITCODE -ne 0) {
    Write-Host "ERROR: Failed to restart service!" -ForegroundColor Red
    exit 1
}

Write-Host "Service restarted" -ForegroundColor Green
Write-Host ""

# Check service status
Write-Host "Checking service status..." -ForegroundColor Cyan
Start-Sleep -Seconds 3
ssh $piHost "sudo systemctl status mx5-display.service --no-pager -l" | Select-Object -First 20

Write-Host ""
Write-Host "================================================" -ForegroundColor Cyan
Write-Host "   All Updates Flashed Successfully!" -ForegroundColor Green
Write-Host "================================================" -ForegroundColor Cyan
Write-Host ""
Write-Host "Summary of changes deployed:" -ForegroundColor White
Write-Host "  - ESP32: Gear estimation, improved text rendering" -ForegroundColor Gray
Write-Host "  - Arduino: No changes (skipped)" -ForegroundColor Gray
Write-Host "  - Pi: CAN handler speed parsing, clutch detection, gear estimation" -ForegroundColor Gray
Write-Host ""

cd $workspaceRoot
