# ============================================================================
# ESP32-S3 Firmware Comparison Tool
# ============================================================================
# Compares two firmware binaries to identify differences
# Useful when reverse-engineering or validating changes
# ============================================================================

param(
    [Parameter(Mandatory=$false)]
    [string]$File1 = "",
    
    [Parameter(Mandatory=$false)]
    [string]$File2 = ""
)

$ErrorActionPreference = "Stop"
$ScriptDir = Split-Path -Parent $PSScriptRoot

Write-Host "============================================" -ForegroundColor Cyan
Write-Host "ESP32-S3 Firmware Comparison Tool" -ForegroundColor Cyan
Write-Host "============================================" -ForegroundColor Cyan
Write-Host ""

# If files not specified, prompt for them
if ([string]::IsNullOrEmpty($File1) -or [string]::IsNullOrEmpty($File2)) {
    $backupDir = Join-Path $ScriptDir "firmware_backup"
    
    if (Test-Path $backupDir) {
        $backups = Get-ChildItem $backupDir -Directory | Sort-Object LastWriteTime -Descending
        
        if ($backups.Count -ge 2) {
            Write-Host "Available backups:" -ForegroundColor Yellow
            $i = 1
            foreach ($backup in $backups) {
                $flashFile = Join-Path $backup.FullName "flash_backup_full.bin"
                $exists = if (Test-Path $flashFile) { "[OK]" } else { "[MISSING]" }
                Write-Host "  $i. $($backup.Name) $exists" -ForegroundColor White
                $i++
            }
            
            Write-Host ""
            $sel1 = Read-Host "Select first backup (1-$($backups.Count))"
            $sel2 = Read-Host "Select second backup (1-$($backups.Count))"
            
            $File1 = Join-Path $backups[$sel1 - 1].FullName "flash_backup_full.bin"
            $File2 = Join-Path $backups[$sel2 - 1].FullName "flash_backup_full.bin"
        } else {
            Write-Host "[ERROR] Need at least 2 backups to compare" -ForegroundColor Red
            exit 1
        }
    } else {
        Write-Host "[ERROR] No backup directory found" -ForegroundColor Red
        exit 1
    }
}

# Verify files exist
if (-not (Test-Path $File1)) {
    Write-Host "[ERROR] File not found: $File1" -ForegroundColor Red
    exit 1
}

if (-not (Test-Path $File2)) {
    Write-Host "[ERROR] File not found: $File2" -ForegroundColor Red
    exit 1
}

Write-Host ""
Write-Host "Comparing:" -ForegroundColor Yellow
Write-Host "  File 1: $File1" -ForegroundColor White
Write-Host "  File 2: $File2" -ForegroundColor White
Write-Host ""

# Get file info
$info1 = Get-Item $File1
$info2 = Get-Item $File2

Write-Host "File Information:" -ForegroundColor Yellow
Write-Host "  File 1: $([math]::Round($info1.Length / 1MB, 2)) MB" -ForegroundColor White
Write-Host "  File 2: $([math]::Round($info2.Length / 1MB, 2)) MB" -ForegroundColor White

# Calculate hashes
Write-Host ""
Write-Host "Calculating hashes..." -ForegroundColor Yellow

$hash1 = Get-FileHash $File1 -Algorithm SHA256
$hash2 = Get-FileHash $File2 -Algorithm SHA256

Write-Host "  File 1 SHA256: $($hash1.Hash.Substring(0, 16))..." -ForegroundColor White
Write-Host "  File 2 SHA256: $($hash2.Hash.Substring(0, 16))..." -ForegroundColor White

if ($hash1.Hash -eq $hash2.Hash) {
    Write-Host ""
    Write-Host "[MATCH] Files are identical!" -ForegroundColor Green
} else {
    Write-Host ""
    Write-Host "[DIFFERENT] Files have differences" -ForegroundColor Yellow
    
    # Read bytes and find differences
    Write-Host ""
    Write-Host "Analyzing differences (this may take a moment)..." -ForegroundColor Yellow
    
    $bytes1 = [System.IO.File]::ReadAllBytes($File1)
    $bytes2 = [System.IO.File]::ReadAllBytes($File2)
    
    $minLen = [Math]::Min($bytes1.Length, $bytes2.Length)
    $diffCount = 0
    $diffRegions = @()
    $inDiff = $false
    $diffStart = 0
    
    for ($i = 0; $i -lt $minLen; $i++) {
        if ($bytes1[$i] -ne $bytes2[$i]) {
            $diffCount++
            if (-not $inDiff) {
                $inDiff = $true
                $diffStart = $i
            }
        } else {
            if ($inDiff) {
                $inDiff = $false
                $diffRegions += @{
                    Start = $diffStart
                    End = $i - 1
                    Size = $i - $diffStart
                }
            }
        }
    }
    
    # Close last diff region if needed
    if ($inDiff) {
        $diffRegions += @{
            Start = $diffStart
            End = $minLen - 1
            Size = $minLen - $diffStart
        }
    }
    
    Write-Host ""
    Write-Host "Difference Summary:" -ForegroundColor Yellow
    Write-Host "  Total bytes different: $diffCount" -ForegroundColor White
    Write-Host "  Number of diff regions: $($diffRegions.Count)" -ForegroundColor White
    
    if ($diffRegions.Count -gt 0 -and $diffRegions.Count -le 20) {
        Write-Host ""
        Write-Host "Diff Regions:" -ForegroundColor Yellow
        foreach ($region in $diffRegions) {
            $startHex = "0x" + $region.Start.ToString("X8")
            $endHex = "0x" + $region.End.ToString("X8")
            Write-Host "  $startHex - $endHex ($($region.Size) bytes)" -ForegroundColor White
        }
    }
    
    # Identify which ESP32-S3 partition each diff is in
    Write-Host ""
    Write-Host "Partition Analysis:" -ForegroundColor Yellow
    
    $partitions = @(
        @{ Name = "Bootloader"; Start = 0x0; End = 0x8000 }
        @{ Name = "Partition Table"; Start = 0x8000; End = 0x9000 }
        @{ Name = "NVS"; Start = 0x9000; End = 0xE000 }
        @{ Name = "OTA Data"; Start = 0xE000; End = 0x10000 }
        @{ Name = "App0 (OTA_0)"; Start = 0x10000; End = 0x310000 }
        @{ Name = "App1 (OTA_1)"; Start = 0x310000; End = 0x610000 }
        @{ Name = "SPIFFS/LittleFS"; Start = 0x610000; End = 0x800000 }
    )
    
    foreach ($partition in $partitions) {
        $partitionDiffs = $diffRegions | Where-Object {
            $_.Start -ge $partition.Start -and $_.Start -lt $partition.End
        }
        
        if ($partitionDiffs.Count -gt 0) {
            $totalBytes = ($partitionDiffs | Measure-Object -Property Size -Sum).Sum
            Write-Host "  $($partition.Name): $($partitionDiffs.Count) regions, $totalBytes bytes different" -ForegroundColor Yellow
        } else {
            Write-Host "  $($partition.Name): No differences" -ForegroundColor Green
        }
    }
}

Write-Host ""
Write-Host "============================================" -ForegroundColor Cyan
Write-Host "Comparison Complete" -ForegroundColor Cyan
Write-Host "============================================" -ForegroundColor Cyan
