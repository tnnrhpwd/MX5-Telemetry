# Upload Both Master and Slave Arduinos
# Interactive script to upload complete dual Arduino system

Write-Host "═══════════════════════════════════════════════════════" -ForegroundColor Cyan
Write-Host "  MX5-Telemetry Dual Arduino Upload" -ForegroundColor Cyan
Write-Host "═══════════════════════════════════════════════════════" -ForegroundColor Cyan
Write-Host ""
Write-Host "This script will upload firmware to BOTH Arduinos." -ForegroundColor White
Write-Host ""

# Check if we're in the right directory
if (-not (Test-Path "master/platformio.ini") -or -not (Test-Path "slave/platformio.ini")) {
    Write-Host "❌ Error: master/platformio.ini or slave/platformio.ini not found!" -ForegroundColor Red
    Write-Host "   Please run this script from the project root." -ForegroundColor Yellow
    pause
    exit 1
}

Write-Host "📋 Upload Order:" -ForegroundColor Green
Write-Host "   1️⃣  Master Arduino (Telemetry Logger)" -ForegroundColor White
Write-Host "       - Source: src/main.cpp" -ForegroundColor Gray
Write-Host "       - Full sensor suite (CAN, GPS, SD)" -ForegroundColor Gray
Write-Host ""
Write-Host "   2️⃣  Slave Arduino (LED Controller)" -ForegroundColor White
Write-Host "       - Source: src_slave/main.cpp" -ForegroundColor Gray
Write-Host "       - LED control only (20 LEDs)" -ForegroundColor Gray
Write-Host ""

$continue = Read-Host "Continue with upload? (Y/n)"
if ($continue -eq "n" -or $continue -eq "N") {
    Write-Host "Upload cancelled." -ForegroundColor Yellow
    exit 0
}

Write-Host ""
Write-Host "═══════════════════════════════════════════════════════" -ForegroundColor Yellow
Write-Host "  Step 1: Upload Master Arduino" -ForegroundColor Yellow
Write-Host "═══════════════════════════════════════════════════════" -ForegroundColor Yellow
Write-Host ""
Write-Host "🔌 Please connect Master Arduino #1 via USB" -ForegroundColor Cyan
Write-Host ""
Read-Host "Press Enter when Master Arduino is connected"

# Call master upload script
& "$PSScriptRoot\upload_master.ps1"

if ($LASTEXITCODE -ne 0) {
    Write-Host ""
    Write-Host "❌ Master upload failed. Please fix errors before continuing." -ForegroundColor Red
    pause
    exit 1
}

Write-Host ""
Write-Host "═══════════════════════════════════════════════════════" -ForegroundColor Yellow
Write-Host "  Step 2: Upload Slave Arduino" -ForegroundColor Yellow
Write-Host "═══════════════════════════════════════════════════════" -ForegroundColor Yellow
Write-Host ""
Write-Host "🔌 Please:" -ForegroundColor Cyan
Write-Host "   1. DISCONNECT Master Arduino" -ForegroundColor White
Write-Host "   2. CONNECT Slave Arduino #2 via USB" -ForegroundColor White
Write-Host ""
Read-Host "Press Enter when Slave Arduino is connected"

# Call slave upload script
& "$PSScriptRoot\upload_slave.ps1"

if ($LASTEXITCODE -ne 0) {
    Write-Host ""
    Write-Host "❌ Slave upload failed." -ForegroundColor Red
    pause
    exit 1
}

Write-Host ""
Write-Host "═══════════════════════════════════════════════════════" -ForegroundColor Green
Write-Host "  ✅ Both Arduinos Successfully Programmed!" -ForegroundColor Green
Write-Host "═══════════════════════════════════════════════════════" -ForegroundColor Green
Write-Host ""
Write-Host "🔗 Final Wiring Steps:" -ForegroundColor Cyan
Write-Host ""
Write-Host "1. Power System:" -ForegroundColor Yellow
Write-Host "   - Connect buck converter to vehicle 12V" -ForegroundColor White
Write-Host "   - Connect both Arduinos to 5V output" -ForegroundColor White
Write-Host "   - Connect shared GND" -ForegroundColor White
Write-Host ""
Write-Host "2. Serial Communication Link:" -ForegroundColor Yellow
Write-Host "   - Master TX (D1) → Slave RX (D0)" -ForegroundColor White
Write-Host "   - Shared GND between Arduinos" -ForegroundColor White
Write-Host ""
Write-Host "3. Master Connections:" -ForegroundColor Yellow
Write-Host "   - D2 ← GPS TX" -ForegroundColor White
Write-Host "   - D3 → GPS RX" -ForegroundColor White
Write-Host "   - D4 → SD CS" -ForegroundColor White
Write-Host "   - D10 → MCP2515 CS" -ForegroundColor White
Write-Host "   - D11/D12/D13 → SPI (CAN & SD)" -ForegroundColor White
Write-Host ""
Write-Host "4. Slave Connections:" -ForegroundColor Yellow
Write-Host "   - D5 → WS2812B LED strip data" -ForegroundColor White
Write-Host "   - 5V/GND → LED strip power" -ForegroundColor White
Write-Host ""
Write-Host "💡 Testing:" -ForegroundColor Cyan
Write-Host "   - Master should output status at 115200 baud" -ForegroundColor White
Write-Host "   - Slave LEDs should flash green 3 times on power-up" -ForegroundColor White
Write-Host "   - When master reads RPM, slave should display it" -ForegroundColor White
Write-Host ""
Write-Host "📖 Full wiring guide: docs/hardware/WIRING_GUIDE.md" -ForegroundColor Gray
Write-Host ""

pause
