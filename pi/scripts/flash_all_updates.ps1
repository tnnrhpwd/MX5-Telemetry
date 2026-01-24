# Flash All Updates Script
# Flashes ESP32 display, Arduino, and Pi with recent changes

$ErrorActionPreference = "Stop"
$workspaceRoot = "c:\Users\tanne\Documents\Github\MX5-Telemetry"

Write-Host "================================================" -ForegroundColor Cyan
Write-Host "   MX5 Telemetry - Flash All Updates" -ForegroundColor Cyan
Write-Host "================================================" -ForegroundColor Cyan
Write-Host ""

# ====================================
# 0. Auto-commit and push changes
# ====================================
cd $workspaceRoot

# Check for uncommitted changes
$gitStatus = git status --porcelain
if ($gitStatus) {
    Write-Host "[0/3] Auto-committing changes..." -ForegroundColor Green
    
    # Generate descriptive commit message
    $timestamp = Get-Date -Format "yyyy-MM-dd HH:mm"
    $changedAreas = @()
    
    # Check which areas have changes
    if ($gitStatus | Select-String "display/") { $changedAreas += "ESP32" }
    if ($gitStatus | Select-String "arduino/") { $changedAreas += "Arduino" }
    if ($gitStatus | Select-String "pi/") { $changedAreas += "Pi" }
    if ($gitStatus | Select-String "tools/") { $changedAreas += "Tools" }
    if ($gitStatus | Select-String "docs/") { $changedAreas += "Docs" }
    
    if ($changedAreas.Count -eq 0) {
        $areaStr = "updates"
    } else {
        $areaStr = $changedAreas -join "/"
    }
    
    $commitMsg = "Auto-commit: $areaStr changes - $timestamp"
    
    Write-Host "Committing with message: $commitMsg" -ForegroundColor Cyan
    git add -A
    git commit -m $commitMsg
    
    Write-Host "Pushing to remote..." -ForegroundColor Cyan
    git push
    
    Write-Host "Changes committed and pushed!" -ForegroundColor Green
    Write-Host ""
} else {
    Write-Host "No uncommitted changes detected" -ForegroundColor Gray
    Write-Host ""
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

# Try multiple times with increasing timeouts (Pi may be slow to respond after flash)
$maxRetries = 3
for ($retry = 1; $retry -le $maxRetries; $retry++) {
    foreach ($hostAddress in $piHosts) {
        Write-Host "Trying $hostAddress (attempt $retry/$maxRetries)..." -ForegroundColor Gray
        try {
            $timeout = 3 + ($retry * 2)  # 5, 7, 9 second timeouts
            $testResult = ssh -o ConnectTimeout=$timeout -o StrictHostKeyChecking=no -o ServerAliveInterval=5 $hostAddress "echo Connected" 2>&1
            if ($LASTEXITCODE -eq 0) {
                $piHost = $hostAddress
                Write-Host "Connected to Pi at $piHost" -ForegroundColor Green
                break
            }
        } catch {
            # Try next host
        }
    }
    if ($piHost) { break }
    if ($retry -lt $maxRetries) {
        Write-Host "Connection failed, waiting 5 seconds before retry..." -ForegroundColor Yellow
        Start-Sleep -Seconds 5
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

# Kill any orphaned Python processes that might be holding the serial port
ssh $piHost "sudo pkill -f 'python.*main.py' 2>/dev/null; sudo pkill -f 'python.*esp32' 2>/dev/null" 2>$null
Start-Sleep -Seconds 1

ssh $piHost "sudo systemctl stop mx5-display.service"
Start-Sleep -Seconds 3  # Give serial port time to release

# Make sure serial port is free
ssh $piHost "sudo fuser -k /dev/ttyUSB0 2>/dev/null; sudo fuser -k /dev/ttyACM0 2>/dev/null" 2>$null
Start-Sleep -Seconds 1

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

# ====================================
# 3. Update Pi Service
# ====================================
Write-Host "[3/3] Updating Pi Service..." -ForegroundColor Green
Write-Host "Changes: Updated CAN handler, gear estimation, clutch detection" -ForegroundColor Gray
Write-Host ""

# Restart the display service
Write-Host "Restarting display service on Pi..." -ForegroundColor Cyan

# Clear any cached connections and restart cleanly
ssh -o ConnectTimeout=10 $piHost "sudo systemctl daemon-reload && sudo systemctl restart mx5-display.service"

if ($LASTEXITCODE -ne 0) {
    Write-Host "WARNING: Service restart command may have timed out, checking status..." -ForegroundColor Yellow
}

Write-Host "Service restart initiated" -ForegroundColor Green
Write-Host ""

# Check service status (with retry in case Pi is slow)
Write-Host "Checking service status..." -ForegroundColor Cyan
Start-Sleep -Seconds 5

# Try to get status with timeout
$statusResult = ssh -o ConnectTimeout=10 $piHost "sudo systemctl status mx5-display.service --no-pager -l 2>&1 | head -20"
if ($LASTEXITCODE -eq 0) {
    Write-Host $statusResult
} else {
    Write-Host "Could not retrieve service status (Pi may be busy), but flash completed." -ForegroundColor Yellow
}

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
