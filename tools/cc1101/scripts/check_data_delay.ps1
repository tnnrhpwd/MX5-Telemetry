$ErrorActionPreference = 'Continue'
Start-Sleep -Seconds 12
for ($i = 0; $i -lt 8; $i++) {
    try {
        $d = Invoke-RestMethod -Uri 'http://127.0.0.1:8765/data' -TimeoutSec 3
        $r = $d.latest.rssi
        Write-Output ("mod={0} freq={1} rssi={2} portErr={3}" -f $d.selected_mod, $d.selected_freq, $r, $d.port_error)
    }
    catch {
        Write-Output ("HTTP error: {0}" -f $_.Exception.Message)
    }
    Start-Sleep -Seconds 1
}
