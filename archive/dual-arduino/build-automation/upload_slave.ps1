# Upload Slave Arduino (LED Controller)
# Builds and uploads src_slave/main.cpp to Arduino Nano #2

Write-Host "═══════════════════════════════════════════════════════" -ForegroundColor Cyan
Write-Host "  MX5-Telemetry Slave Arduino Upload (LED Controller)" -ForegroundColor Cyan
Write-Host "═══════════════════════════════════════════════════════" -ForegroundColor Cyan
Write-Host ""

# Check if we're in the right directory
if (-not (Test-Path "slave/platformio.ini")) {
    Write-Host "❌ Error: slave/platformio.ini not found!" -ForegroundColor Red
    Write-Host "   Please run this script from the project root." -ForegroundColor Yellow
    pause
    exit 1
}

Write-Host "📋 Configuration:" -ForegroundColor Green
Write-Host "   - Environment: nano_atmega328 (Slave)" -ForegroundColor White
Write-Host "   - Source: slave/src/main.cpp" -ForegroundColor White
Write-Host "   - Libraries: Adafruit NeoPixel only" -ForegroundColor White
Write-Host "   - Serial: 9600 baud (RX from master)" -ForegroundColor White
Write-Host "   - LED Count: 20 LEDs on pin D5" -ForegroundColor White
Write-Host ""

Write-Host "🔌 Please ensure:" -ForegroundColor Yellow
Write-Host "   1. Slave Arduino is connected via USB" -ForegroundColor White
Write-Host "   2. Serial Monitor is CLOSED" -ForegroundColor White
Write-Host "   3. Master Arduino is disconnected (or use different port)" -ForegroundColor White
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
    # PlatformIO is available - build from slave directory
    & $pioExe run -d slave -e nano_atmega328
    
    if ($LASTEXITCODE -eq 0) {
        Write-Host ""
        Write-Host "✅ Build successful!" -ForegroundColor Green
        Write-Host ""
        Write-Host "📤 Uploading to Slave Arduino..." -ForegroundColor Cyan
        
        & $pioExe run -d slave -e nano_atmega328 -t upload
        
        if ($LASTEXITCODE -eq 0) {
            Write-Host ""
            Write-Host "═══════════════════════════════════════════════════════" -ForegroundColor Green
            Write-Host "  ✅ Slave Arduino Upload Complete!" -ForegroundColor Green
            Write-Host "═══════════════════════════════════════════════════════" -ForegroundColor Green
            Write-Host ""
            Write-Host "💡 Expected behavior:" -ForegroundColor Cyan
            Write-Host "   - LED strip should flash GREEN 3 times on startup" -ForegroundColor White
            Write-Host "   - LEDs respond to serial commands (RPM:xxxx, SPD:xxx)" -ForegroundColor White
            Write-Host ""
            Write-Host "🔗 Wiring connections:" -ForegroundColor Cyan
            Write-Host "   - Slave D0 (RX) ← Master D1 (TX)" -ForegroundColor White
            Write-Host "   - Slave D5 → WS2812B LED strip data pin" -ForegroundColor White
            Write-Host "   - Shared GND between both Arduinos" -ForegroundColor White
            Write-Host ""
            Write-Host "🧪 Test slave with commands:" -ForegroundColor Cyan
            Write-Host "   RPM:3000   - Show yellow bar" -ForegroundColor White
            Write-Host "   SPD:0      - Show white idle animation" -ForegroundColor White
            Write-Host "   ERR        - Show red error animation" -ForegroundColor White
            Write-Host "   CLR        - Clear all LEDs" -ForegroundColor White
            Write-Host ""
            
            # Offer to open serial monitor for testing
            $monitor = Read-Host "Open Serial Monitor to test? (Y/n)"
            if ($monitor -ne "n" -and $monitor -ne "N") {
                Write-Host ""
                Write-Host "Opening Serial Monitor (9600 baud)..." -ForegroundColor Cyan
                Write-Host "Type commands like: RPM:3000" -ForegroundColor Gray
                Write-Host "Press Ctrl+C to exit" -ForegroundColor Gray
                Start-Sleep -Seconds 2
                & $pioExe device monitor -b 9600
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
} else {
    # PlatformIO CLI not found, provide instructions
    Write-Host ""
    Write-Host "❌ PlatformIO CLI not found in PATH" -ForegroundColor Red
    Write-Host ""
    Write-Host "Please use one of these methods instead:" -ForegroundColor Yellow
    Write-Host ""
    Write-Host "Method 1: VS Code PlatformIO Extension" -ForegroundColor Cyan
    Write-Host "   1. Open this project in VS Code" -ForegroundColor White
    Write-Host "   2. Click PlatformIO icon (alien head) in left sidebar" -ForegroundColor White
    Write-Host "   3. Select 'led_slave' environment" -ForegroundColor White
    Write-Host "   4. Click 'Upload' button" -ForegroundColor White
    Write-Host ""
    Write-Host "Method 2: Install PlatformIO Core" -ForegroundColor Cyan
    Write-Host "   pip install platformio" -ForegroundColor White
    Write-Host "   Then run this script again" -ForegroundColor White
    Write-Host ""
}

pause
