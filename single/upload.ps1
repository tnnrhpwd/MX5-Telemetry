# MX5-Telemetry Single Arduino Upload Script
# Auto-reset via DTR toggle - no manual reset needed!

param(
    [string]$Port = "COM5"
)

$pioPath = "$env:USERPROFILE\.platformio\penv\Scripts\pio.exe"
$avrdudePath = "$env:USERPROFILE\.platformio\packages\tool-avrdude\avrdude.exe"
$avrdudeConf = "$env:USERPROFILE\.platformio\packages\tool-avrdude\avrdude.conf"
$firmwarePath = "$PSScriptRoot\.pio\build\nano\firmware.hex"

Write-Host ""
Write-Host "========================================" -ForegroundColor Cyan
Write-Host "  MX5-Telemetry Single Arduino Upload  " -ForegroundColor Cyan
Write-Host "========================================" -ForegroundColor Cyan
Write-Host ""

# Step 1: Build
Write-Host "Building firmware..." -ForegroundColor Yellow
Push-Location $PSScriptRoot
& $pioPath run
if ($LASTEXITCODE -ne 0) {
    Write-Host "Build failed!" -ForegroundColor Red
    Pop-Location
    exit 1
}
Pop-Location
Write-Host "Build successful!" -ForegroundColor Green
Write-Host ""

# Step 2: Auto-reset Arduino via DTR toggle
Write-Host "Resetting Arduino..." -ForegroundColor Yellow
try {
    $serial = New-Object System.IO.Ports.SerialPort $Port, 115200
    $serial.DtrEnable = $false
    $serial.Open()
    Start-Sleep -Milliseconds 50
    $serial.DtrEnable = $true
    Start-Sleep -Milliseconds 50
    $serial.DtrEnable = $false
    $serial.Close()
    Start-Sleep -Milliseconds 100
    Write-Host "Reset complete!" -ForegroundColor Green
}
catch {
    Write-Host "Auto-reset failed, trying upload anyway..." -ForegroundColor Yellow
}

# Step 3: Upload immediately after reset
Write-Host "Uploading firmware..." -ForegroundColor Yellow
& $avrdudePath -C $avrdudeConf -p atmega328p -c arduino -P $Port -b 115200 -D -U "flash:w:${firmwarePath}:i"

if ($LASTEXITCODE -eq 0) {
    Write-Host ""
    Write-Host "========================================" -ForegroundColor Green
    Write-Host "  UPLOAD SUCCESSFUL!" -ForegroundColor Green
    Write-Host "========================================" -ForegroundColor Green
    Write-Host ""
}
else {
    Write-Host ""
    Write-Host "Auto-upload failed. Trying manual reset method..." -ForegroundColor Yellow
    Write-Host ""
    Write-Host "1. Press and HOLD the RESET button on Arduino" -ForegroundColor White
    Write-Host "2. Press ENTER here (while still holding RESET)" -ForegroundColor White
    Write-Host "3. When you see 'RELEASE NOW', let go of RESET" -ForegroundColor White
    Write-Host ""
    Read-Host "Press ENTER when holding RESET"
    Write-Host ""
    Write-Host ">>> RELEASE RESET NOW! <<<" -ForegroundColor Red -BackgroundColor Yellow
    Write-Host ""
    & $avrdudePath -C $avrdudeConf -p atmega328p -c arduino -P $Port -b 115200 -D -U "flash:w:${firmwarePath}:i"
    
    if ($LASTEXITCODE -eq 0) {
        Write-Host ""
        Write-Host "========================================" -ForegroundColor Green
        Write-Host "  UPLOAD SUCCESSFUL!" -ForegroundColor Green
        Write-Host "========================================" -ForegroundColor Green
    }
    else {
        Write-Host "Upload failed!" -ForegroundColor Red
    }
}
