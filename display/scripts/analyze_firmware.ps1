# ============================================================================
# ESP32-S3 Firmware Analysis Script
# ============================================================================
# Analyzes a firmware binary to help with reverse engineering
# Extracts strings, identifies libraries, and provides insights
# ============================================================================

param(
    [Parameter(Mandatory=$false)]
    [string]$FirmwarePath = "",
    
    [Parameter(Mandatory=$false)]
    [string]$OutputDir = "analysis_output"
)

$ErrorActionPreference = "Stop"
$ScriptDir = Split-Path -Parent $PSScriptRoot

Write-Host "============================================" -ForegroundColor Cyan
Write-Host "ESP32-S3 Firmware Analysis Tool" -ForegroundColor Cyan
Write-Host "============================================" -ForegroundColor Cyan
Write-Host ""

# Find firmware file
if ([string]::IsNullOrEmpty($FirmwarePath)) {
    $backupDir = Join-Path $ScriptDir "firmware_backup"
    if (Test-Path $backupDir) {
        $backups = Get-ChildItem $backupDir -Directory | Sort-Object LastWriteTime -Descending
        if ($backups.Count -gt 0) {
            Write-Host "Available backups:" -ForegroundColor Yellow
            $i = 1
            foreach ($backup in $backups) {
                Write-Host "  $i. $($backup.Name)" -ForegroundColor White
                $i++
            }
            Write-Host ""
            $selection = Read-Host "Select backup to analyze (1-$($backups.Count))"
            $FirmwarePath = Join-Path $backups[$selection - 1].FullName "application.bin"
        }
    }
}

if (-not (Test-Path $FirmwarePath)) {
    Write-Host "[ERROR] Firmware file not found: $FirmwarePath" -ForegroundColor Red
    exit 1
}

# Create output directory
$OutputPath = Join-Path $ScriptDir $OutputDir
if (-not (Test-Path $OutputPath)) {
    New-Item -ItemType Directory -Path $OutputPath -Force | Out-Null
}

Write-Host "[INFO] Analyzing: $FirmwarePath" -ForegroundColor Yellow
Write-Host "[INFO] Output to: $OutputPath" -ForegroundColor Yellow
Write-Host ""

# Get file info
$fileInfo = Get-Item $FirmwarePath
Write-Host "File Information:" -ForegroundColor Cyan
Write-Host "  Size: $([math]::Round($fileInfo.Length / 1KB, 2)) KB ($($fileInfo.Length) bytes)" -ForegroundColor White
Write-Host "  Modified: $($fileInfo.LastWriteTime)" -ForegroundColor White
Write-Host ""

# Calculate hash
$hash = Get-FileHash $FirmwarePath -Algorithm SHA256
Write-Host "  SHA256: $($hash.Hash)" -ForegroundColor Gray
Write-Host ""

# ============================================================================
# Extract Strings
# ============================================================================
Write-Host "Extracting strings..." -ForegroundColor Cyan

$bytes = [System.IO.File]::ReadAllBytes($FirmwarePath)
$strings = @()
$currentString = ""
$minLength = 4

for ($i = 0; $i -lt $bytes.Length; $i++) {
    $byte = $bytes[$i]
    # Printable ASCII range (32-126)
    if ($byte -ge 32 -and $byte -le 126) {
        $currentString += [char]$byte
    } else {
        if ($currentString.Length -ge $minLength) {
            $strings += $currentString
        }
        $currentString = ""
    }
}

$stringsFile = Join-Path $OutputPath "strings.txt"
$strings | Out-File -FilePath $stringsFile -Encoding UTF8
Write-Host "  Extracted $($strings.Count) strings to strings.txt" -ForegroundColor Green

# ============================================================================
# Identify Libraries
# ============================================================================
Write-Host ""
Write-Host "Identifying libraries..." -ForegroundColor Cyan

$librarySignatures = @{
    "LovyanGFX" = @("LGFX", "Panel_GC9A01", "Panel_ST7789", "lgfx::", "LovyanGFX")
    "TFT_eSPI" = @("TFT_eSPI", "TFT_WIDTH", "TFT_HEIGHT", "tft.")
    "LVGL" = @("lv_obj", "lv_label", "lv_arc", "lv_btn", "LVGL", "lv_disp")
    "Arduino_GFX" = @("Arduino_GFX", "Arduino_ESP32", "GFX_CLASS")
    "Adafruit_GFX" = @("Adafruit_GFX", "Adafruit_SPITFT")
    "Adafruit_NeoPixel" = @("Adafruit_NeoPixel", "NeoPixel")
    "FastLED" = @("FastLED", "CRGB", "CHSV")
    "WiFi" = @("WiFi.begin", "WIFI_STA", "WIFI_AP", "WiFiClient")
    "BLE" = @("BLEDevice", "BLEServer", "BLECharacteristic", "NimBLE")
    "Audio" = @("I2S_", "AudioOutput", "ESP8266Audio", "AudioFileSource")
    "ESP-IDF" = @("esp_err", "ESP_LOG", "esp_wifi", "esp_bt", "nvs_flash")
    "FreeRTOS" = @("xTaskCreate", "vTaskDelay", "xQueue", "xSemaphore")
    "Touch_FT5x06" = @("FT5x06", "FT6206", "FT6336")
    "Touch_CST816" = @("CST816", "CST820")
    "Touch_GT911" = @("GT911", "Goodix")
    "SPI" = @("SPI.begin", "SPI.transfer", "SPIClass")
    "I2C/Wire" = @("Wire.begin", "Wire.write", "TwoWire")
    "SD Card" = @("SD.begin", "SD_MMC", "SdFat")
    "SPIFFS" = @("SPIFFS.begin", "SPIFFS.open")
    "LittleFS" = @("LittleFS.begin", "LittleFS.open")
    "ArduinoJSON" = @("JsonDocument", "deserializeJson", "ArduinoJson")
    "HTTPClient" = @("HTTPClient", "http.begin", "http.GET")
    "WebServer" = @("WebServer", "server.on", "server.begin")
    "OTA" = @("ArduinoOTA", "OTA.begin", "Update.begin")
    "MQTT" = @("PubSubClient", "mqtt.connect", "mqtt.publish")
}

$detectedLibraries = @{}
$allStringsText = $strings -join "`n"

foreach ($lib in $librarySignatures.Keys) {
    $matches = @()
    foreach ($sig in $librarySignatures[$lib]) {
        if ($allStringsText -match [regex]::Escape($sig)) {
            $matches += $sig
        }
    }
    if ($matches.Count -gt 0) {
        $detectedLibraries[$lib] = $matches
    }
}

if ($detectedLibraries.Count -gt 0) {
    Write-Host "  Detected libraries:" -ForegroundColor Green
    foreach ($lib in $detectedLibraries.Keys) {
        $sigs = $detectedLibraries[$lib] -join ", "
        Write-Host "    - $lib (matched: $sigs)" -ForegroundColor White
    }
} else {
    Write-Host "  No common libraries detected" -ForegroundColor Yellow
}

# ============================================================================
# Find Configuration Values
# ============================================================================
Write-Host ""
Write-Host "Searching for configuration values..." -ForegroundColor Cyan

# WiFi SSIDs/passwords
$wifiStrings = $strings | Where-Object { $_ -match "ssid|password|wifi|SSID|PASSWORD|WIFI" }
if ($wifiStrings.Count -gt 0) {
    Write-Host "  Possible WiFi configuration:" -ForegroundColor Yellow
    $wifiStrings | Select-Object -First 10 | ForEach-Object {
        Write-Host "    $_" -ForegroundColor Gray
    }
}

# URLs
$urlStrings = $strings | Where-Object { $_ -match "http://|https://|mqtt://|ws://" }
if ($urlStrings.Count -gt 0) {
    Write-Host "  URLs found:" -ForegroundColor Yellow
    $urlStrings | Select-Object -First 10 | ForEach-Object {
        Write-Host "    $_" -ForegroundColor Gray
    }
}

# Version strings
$versionStrings = $strings | Where-Object { $_ -match "v\d+\.\d+|version|VERSION|Ver\.|V\d+" }
if ($versionStrings.Count -gt 0) {
    Write-Host "  Version strings:" -ForegroundColor Yellow
    $versionStrings | Select-Object -First 10 | ForEach-Object {
        Write-Host "    $_" -ForegroundColor Gray
    }
}

# ============================================================================
# Find Display Configuration
# ============================================================================
Write-Host ""
Write-Host "Searching for display configuration..." -ForegroundColor Cyan

$displayStrings = $strings | Where-Object { 
    $_ -match "360|GC9A01|ST7789|ILI9341|SPI|LCD|TFT|display|DISPLAY|rotation|width|height"
}
if ($displayStrings.Count -gt 0) {
    Write-Host "  Display-related strings:" -ForegroundColor Yellow
    $displayStrings | Select-Object -First 20 | ForEach-Object {
        Write-Host "    $_" -ForegroundColor Gray
    }
}

# ============================================================================
# Generate Analysis Report
# ============================================================================
Write-Host ""
Write-Host "Generating analysis report..." -ForegroundColor Cyan

$reportFile = Join-Path $OutputPath "analysis_report.md"
$report = @"
# Firmware Analysis Report

**File**: $($fileInfo.Name)
**Size**: $([math]::Round($fileInfo.Length / 1KB, 2)) KB
**SHA256**: $($hash.Hash)
**Analyzed**: $(Get-Date -Format "yyyy-MM-dd HH:mm:ss")

## Detected Libraries

"@

foreach ($lib in $detectedLibraries.Keys) {
    $sigs = $detectedLibraries[$lib] -join ", "
    $report += "- **$lib**: $sigs`n"
}

$report += @"

## Recommended platformio.ini Configuration

Based on detected libraries, try this configuration:

``````ini
[env:esp32s3_display]
platform = espressif32
board = esp32-s3-devkitc-1
framework = arduino

lib_deps = 
"@

if ($detectedLibraries.ContainsKey("LovyanGFX")) {
    $report += "    lovyan03/LovyanGFX@^1.1.12`n"
}
if ($detectedLibraries.ContainsKey("LVGL")) {
    $report += "    lvgl/lvgl@^8.3.11`n"
}
if ($detectedLibraries.ContainsKey("TFT_eSPI")) {
    $report += "    bodmer/TFT_eSPI@^2.5.0`n"
}
if ($detectedLibraries.ContainsKey("Touch_FT5x06")) {
    $report += "    adafruit/Adafruit FT6206 Library@^1.1.0`n"
}
if ($detectedLibraries.ContainsKey("Audio")) {
    $report += "    earlephilhower/ESP8266Audio@^1.9.7`n"
}

$report += @"
``````

## Interesting Strings

See `strings.txt` for the complete list.

### Possible Function Names
"@

$functionStrings = $strings | Where-Object { $_ -match "^[a-z][a-zA-Z0-9_]+$" -and $_.Length -gt 6 -and $_.Length -lt 40 }
$report += "`n``````"
$functionStrings | Select-Object -First 50 | ForEach-Object { $report += "`n$_" }
$report += "`n```````n"

$report += @"

## Next Steps

1. Review `strings.txt` for more clues
2. Use Ghidra to analyze the binary structure
3. Match the display driver and pin configuration
4. Reconstruct the main.cpp based on identified patterns

"@

$report | Out-File -FilePath $reportFile -Encoding UTF8
Write-Host "  Report saved to: $reportFile" -ForegroundColor Green

# ============================================================================
# Summary
# ============================================================================
Write-Host ""
Write-Host "============================================" -ForegroundColor Green
Write-Host "Analysis Complete!" -ForegroundColor Green
Write-Host "============================================" -ForegroundColor Green
Write-Host ""
Write-Host "Output files:" -ForegroundColor Cyan
Write-Host "  - $stringsFile" -ForegroundColor White
Write-Host "  - $reportFile" -ForegroundColor White
Write-Host ""
Write-Host "Next steps:" -ForegroundColor Yellow
Write-Host "  1. Review the analysis report" -ForegroundColor White
Write-Host "  2. Search strings.txt for specific features" -ForegroundColor White
Write-Host "  3. Use Ghidra for deeper binary analysis" -ForegroundColor White
Write-Host "  4. Update display/src/main.cpp to match" -ForegroundColor White
