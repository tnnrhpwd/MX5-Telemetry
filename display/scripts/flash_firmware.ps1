# ============================================================================
# ESP32-S3 Firmware Flash Script
# ============================================================================
# This script flashes firmware to an ESP32-S3 device
# Can be used to restore backed-up firmware or flash new development builds
# ============================================================================

param(
    [Parameter(Mandatory=$false)]
    [string]$ComPort = "",
    
    [Parameter(Mandatory=$false)]
    [string]$FirmwarePath = "",
    
    [Parameter(Mandatory=$false)]
    [switch]$EraseFlash,
    
    [Parameter(Mandatory=$false)]
    [switch]$Development
)

$ErrorActionPreference = "Stop"
$ScriptDir = Split-Path -Parent $PSScriptRoot

Write-Host "============================================" -ForegroundColor Cyan
Write-Host "ESP32-S3 Firmware Flash Tool" -ForegroundColor Cyan
Write-Host "============================================" -ForegroundColor Cyan
Write-Host ""

# Auto-detect COM port if not specified
if ([string]::IsNullOrEmpty($ComPort)) {
    Write-Host "[INFO] Scanning for ESP32-S3 devices..." -ForegroundColor Yellow
    
    $ports = Get-CimInstance -ClassName Win32_PnPEntity | Where-Object {
        $_.Name -match "COM\d+" -and ($_.Name -match "USB|Serial|ESP32|Silicon Labs|CH340")
    }
    
    if ($ports.Count -eq 0) {
        Write-Host "[ERROR] No serial devices found. Please connect your ESP32-S3." -ForegroundColor Red
        exit 1
    }
    
    if ($ports.Count -eq 1) {
        if ($ports[0].Name -match "(COM\d+)") {
            $ComPort = $Matches[1]
        }
        Write-Host "[OK] Found device: $ComPort" -ForegroundColor Green
    } else {
        Write-Host "[INFO] Multiple devices found:" -ForegroundColor Yellow
        $i = 1
        foreach ($port in $ports) {
            Write-Host "  $i. $($port.Name)" -ForegroundColor White
            $i++
        }
        $selection = Read-Host "Select device number (1-$($ports.Count))"
        $selectedPort = $ports[$selection - 1]
        if ($selectedPort.Name -match "(COM\d+)") {
            $ComPort = $Matches[1]
        }
    }
}

# Check for esptool
$esptoolPath = $null
$pioEsptoolExe = Join-Path $env:USERPROFILE ".platformio\packages\tool-esptoolpy\esptool.exe"

if (Test-Path $pioEsptoolExe) {
    $esptoolPath = $pioEsptoolExe
} else {
    $systemEsptool = Get-Command esptool.py -ErrorAction SilentlyContinue
    if ($systemEsptool) {
        $esptoolPath = "esptool.py"
    } else {
        Write-Host "[ERROR] esptool not found!" -ForegroundColor Red
        Write-Host "        Install with: pip install esptool" -ForegroundColor Yellow
        exit 1
    }
}

Write-Host "[OK] Using esptool: $esptoolPath" -ForegroundColor Green

# Determine what to flash
if ($Development) {
    # Flash the development build from PlatformIO
    Write-Host ""
    Write-Host "[INFO] Flashing development build..." -ForegroundColor Yellow
    
    $buildDir = Join-Path $ScriptDir ".pio\build\esp32s3_display"
    $firmwareFile = Join-Path $buildDir "firmware.bin"
    $partitionsFile = Join-Path $buildDir "partitions.bin"
    $bootloaderFile = Join-Path $buildDir "bootloader.bin"
    
    if (-not (Test-Path $firmwareFile)) {
        Write-Host "[ERROR] No build found. Run 'pio run -d display' first." -ForegroundColor Red
        exit 1
    }
    
    if ($EraseFlash) {
        Write-Host "[INFO] Erasing flash..." -ForegroundColor Yellow
        & $esptoolPath --port $ComPort --chip esp32s3 erase_flash
    }
    
    Write-Host "[INFO] Flashing firmware..." -ForegroundColor Yellow
    & $esptoolPath --port $ComPort --chip esp32s3 --baud 921600 `
        write_flash -z `
        --flash_mode dio `
        --flash_freq 80m `
        --flash_size 16MB `
        0x0 $bootloaderFile `
        0x8000 $partitionsFile `
        0x10000 $firmwareFile
        
} elseif (-not [string]::IsNullOrEmpty($FirmwarePath)) {
    # Flash a backup file
    Write-Host ""
    Write-Host "[INFO] Flashing backup firmware: $FirmwarePath" -ForegroundColor Yellow
    
    if (-not (Test-Path $FirmwarePath)) {
        Write-Host "[ERROR] Firmware file not found: $FirmwarePath" -ForegroundColor Red
        exit 1
    }
    
    if ($EraseFlash) {
        Write-Host "[INFO] Erasing flash..." -ForegroundColor Yellow
        & $esptoolPath --port $ComPort --chip esp32s3 erase_flash
    }
    
    $fileSize = (Get-Item $FirmwarePath).Length
    $sizeMB = [math]::Round($fileSize / 1MB, 2)
    Write-Host "[INFO] File size: $sizeMB MB" -ForegroundColor White
    Write-Host "[INFO] This may take several minutes..." -ForegroundColor Yellow
    
    & $esptoolPath --port $ComPort --chip esp32s3 --baud 921600 `
        write_flash -z `
        --flash_mode dio `
        --flash_freq 80m `
        0x0 $FirmwarePath
        
} else {
    # Interactive menu
    Write-Host ""
    Write-Host "What would you like to flash?" -ForegroundColor Cyan
    Write-Host "  1. Development build (from pio run)" -ForegroundColor White
    Write-Host "  2. Backup firmware file" -ForegroundColor White
    Write-Host "  3. Erase flash only" -ForegroundColor White
    Write-Host ""
    $choice = Read-Host "Select option (1-3)"
    
    switch ($choice) {
        "1" {
            & $PSCommandPath -ComPort $ComPort -Development
        }
        "2" {
            $backupDir = Join-Path $ScriptDir "firmware_backup"
            if (Test-Path $backupDir) {
                $backups = Get-ChildItem $backupDir -Directory | Sort-Object LastWriteTime -Descending
                if ($backups.Count -gt 0) {
                    Write-Host ""
                    Write-Host "Available backups:" -ForegroundColor Cyan
                    $i = 1
                    foreach ($backup in $backups) {
                        Write-Host "  $i. $($backup.Name)" -ForegroundColor White
                        $i++
                    }
                    $selection = Read-Host "Select backup (1-$($backups.Count))"
                    $selectedBackup = $backups[$selection - 1]
                    $firmwareFile = Join-Path $selectedBackup.FullName "flash_backup_full.bin"
                    
                    if (Test-Path $firmwareFile) {
                        & $PSCommandPath -ComPort $ComPort -FirmwarePath $firmwareFile
                    } else {
                        Write-Host "[ERROR] flash_backup_full.bin not found in backup" -ForegroundColor Red
                    }
                } else {
                    Write-Host "[ERROR] No backups found" -ForegroundColor Red
                }
            } else {
                Write-Host "[ERROR] No backup directory found" -ForegroundColor Red
            }
        }
        "3" {
            Write-Host "[INFO] Erasing flash..." -ForegroundColor Yellow
            & $esptoolPath --port $ComPort --chip esp32s3 erase_flash
        }
    }
}

Write-Host ""
Write-Host "============================================" -ForegroundColor Green
Write-Host "Flash Complete!" -ForegroundColor Green
Write-Host "============================================" -ForegroundColor Green
