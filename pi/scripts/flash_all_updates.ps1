# Compatibility shim - the real deployment logic lives in scripts/push-hardware.ps1.
#
# Kept so old notes, shortcuts and muscle memory that call
# pi\scripts\flash_all_updates.ps1 keep working. Every flag is forwarded, e.g.
#
#   .\pi\scripts\flash_all_updates.ps1 -DryRun
#   .\pi\scripts\flash_all_updates.ps1 -Targets esp32,pi -Force
[CmdletBinding()]
param(
    [Parameter(ValueFromRemainingArguments = $true)]
    [string[]]$Rest
)

$target = Join-Path (Split-Path -Parent (Split-Path -Parent $PSScriptRoot)) 'scripts\push-hardware.ps1'

if (-not (Test-Path $target)) {
    Write-Host "ERROR: $target not found." -ForegroundColor Red
    exit 1
}

# Re-invoke in a child PowerShell so the forwarded flags are parsed as
# parameters again (array splatting into a script would bind them positionally).
$powershellExe = (Get-Process -Id $PID).Path
& $powershellExe -NoProfile -ExecutionPolicy Bypass -File $target @Rest
exit $LASTEXITCODE
