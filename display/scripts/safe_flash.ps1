# Safe ESP32 Display Flash Script
# Stops Pi app, flashes ESP32, then restarts Pi app
# Usage: .\safe_flash.ps1

$PI_HOST = "pi@192.168.1.23"

Write-Host "=== Safe ESP32 Display Flash ===" -ForegroundColor Cyan
Write-Host ""

# Step 1: Stop the Pi display service
Write-Host "[1/4] Stopping mx5-display service..." -ForegroundColor Yellow
ssh $PI_HOST "sudo systemctl stop mx5-display"
if ($LASTEXITCODE -ne 0) {
    Write-Host "Warning: Could not stop service (may not be running)" -ForegroundColor DarkYellow
}
Start-Sleep -Seconds 2
Write-Host "      Service stopped" -ForegroundColor Green

# Step 2: Pull latest code
Write-Host "[2/4] Pulling latest code..." -ForegroundColor Yellow
ssh $PI_HOST "cd ~/MX5-Telemetry && git pull"
if ($LASTEXITCODE -ne 0) {
    Write-Host "ERROR: Git pull failed!" -ForegroundColor Red
    Write-Host "Restarting service anyway..." -ForegroundColor Yellow
    ssh $PI_HOST "sudo systemctl start mx5-display"
    exit 1
}
Write-Host "      Code updated" -ForegroundColor Green

# Step 3: Flash ESP32
Write-Host "[3/4] Flashing ESP32 (this takes ~60 seconds)..." -ForegroundColor Yellow
ssh $PI_HOST "cd ~/MX5-Telemetry && ~/.local/bin/pio run -d display --target upload"
$flashResult = $LASTEXITCODE
if ($flashResult -ne 0) {
    Write-Host "ERROR: Flash failed!" -ForegroundColor Red
    Write-Host "Restarting service anyway..." -ForegroundColor Yellow
    ssh $PI_HOST "sudo systemctl start mx5-display"
    exit 1
}
Write-Host "      Flash complete" -ForegroundColor Green

# Step 4: Restart Pi display service
Write-Host "[4/4] Restarting mx5-display service..." -ForegroundColor Yellow
Start-Sleep -Seconds 2
ssh $PI_HOST "sudo systemctl start mx5-display"
if ($LASTEXITCODE -ne 0) {
    Write-Host "ERROR: Could not restart service!" -ForegroundColor Red
    exit 1
}
Write-Host "      Service started" -ForegroundColor Green

Write-Host ""
Write-Host "=== Flash Complete ===" -ForegroundColor Cyan
