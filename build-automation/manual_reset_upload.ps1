# Manual reset upload with precise timing
param(
    [string]$Port = "COM3"
)

Write-Host ""
Write-Host "=== Manual Reset Upload for Slave ===" -ForegroundColor Cyan
Write-Host ""
Write-Host "This will upload in TWO stages:" -ForegroundColor Yellow
Write-Host "1. Build the firmware" -ForegroundColor White
Write-Host "2. Upload with manual reset timing" -ForegroundColor White
Write-Host ""

# Stage 1: Build only
Write-Host "Stage 1: Building firmware..." -ForegroundColor Green
& "$env:USERPROFILE\.platformio\penv\Scripts\pio.exe" run -d slave -e nano_old_bootloader

if ($LASTEXITCODE -ne 0) {
    Write-Host "Build failed!" -ForegroundColor Red
    exit 1
}

Write-Host ""
Write-Host "Build successful!" -ForegroundColor Green
Write-Host ""
Write-Host "Stage 2: Manual reset upload" -ForegroundColor Green
Write-Host ""
Write-Host "PRECISE TIMING REQUIRED:" -ForegroundColor Yellow
Write-Host "1. Press and HOLD the reset button" -ForegroundColor White
Write-Host "2. Press Enter to start upload" -ForegroundColor White
Write-Host "3. RELEASE reset button immediately when upload starts" -ForegroundColor White
Write-Host "4. The bootloader has 2 seconds to accept upload" -ForegroundColor White
Write-Host ""

Read-Host "Press and HOLD reset, then press Enter"

Write-Host ""
Write-Host ">>> RELEASE RESET BUTTON NOW! <<<" -ForegroundColor Red -BackgroundColor White
Write-Host ""

# Use avrdude directly for more control
$avrdudePath = "$env:USERPROFILE\.platformio\packages\tool-avrdude\avrdude.exe"
$avrdudeConf = "$env:USERPROFILE\.platformio\packages\tool-avrdude\avrdude.conf"
$firmwareHex = "slave\.pio\build\nano_old_bootloader\firmware.hex"

& $avrdudePath -v -p atmega328p -C $avrdudeConf -c arduino -b 57600 -D -P $Port -U "flash:w:$firmwareHex:i"

if ($LASTEXITCODE -eq 0) {
    Write-Host ""
    Write-Host "[OK] Upload successful!" -ForegroundColor Green
} else {
    Write-Host ""
    Write-Host "[FAIL] Upload failed - try again" -ForegroundColor Red
}
