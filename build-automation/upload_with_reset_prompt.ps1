# Upload with manual reset prompt
param(
    [Parameter(Mandatory=$true)]
    [ValidateSet("master", "slave")]
    [string]$Project,
    
    [Parameter(Mandatory=$true)]
    [string]$Port
)

Write-Host ""
Write-Host "=== Upload with Manual Reset ===" -ForegroundColor Cyan
Write-Host ""
Write-Host "Project: $Project" -ForegroundColor Yellow
Write-Host "Port: $Port" -ForegroundColor Yellow
Write-Host ""
Write-Host "INSTRUCTIONS:" -ForegroundColor Green
Write-Host "1. Get ready to press the RESET button on your Arduino" -ForegroundColor White
Write-Host "2. Press Enter to start upload" -ForegroundColor White
Write-Host "3. When you see 'Uploading...', press RESET on Arduino" -ForegroundColor White
Write-Host "4. Release after 1 second" -ForegroundColor White
Write-Host ""

Read-Host "Press Enter when ready"

Write-Host ""
Write-Host "Starting upload in 3 seconds..." -ForegroundColor Yellow
Start-Sleep -Seconds 1
Write-Host "2..." -ForegroundColor Yellow
Start-Sleep -Seconds 1
Write-Host "1..." -ForegroundColor Yellow
Start-Sleep -Seconds 1
Write-Host ""
Write-Host ">>> PRESS RESET BUTTON NOW! <<<" -ForegroundColor Red -BackgroundColor White
Write-Host ""

& "$env:USERPROFILE\.platformio\penv\Scripts\pio.exe" run -d $Project -e nano_old_bootloader -t upload --upload-port $Port
