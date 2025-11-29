# Upload Arduinos with automatic identification and validation
# Supports selective upload when only one Arduino is connected
param(
    [string]$MasterPort = "COM3",
    [string]$SlavePort = "COM4"
)

Write-Host ""
Write-Host "=== Arduino Identification & Upload ===" -ForegroundColor Cyan
Write-Host ""

# Function to check if port exists
function Test-PortExists {
    param([string]$Port)
    $ports = [System.IO.Ports.SerialPort]::GetPortNames()
    return $ports -contains $Port
}

# Function to identify Arduino
function Identify-Arduino {
    param([string]$Port)
    
    if (-not (Test-PortExists -Port $Port)) {
        return "NOT_CONNECTED"
    }
    
    try {
        $serialPort = New-Object System.IO.Ports.SerialPort
        $serialPort.PortName = $Port
        $serialPort.BaudRate = 115200
        $serialPort.ReadTimeout = 2000
        $serialPort.DtrEnable = $true
        $serialPort.RtsEnable = $true
        
        $serialPort.Open()
        Start-Sleep -Milliseconds 500
        
        $output = ""
        $startTime = Get-Date
        
        while (((Get-Date) - $startTime).TotalSeconds -lt 2) {
            if ($serialPort.BytesToRead -gt 0) {
                $output += $serialPort.ReadExisting()
            }
            Start-Sleep -Milliseconds 100
        }
        
        $serialPort.Close()
        
        if ($output -match "MX5v3") {
            return "MASTER"
        }
        elseif ($output.Length -gt 0) {
            return "SLAVE"
        }
        else {
            return "UNKNOWN"
        }
    }
    catch {
        return "ERROR"
    }
}

# Step 1: Identify current state
Write-Host "Step 1: Detecting connected Arduinos..." -ForegroundColor Yellow
$currentMaster = Identify-Arduino -Port $MasterPort
$currentSlave = Identify-Arduino -Port $SlavePort

$masterConnected = $currentMaster -ne "NOT_CONNECTED"
$slaveConnected = $currentSlave -ne "NOT_CONNECTED"

Write-Host "  $MasterPort : $currentMaster" -ForegroundColor $(if ($currentMaster -eq "MASTER") { "Green" } elseif ($currentMaster -eq "NOT_CONNECTED") { "DarkGray" } else { "Yellow" })
Write-Host "  $SlavePort  : $currentSlave" -ForegroundColor $(if ($currentSlave -eq "SLAVE" -or $currentSlave -eq "UNKNOWN") { "Green" } elseif ($currentSlave -eq "NOT_CONNECTED") { "DarkGray" } else { "Yellow" })
Write-Host ""

if (-not $masterConnected -and -not $slaveConnected) {
    Write-Host "[X] No Arduinos detected on $MasterPort or $SlavePort" -ForegroundColor Red
    Write-Host "  Please connect at least one Arduino and try again." -ForegroundColor Yellow
    exit 1
}

# Step 2: Auto-swap if master detected on slave port
if ($currentSlave -eq "MASTER") {
    Write-Host "[!] WARNING: MASTER firmware detected on $SlavePort!" -ForegroundColor Red
    Write-Host "  Auto-swapping ports..." -ForegroundColor Yellow
    $temp = $MasterPort
    $MasterPort = $SlavePort
    $SlavePort = $temp
    $temp = $masterConnected
    $masterConnected = $slaveConnected
    $slaveConnected = $temp
    Write-Host "  Ports swapped: Master=$MasterPort, Slave=$SlavePort" -ForegroundColor Cyan
    Write-Host ""
}

# Step 3: Determine upload strategy
Write-Host "Step 2: Planning upload strategy..." -ForegroundColor Yellow
$uploadMaster = $masterConnected
$uploadSlave = $slaveConnected

if ($uploadMaster -and $uploadSlave) {
    Write-Host "  [OK] Both Arduinos detected - uploading both" -ForegroundColor Green
}
elseif ($uploadMaster) {
    Write-Host "  [!] Only Master Arduino detected - uploading master only" -ForegroundColor Yellow
}
elseif ($uploadSlave) {
    Write-Host "  [!] Only Slave Arduino detected - uploading slave only" -ForegroundColor Yellow
}
Write-Host ""

# Step 4: Upload firmware
Write-Host "Step 3: Uploading firmware..." -ForegroundColor Yellow

$jobs = @()
$uploadCount = 0

if ($uploadMaster) {
    Write-Host "  -> Master -> $MasterPort" -ForegroundColor Cyan
    $masterJob = Start-Job -ScriptBlock {
        param($port)
        Set-Location "C:\Users\tanne\Documents\Github\MX5-Telemetry"
        $pioPath = "C:\Users\tanne\AppData\Local\Packages\PythonSoftwareFoundation.Python.3.11_qbz5n2kfra8p0\LocalCache\local-packages\Python311\Scripts\pio.exe"
        & $pioPath run -d master -t upload --upload-port $port 2>&1
    } -ArgumentList $MasterPort
    $jobs += @{Job = $masterJob; Name = "Master"; Port = $MasterPort}
    $uploadCount++
}
else {
    Write-Host "  [SKIP] Master (not connected)" -ForegroundColor DarkGray
}

if ($uploadSlave) {
    Write-Host "  -> Slave  -> $SlavePort" -ForegroundColor Cyan
    $slaveJob = Start-Job -ScriptBlock {
        param($port)
        Set-Location "C:\Users\tanne\Documents\Github\MX5-Telemetry"
        $pioPath = "C:\Users\tanne\AppData\Local\Packages\PythonSoftwareFoundation.Python.3.11_qbz5n2kfra8p0\LocalCache\local-packages\Python311\Scripts\pio.exe"
        & $pioPath run -d slave -t upload --upload-port $port 2>&1
    } -ArgumentList $SlavePort
    $jobs += @{Job = $slaveJob; Name = "Slave"; Port = $SlavePort}
    $uploadCount++
}
else {
    Write-Host "  [SKIP] Slave  (not connected)" -ForegroundColor DarkGray
}

Write-Host ""
Write-Host "Waiting for $uploadCount upload$(if ($uploadCount -ne 1) {'s'}) to complete..." -ForegroundColor Gray

# Wait for all jobs and collect results
$results = @{}
foreach ($jobInfo in $jobs) {
    $result = Receive-Job -Job $jobInfo.Job -Wait
    $results[$jobInfo.Name] = $result
    Remove-Job -Job $jobInfo.Job
}

# Step 5: Check results
Write-Host ""
Write-Host "=== Upload Results ===" -ForegroundColor Cyan

if ($uploadMaster) {
    if ($results["Master"] -match "SUCCESS") {
        Write-Host "  [OK] Master upload successful ($MasterPort)" -ForegroundColor Green
    }
    else {
        Write-Host "  [X] Master upload failed ($MasterPort)" -ForegroundColor Red
        Write-Host "    Error details:" -ForegroundColor Gray
        $errorLines = $results["Master"] | Select-String -Pattern "error|Error|ERROR|failed"
        if ($errorLines) {
            foreach ($line in $errorLines) {
                Write-Host "    $line" -ForegroundColor DarkRed
            }
        }
    }
}

if ($uploadSlave) {
    if ($results["Slave"] -match "SUCCESS") {
        Write-Host "  [OK] Slave upload successful ($SlavePort)" -ForegroundColor Green
    }
    else {
        Write-Host "  [X] Slave upload failed ($SlavePort)" -ForegroundColor Red
        Write-Host "    Error details:" -ForegroundColor Gray
        $errorLines = $results["Slave"] | Select-String -Pattern "error|Error|ERROR|failed"
        if ($errorLines) {
            foreach ($line in $errorLines) {
                Write-Host "    $line" -ForegroundColor DarkRed
            }
        }
    }
}

# Step 6: Verify new state
Write-Host ""
Write-Host "Step 4: Verifying uploaded firmware..." -ForegroundColor Yellow
Start-Sleep -Seconds 2

$verifyCount = 0
$verifySuccess = 0

if ($uploadMaster) {
    $newMaster = Identify-Arduino -Port $MasterPort
    Write-Host "  $MasterPort : $newMaster" -ForegroundColor $(if ($newMaster -eq "MASTER") { "Green" } else { "Red" })
    $verifyCount++
    if ($newMaster -eq "MASTER") {
        $verifySuccess++
    }
}

if ($uploadSlave) {
    $newSlave = Identify-Arduino -Port $SlavePort
    Write-Host "  $SlavePort  : $newSlave" -ForegroundColor $(if ($newSlave -eq "SLAVE" -or $newSlave -eq "UNKNOWN") { "Green" } else { "Red" })
    $verifyCount++
    if ($newSlave -eq "SLAVE" -or $newSlave -eq "UNKNOWN") {
        $verifySuccess++
    }
}

Write-Host ""
if ($verifySuccess -eq $verifyCount) {
    Write-Host "[OK] All uploads verified successfully! ($verifySuccess/$verifyCount)" -ForegroundColor Green
}
else {
    Write-Host "[!] Verification incomplete ($verifySuccess/$verifyCount succeeded)" -ForegroundColor Yellow
}
