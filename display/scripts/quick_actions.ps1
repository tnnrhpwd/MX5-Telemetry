# ============================================================================
# ESP32-S3 Quick Actions Menu
# ============================================================================
# Interactive menu for common ESP32-S3 development tasks
# ============================================================================

$ErrorActionPreference = "Stop"
$ScriptDir = Split-Path -Parent $PSScriptRoot

function Show-Menu {
    Clear-Host
    Write-Host "============================================" -ForegroundColor Cyan
    Write-Host "ESP32-S3 Round Display - Quick Actions" -ForegroundColor Cyan
    Write-Host "============================================" -ForegroundColor Cyan
    Write-Host ""
    Write-Host "  FIRMWARE MANAGEMENT" -ForegroundColor Yellow
    Write-Host "    1. Backup firmware from device" -ForegroundColor White
    Write-Host "    2. Flash firmware to device" -ForegroundColor White
    Write-Host "    3. Erase device flash" -ForegroundColor White
    Write-Host ""
    Write-Host "  DEVELOPMENT" -ForegroundColor Yellow
    Write-Host "    4. Build project" -ForegroundColor White
    Write-Host "    5. Build and upload" -ForegroundColor White
    Write-Host "    6. Upload only" -ForegroundColor White
    Write-Host "    7. Serial monitor" -ForegroundColor White
    Write-Host ""
    Write-Host "  REVERSE ENGINEERING" -ForegroundColor Yellow
    Write-Host "    8. Analyze firmware (identify libraries)" -ForegroundColor White
    Write-Host "    9. Compare two firmwares" -ForegroundColor White
    Write-Host ""
    Write-Host "  UTILITIES" -ForegroundColor Yellow
    Write-Host "    A. Check device info" -ForegroundColor White
    Write-Host "    B. List COM ports" -ForegroundColor White
    Write-Host ""
    Write-Host "    Q. Quit" -ForegroundColor DarkGray
    Write-Host ""
}

function Wait-ForKey {
    Write-Host ""
    Write-Host "Press any key to continue..." -ForegroundColor DarkGray
    $null = $Host.UI.RawUI.ReadKey("NoEcho,IncludeKeyDown")
}

do {
    Show-Menu
    $choice = Read-Host "Select option"
    
    switch ($choice.ToUpper()) {
        "1" {
            Write-Host ""
            & "$PSScriptRoot\backup_firmware.ps1"
            Wait-ForKey
        }
        "2" {
            Write-Host ""
            & "$PSScriptRoot\flash_firmware.ps1"
            Wait-ForKey
        }
        "3" {
            Write-Host ""
            Write-Host "[WARN] This will erase ALL data on the device!" -ForegroundColor Red
            $confirm = Read-Host "Are you sure? (yes/no)"
            if ($confirm -eq "yes") {
                & "$PSScriptRoot\flash_firmware.ps1" -EraseFlash
            }
            Wait-ForKey
        }
        "4" {
            Write-Host ""
            Push-Location $ScriptDir
            pio run
            Pop-Location
            Wait-ForKey
        }
        "5" {
            Write-Host ""
            Push-Location $ScriptDir
            pio run --target upload
            Pop-Location
            Wait-ForKey
        }
        "6" {
            Write-Host ""
            & "$PSScriptRoot\flash_firmware.ps1" -Development
            Wait-ForKey
        }
        "7" {
            Write-Host ""
            Push-Location $ScriptDir
            pio device monitor -b 115200
            Pop-Location
        }
        "8" {
            Write-Host ""
            & "$PSScriptRoot\analyze_firmware.ps1"
            Wait-ForKey
        }
        "9" {
            Write-Host ""
            & "$PSScriptRoot\compare_firmware.ps1"
            Wait-ForKey
        }
        "A" {
            Write-Host ""
            $esptoolPath = Join-Path $env:USERPROFILE ".platformio\packages\tool-esptoolpy\esptool.exe"
            if (Test-Path $esptoolPath) {
                $port = Read-Host "COM port"
                & $esptoolPath --port $port --chip esp32s3 chip_id
                & $esptoolPath --port $port --chip esp32s3 flash_id
            }
            else {
                Write-Host "[ERROR] esptool not found" -ForegroundColor Red
            }
            Wait-ForKey
        }
        "B" {
            Write-Host ""
            Get-CimInstance -ClassName Win32_PnPEntity | Where-Object {
                $_.Name -match "COM\d+"
            } | ForEach-Object {
                Write-Host "  $($_.Name)" -ForegroundColor White
            }
            Wait-ForKey
        }
        "Q" {
            Write-Host "Goodbye!" -ForegroundColor Cyan
        }
        default {
            Write-Host "Invalid option" -ForegroundColor Red
            Start-Sleep -Seconds 1
        }
    }
} while ($choice.ToUpper() -ne "Q")
