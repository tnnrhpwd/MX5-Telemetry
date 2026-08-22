<#
.SYNOPSIS
    Authorizes a new device (SSH public key) to decrypt future env backups.
.DESCRIPTION
    Run this from a machine that already has working, decrypted local secret files (a
    "trusted" machine). It appends the new device's public key to
    scripts/env-backup/recipients.txt, commits that change to the MX5-Telemetry repo,
    re-encrypts the current local secret files for the expanded recipient list, and pushes
    the update to MX5-Telemetry-secrets.

    This is the one-time bootstrap step needed the first time a brand-new SSH keypair
    (e.g. on a new laptop) needs to be able to run `.\scripts\restore-env.ps1`.
.PARAMETER PublicKey
    Path to the new device's SSH public key (.pub file), or the raw key string itself
    (e.g. "ssh-ed25519 AAAA... user@newlaptop").
.EXAMPLE
    .\scripts\add-env-recipient.ps1 -PublicKey "C:\path\to\new-laptop_id_ed25519.pub"
#>

param(
    [Parameter(Mandatory = $true)]
    [string]$PublicKey
)

$ErrorActionPreference = "Stop"

$env:PATH += ";$env:LOCALAPPDATA\Microsoft\WinGet\Links"

$RepoRoot = (& git rev-parse --show-toplevel).Trim()
$RecipientsPath = Join-Path $RepoRoot "scripts\env-backup\recipients.txt"

if (Test-Path $PublicKey) {
    $newKey = (Get-Content $PublicKey -Raw).Trim()
} else {
    $newKey = $PublicKey.Trim()
}

if ($newKey -notmatch '^(ssh-rsa|ssh-ed25519|age1)') {
    throw "Doesn't look like a valid SSH public key or age recipient: $newKey"
}

$existing = Get-Content $RecipientsPath
if ($existing -contains $newKey) {
    Write-Host "This key is already an authorized recipient - nothing to add."
} else {
    Add-Content -Path $RecipientsPath -Value $newKey
    Write-Host "Added new recipient to scripts\env-backup\recipients.txt"

    Push-Location $RepoRoot
    try {
        git add "scripts/env-backup/recipients.txt"
        git commit -m "chore(env-backup): authorize new device for env backups" | Out-Null
        git push
        Write-Host "Pushed recipients.txt update to MX5-Telemetry."
    } finally {
        Pop-Location
    }
}

Write-Host "Re-encrypting backups for the updated recipient list..."
& (Join-Path $RepoRoot "scripts\backup-env.ps1")
