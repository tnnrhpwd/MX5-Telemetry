# Flash All Updates Script
# Commits changes, pushes to GitHub, pulls on Pi, and flashes devices

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

cd $workspaceRoot

# ====================================
# 0. Commit and Push Changes
# ====================================
Write-Host "[0/4] Committing and pushing changes to GitHub..." -ForegroundColor Green
Write-Host ""

# Check for uncommitted changes
$status = git status --porcelain
if ($status) {
    Write-Host "Uncommitted changes detected:" -ForegroundColor Yellow
    git status --short
    Write-Host ""
    
    $commitMsg = Read-Host "Enter commit message (or press Enter for auto-message)"
    if ([string]::IsNullOrWhiteSpace($commitMsg)) {
        $commitMsg = "Update firmware and Pi code - auto-commit for flash"
    }
    
    Write-Host "Staging all changes..." -ForegroundColor Cyan
    git add -A
    
    Write-Host "Committing changes..." -ForegroundColor Cyan
    git commit -m "$commitMsg"
    
    if ($LASTEXITCODE -ne 0) {
        Write-Host "ERROR: Git commit failed!" -ForegroundColor Red
        exit 1
    }
} else {
    Write-Host "No uncommitted changes" -ForegroundColor Gray
}

Write-Host "Pushing to GitHub..." -ForegroundColor Cyan
git push

if ($LASTEXITCODE -ne 0) {
    Write-Host "ERROR: Git push failed!" -ForegroundColor Red
    exit 1
}

Write-Host "Successfully pushed to GitHub!" -ForegroundColor Green
Prompt-Continue "Ready to connect to Pi and pull changes?"

# ====================================
# 1. Connect to Pi and Pull Changes
# ====================================
Write-Host "[1/4] Connecting to Pi and pulling changes..." -ForegroundColor Green
Write-Host ""

$piHost = "pi@192.168.1.23"

# Check if Pi is reachable
Write-Host "Checking Pi connection..." -ForegroundColor Cyan
try {
    $testResult = ssh -o ConnectTimeout=5 $piHost "echo Connected" 2>&1
    if ($LASTEXITCODE -ne 0) {
        throw "Connection failed"
    }
} catch {
    Write-Host "ERROR: Cannot connect to Pi at $piHost" -ForegroundColor Red
    Write-Host "Make sure the Pi is powered on and connected to the network." -ForegroundColor Yellow
    exit 1
}

Write-Host "Connected to Pi" -ForegroundColor Green
Write-Host ""

# Check if repository exists on Pi
Write-Host "Checking repository on Pi..." -ForegroundColor Cyan
$repoCheck = ssh $piHost "test -d ~/mx5-telemetry && echo 'exists' || echo 'missing'"

if ($repoCheck -match "missing") {
    Write-Host "Repository not found. Cloning from GitHub..." -ForegroundColor Yellow
    ssh $piHost 'cd ~ && git clone https://github.com/tnnrhpwd/MX5-Telemetry.git mx5-telemetry'
    
    if ($LASTEXITCODE -ne 0) {
        Write-Host "ERROR: Failed to clone repository on Pi!" -ForegroundColor Red
        exit 1
    }
    Write-Host "Repository cloned successfully!" -ForegroundColor Green
} else {
    Write-Host "Repository exists on Pi" -ForegroundColor Gray
}

# Pull latest changes on Pi
Write-Host "Pulling latest changes from GitHub on Pi..." -ForegroundColor Cyan
ssh $piHost 'cd ~/mx5-telemetry && git pull'

if ($LASTEXITCODE -ne 0) {
    Write-Host "ERROR: Git pull on Pi failed!" -ForegroundColor Red
    Write-Host "You may need to SSH to the Pi and resolve conflicts manually." -ForegroundColor Yellow
    exit 1
}

Write-Host "Successfully pulled changes on Pi!" -ForegroundColor Green
Prompt-Continue "Ready to flash ESP32?"

# ====================================
# 2. Flash ESP32 Display (via Pi)
# ====================================
Write-Host "[2/4] Flashing ESP32 Display..." -ForegroundColor Green
Write-Host "Changes: Updated display text rendering and gear estimation features" -ForegroundColor Gray
Write-Host ""

# Flash ESP32 on Pi using existing platformio installation
Write-Host "Flashing ESP32 (using cached builds)..." -ForegroundColor Cyan
ssh $piHost 'bash -lc "cd ~/mx5-telemetry/display && pio run --target upload"'

if ($LASTEXITCODE -ne 0) {
    Write-Host "WARNING: Flash failed, retrying..." -ForegroundColor Yellow
    Start-Sleep -Seconds 2
    ssh $piHost 'bash -lc "cd ~/mx5-telemetry/display && pio run --target upload"'
    
    if ($LASTEXITCODE -ne 0) {
        Write-Host "ERROR: ESP32 flash failed after retry!" -ForegroundColor Red
        Write-Host "You may need to manually reset the ESP32 or check the USB connection" -ForegroundColor Yellow
        exit 1
    }
}

Write-Host "ESP32 Display flashed successfully!" -ForegroundColor Green
Prompt-Continue "Ready to flash Arduino?"

# ====================================
# 3. Flash Arduino (via Pi)
# ====================================
Write-Host "[3/4] Flashing Arduino..." -ForegroundColor Green
Write-Host "Note: Arduino code hasn't changed in recent commits" -ForegroundColor Gray
Write-Host "Checking if flash is needed..." -ForegroundColor Gray
Write-Host ""

# Check if Arduino code was modified in recent commits
$arduinoChanges = git log -4 --name-only --oneline | Select-String "arduino/src/"
if (-not $arduinoChanges) {
    Write-Host "Arduino code unchanged - skipping flash" -ForegroundColor Yellow
} else {
    # Flash Arduino on Pi using cached builds
    Write-Host "Flashing Arduino (using cached builds)..." -ForegroundColor Cyan
    ssh $piHost 'bash -lc "cd ~/mx5-telemetry/arduino && pio run --target upload"'
    
    if ($LASTEXITCODE -ne 0) {
        Write-Host "ERROR: Arduino flash failed!" -ForegroundColor Red
        exit 1
    }
    
    Write-Host "Arduino flashed successfully!" -ForegroundColor Green
}

Prompt-Continue "Ready to restart Pi services?"

# ====================================
# 4. Restart Pi Services
# ====================================
Write-Host "[4/4] Restarting Pi services..." -ForegroundColor Green
Write-Host "Changes: Updated CAN handler, gear estimation, clutch detection, web server" -ForegroundColor Gray
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
Write-Host "  - Git: Committed and pushed to GitHub" -ForegroundColor Gray
Write-Host "  - Pi: Pulled latest changes" -ForegroundColor Gray
Write-Host "  - ESP32: Gear estimation, improved text rendering" -ForegroundColor Gray
Write-Host "  - Arduino: No changes (skipped)" -ForegroundColor Gray
Write-Host "  - Pi Service: Restarted with new code" -ForegroundColor Gray
Write-Host ""

cd $workspaceRoot
