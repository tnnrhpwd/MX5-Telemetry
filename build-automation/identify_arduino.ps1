# Identify Arduino by probing serial output
param(
    [Parameter(Mandatory=$true)]
    [string]$Port,
    [int]$BaudRate = 115200,
    [int]$TimeoutSeconds = 3
)

Write-Host "Probing $Port at $BaudRate baud..." -ForegroundColor Cyan

try {
    # Open serial port
    $serialPort = New-Object System.IO.Ports.SerialPort
    $serialPort.PortName = $Port
    $serialPort.BaudRate = $BaudRate
    $serialPort.ReadTimeout = $TimeoutSeconds * 1000
    $serialPort.WriteTimeout = 1000
    $serialPort.DtrEnable = $true
    $serialPort.RtsEnable = $true
    
    $serialPort.Open()
    Start-Sleep -Milliseconds 500
    
    # Try to read existing output
    $output = ""
    $startTime = Get-Date
    
    while (((Get-Date) - $startTime).TotalSeconds -lt $TimeoutSeconds) {
        if ($serialPort.BytesToRead -gt 0) {
            $output += $serialPort.ReadExisting()
        }
        Start-Sleep -Milliseconds 100
    }
    
    $serialPort.Close()
    
    if ($output -match "MX5v3") {
        Write-Host "✓ MASTER Arduino detected on $Port" -ForegroundColor Green
        Write-Host "  Output: $($output.Substring(0, [Math]::Min(100, $output.Length)))" -ForegroundColor Gray
        return "MASTER"
    }
    elseif ($output.Length -gt 0) {
        Write-Host "✓ Arduino detected on $Port (possibly SLAVE)" -ForegroundColor Yellow
        Write-Host "  Output: $($output.Substring(0, [Math]::Min(100, $output.Length)))" -ForegroundColor Gray
        return "SLAVE"
    }
    else {
        Write-Host "⚠ No output from $Port (unprogrammed or different baud rate)" -ForegroundColor Yellow
        return "UNKNOWN"
    }
}
catch {
    Write-Host "✗ Error reading $Port : $_" -ForegroundColor Red
    return "ERROR"
}
