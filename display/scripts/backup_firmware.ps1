# ============================================================================
# ESP32-S3 Firmware Backup Script
# ============================================================================
# This script backs up the complete firmware from an ESP32-S3 device
# Use this to pull the binary from your friend's module before redeveloping
# ============================================================================

param(
    [Parameter(Mandatory = $false)]
    [string]$ComPort = "",
    
    [Parameter(Mandatory = $false)]
    [string]$OutputDir = "firmware_backup",
    
    [Parameter(Mandatory = $false)]
    [string]$FlashSize = "16MB"
)

$ErrorActionPreference = "Stop"

Write-Host "============================================" -ForegroundColor Cyan
Write-Host "ESP32-S3 Firmware Backup Tool" -ForegroundColor Cyan
Write-Host "============================================" -ForegroundColor Cyan
Write-Host ""

# Create output directory
$BackupDir = Join-Path $PSScriptRoot "..\$OutputDir"
$Timestamp = Get-Date -Format "yyyy-MM-dd_HH-mm-ss"
$BackupPath = Join-Path $BackupDir $Timestamp

if (-not (Test-Path $BackupPath)) {
    New-Item -ItemType Directory -Path $BackupPath -Force | Out-Null
    Write-Host "[OK] Created backup directory: $BackupPath" -ForegroundColor Green
}

# Auto-detect COM port if not specified
if ([string]::IsNullOrEmpty($ComPort)) {
    Write-Host "[INFO] Scanning for ESP32-S3 devices..." -ForegroundColor Yellow
    
    $ports = Get-WmiObject Win32_SerialPort | Where-Object { 
        $_.Description -match "USB|Serial|ESP32|CP210|CH340|FTDI" 
    }
    
    if ($ports.Count -eq 0) {
        # Try alternative detection
        $ports = Get-CimInstance -ClassName Win32_PnPEntity | Where-Object {
            $_.Name -match "COM\d+" -and ($_.Name -match "USB|Serial|ESP32|Silicon Labs|CH340")
        }
    }
    
    if ($ports.Count -eq 0) {
        Write-Host "[ERROR] No serial devices found. Please connect your ESP32-S3." -ForegroundColor Red
        Write-Host "        Make sure drivers are installed (CP210x or CH340)" -ForegroundColor Red
        exit 1
    }
    
    if ($ports.Count -eq 1) {
        $ComPort = ($ports[0].Name -match "COM\d+")[0]
        if ($ports[0].DeviceID) {
            $ComPort = $ports[0].DeviceID
        }
        elseif ($ports[0].Name -match "(COM\d+)") {
            $ComPort = $Matches[1]
        }
        Write-Host "[OK] Found device: $ComPort" -ForegroundColor Green
    }
    else {
        Write-Host "[INFO] Multiple devices found:" -ForegroundColor Yellow
        $i = 1
        foreach ($port in $ports) {
            $portName = if ($port.DeviceID) { $port.DeviceID } else { $port.Name }
            Write-Host "  $i. $portName - $($port.Description)" -ForegroundColor White
            $i++
        }
        $selection = Read-Host "Select device number (1-$($ports.Count))"
        $selectedPort = $ports[$selection - 1]
        if ($selectedPort.DeviceID) {
            $ComPort = $selectedPort.DeviceID
        }
        else {
            if ($selectedPort.Name -match "(COM\d+)") {
                $ComPort = $Matches[1]
            }
        }
    }
}

Write-Host ""
Write-Host "[INFO] Backup Configuration:" -ForegroundColor Cyan
Write-Host "       Port: $ComPort" -ForegroundColor White
Write-Host "       Flash Size: $FlashSize" -ForegroundColor White
Write-Host "       Output: $BackupPath" -ForegroundColor White
Write-Host ""

# Calculate flash size in bytes
$FlashSizeBytes = switch ($FlashSize) {
    "4MB" { "0x400000" }
    "8MB" { "0x800000" }
    "16MB" { "0x1000000" }
    "32MB" { "0x2000000" }
    default { "0x1000000" }
}

# Check if esptool is available
$esptoolPath = $null

# Try PlatformIO's esptool first
$pioEsptool = Join-Path $env:USERPROFILE ".platformio\packages\tool-esptoolpy\esptool.py"
$pioEsptoolExe = Join-Path $env:USERPROFILE ".platformio\packages\tool-esptoolpy\esptool.exe"

if (Test-Path $pioEsptoolExe) {
    $esptoolPath = $pioEsptoolExe
    Write-Host "[OK] Using PlatformIO esptool: $esptoolPath" -ForegroundColor Green
}
elseif (Test-Path $pioEsptool) {
    $esptoolPath = "python `"$pioEsptool`""
    Write-Host "[OK] Using PlatformIO esptool.py: $pioEsptool" -ForegroundColor Green
}
else {
    # Try system esptool
    $systemEsptool = Get-Command esptool.py -ErrorAction SilentlyContinue
    if ($systemEsptool) {
        $esptoolPath = "esptool.py"
        Write-Host "[OK] Using system esptool.py" -ForegroundColor Green
    }
    else {
        Write-Host "[ERROR] esptool not found!" -ForegroundColor Red
        Write-Host "        Install with: pip install esptool" -ForegroundColor Yellow
        Write-Host "        Or run: pio pkg install -g tool-esptoolpy" -ForegroundColor Yellow
        exit 1
    }
}

Write-Host ""
Write-Host "[INFO] Starting firmware backup..." -ForegroundColor Yellow
Write-Host "[WARN] This may take several minutes for a 16MB flash." -ForegroundColor Yellow
Write-Host ""

# Read flash info first
Write-Host "Step 1/4: Reading flash information..." -ForegroundColor Cyan
$flashInfoFile = Join-Path $BackupPath "flash_info.txt"
$cmd = "$esptoolPath --port $ComPort --chip esp32s3 flash_id"
Write-Host "  Command: $cmd" -ForegroundColor DarkGray
Invoke-Expression $cmd | Tee-Object -FilePath $flashInfoFile

Write-Host ""

# Read MAC address
Write-Host "Step 2/4: Reading device information..." -ForegroundColor Cyan
$deviceInfoFile = Join-Path $BackupPath "device_info.txt"
$cmd = "$esptoolPath --port $ComPort --chip esp32s3 chip_id"
Invoke-Expression $cmd | Tee-Object -FilePath $deviceInfoFile

Write-Host ""

# Backup complete flash
Write-Host "Step 3/4: Backing up complete flash ($FlashSize)..." -ForegroundColor Cyan
$flashBackupFile = Join-Path $BackupPath "flash_backup_full.bin"
$cmd = "$esptoolPath --port $ComPort --chip esp32s3 --baud 921600 read_flash 0x0 $FlashSizeBytes `"$flashBackupFile`""
Write-Host "  Command: $cmd" -ForegroundColor DarkGray
Write-Host "  This will take a few minutes..." -ForegroundColor Yellow
Invoke-Expression $cmd

Write-Host ""

# Backup individual partitions
Write-Host "Step 4/4: Backing up individual partitions..." -ForegroundColor Cyan

# Bootloader (usually at 0x0 or 0x1000 for ESP32-S3)
$bootloaderFile = Join-Path $BackupPath "bootloader.bin"
$cmd = "$esptoolPath --port $ComPort --chip esp32s3 --baud 921600 read_flash 0x0 0x8000 `"$bootloaderFile`""
Write-Host "  Bootloader..." -ForegroundColor White
Invoke-Expression $cmd

# Partition table (at 0x8000)
$partitionFile = Join-Path $BackupPath "partition_table.bin"
$cmd = "$esptoolPath --port $ComPort --chip esp32s3 --baud 921600 read_flash 0x8000 0x1000 `"$partitionFile`""
Write-Host "  Partition table..." -ForegroundColor White
Invoke-Expression $cmd

# Application (at 0x10000, 3MB)
$appFile = Join-Path $BackupPath "application.bin"
$cmd = "$esptoolPath --port $ComPort --chip esp32s3 --baud 921600 read_flash 0x10000 0x300000 `"$appFile`""
Write-Host "  Application (may take a minute)..." -ForegroundColor White
Invoke-Expression $cmd

Write-Host ""
Write-Host "============================================" -ForegroundColor Green
Write-Host "Backup Complete!" -ForegroundColor Green
Write-Host "============================================" -ForegroundColor Green
Write-Host ""
Write-Host "Backup files saved to: $BackupPath" -ForegroundColor Cyan
Write-Host ""
Write-Host "Files created:" -ForegroundColor White
Get-ChildItem $BackupPath | ForEach-Object {
    $sizeKB = [math]::Round($_.Length / 1KB, 2)
    $sizeMB = [math]::Round($_.Length / 1MB, 2)
    if ($sizeMB -ge 1) {
        Write-Host "  - $($_.Name) ($sizeMB MB)" -ForegroundColor Gray
    }
    else {
        Write-Host "  - $($_.Name) ($sizeKB KB)" -ForegroundColor Gray
    }
}

Write-Host ""
Write-Host "To restore this firmware to another device, use:" -ForegroundColor Yellow
Write-Host "  .\flash_firmware.ps1 -FirmwarePath `"$BackupPath\flash_backup_full.bin`"" -ForegroundColor White
