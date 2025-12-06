# Upload Master Arduino (Telemetry Logger)
# Builds and uploads src/main.cpp to Arduino Nano #1

Write-Host "═══════════════════════════════════════════════════════" -ForegroundColor Cyan
Write-Host "  MX5-Telemetry Master Arduino Upload" -ForegroundColor Cyan
Write-Host "═══════════════════════════════════════════════════════" -ForegroundColor Cyan
Write-Host ""

# Check if we're in the right directory
if (-not (Test-Path "master/platformio.ini")) {
    Write-Host "❌ Error: master/platformio.ini not found!" -ForegroundColor Red
    Write-Host "   Please run this script from the project root." -ForegroundColor Yellow
    pause
    exit 1
}

Write-Host "📋 Configuration:" -ForegroundColor Green
Write-Host "   - Environment: nano_atmega328 (Master)" -ForegroundColor White
Write-Host "   - Source: master/src/main.cpp" -ForegroundColor White
Write-Host "   - Libraries: CAN, GPS, SD, LEDSlave" -ForegroundColor White
Write-Host "   - Serial: 115200 baud" -ForegroundColor White
Write-Host ""

Write-Host "🔌 Please ensure:" -ForegroundColor Yellow
Write-Host "   1. Master Arduino is connected via USB" -ForegroundColor White
Write-Host "   2. Serial Monitor is CLOSED" -ForegroundColor White
Write-Host "   3. LED slave Arduino is disconnected (avoid conflicts)" -ForegroundColor White
Write-Host ""

$continue = Read-Host "Continue? (Y/n)"
if ($continue -eq "n" -or $continue -eq "N") {
    Write-Host "Upload cancelled." -ForegroundColor Yellow
    exit 0
}

Write-Host ""
Write-Host "🔨 Building firmware..." -ForegroundColor Cyan

# Find PlatformIO executable
$pioExe = $null

# Method 1: Check if pio is in PATH
$pioCmd = Get-Command pio -ErrorAction SilentlyContinue
if ($pioCmd) {
    $pioExe = "pio"
    Write-Host "   Using PlatformIO from PATH" -ForegroundColor Gray
}
# Method 2: Check VS Code PlatformIO extension
elseif (Test-Path "$env:USERPROFILE\.platformio\penv\Scripts\platformio.exe") {
    $pioExe = "$env:USERPROFILE\.platformio\penv\Scripts\platformio.exe"
    Write-Host "   Using VS Code PlatformIO extension" -ForegroundColor Gray
}

if ($pioExe) {
    # PlatformIO is available - build from master directory
    & $pioExe run -d master -e nano_atmega328
    
    if ($LASTEXITCODE -eq 0) {
        Write-Host ""
        Write-Host "✅ Build successful!" -ForegroundColor Green
        Write-Host ""
        Write-Host "📤 Uploading to Master Arduino..." -ForegroundColor Cyan
        
        & $pioExe run -d master -e nano_atmega328 -t upload
        
        if ($LASTEXITCODE -eq 0) {
            Write-Host ""
            Write-Host "═══════════════════════════════════════════════════════" -ForegroundColor Green
            Write-Host "  ✅ Master Arduino Upload Complete!" -ForegroundColor Green
            Write-Host "═══════════════════════════════════════════════════════" -ForegroundColor Green
            Write-Host ""
            Write-Host "💡 Next steps:" -ForegroundColor Cyan
            Write-Host "   1. Open Serial Monitor at 115200 baud to verify" -ForegroundColor White
            Write-Host "   2. Upload slave firmware: .\upload_slave.ps1" -ForegroundColor White
            Write-Host "   3. Connect slave TX → master RX for serial link" -ForegroundColor White
            Write-Host ""
            
            # Offer to open serial monitor
            $monitor = Read-Host "Open Serial Monitor? (Y/n)"
            if ($monitor -ne "n" -and $monitor -ne "N") {
                Write-Host ""
                Write-Host "Opening Serial Monitor (press Ctrl+C to exit)..." -ForegroundColor Cyan
                Start-Sleep -Seconds 2
                & $pioExe device monitor -b 115200
            }
        } else {
            Write-Host ""
            Write-Host "❌ Upload failed!" -ForegroundColor Red
            Write-Host ""
            Write-Host "Troubleshooting:" -ForegroundColor Yellow
            Write-Host "   - Check if Arduino is connected" -ForegroundColor White
            Write-Host "   - Try a different USB port" -ForegroundColor White
            Write-Host "   - Close any Serial Monitor programs" -ForegroundColor White
            Write-Host "   - Press reset button right before upload" -ForegroundColor White
            Write-Host ""
        }
    } else {
        Write-Host ""
        Write-Host "❌ Build failed! Check errors above." -ForegroundColor Red
    }
}
else {
    # PlatformIO CLI not found, provide instructions
    Write-Host ""
    Write-Host "❌ PlatformIO CLI not found in PATH" -ForegroundColor Red
    Write-Host ""
    Write-Host "Please use one of these methods instead:" -ForegroundColor Yellow
    Write-Host ""
    Write-Host "Method 1: VS Code PlatformIO Extension" -ForegroundColor Cyan
    Write-Host "   1. Open this project in VS Code" -ForegroundColor White
    Write-Host "   2. Click PlatformIO icon (alien head) in left sidebar" -ForegroundColor White
    Write-Host "   3. Select 'nano_atmega328' environment" -ForegroundColor White
    Write-Host "   4. Click 'Upload' button" -ForegroundColor White
    Write-Host ""
    Write-Host "Method 2: Install PlatformIO Core" -ForegroundColor Cyan
    Write-Host "   pip install platformio" -ForegroundColor White
    Write-Host "   Then run this script again" -ForegroundColor White
    Write-Host ""
}

pause
