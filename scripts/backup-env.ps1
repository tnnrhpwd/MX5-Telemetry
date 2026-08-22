<#
.SYNOPSIS
    Encrypts local secret files and pushes them to the private MX5-Telemetry-secrets backup repo.
.DESCRIPTION
    Uses `age` to encrypt each file listed in scripts/env-backup/manifest.json against every
    SSH/age public key in scripts/env-backup/recipients.txt, then commits and pushes the
    encrypted blobs to the private tnnrhpwd/MX5-Telemetry-secrets GitHub repo.

    Plaintext secrets (e.g. pi/wpa_supplicant.conf with real WiFi passwords) never leave this
    machine and never touch the MX5-Telemetry repo - only ciphertext (readable solely by
    holders of an authorized SSH private key) is stored remotely.
.EXAMPLE
    .\scripts\backup-env.ps1
#>

$ErrorActionPreference = "Stop"

# `age` is installed per-user via winget; make sure it's on PATH even in a brand-new shell.
$env:PATH += ";$env:LOCALAPPDATA\Microsoft\WinGet\Links"
if (-not (Get-Command age -ErrorAction SilentlyContinue)) {
    throw "age is not installed. Install it with: winget install --id FiloSottile.age -e --scope user"
}

$RepoRoot = (& git rev-parse --show-toplevel).Trim()
$EnvBackupDir = Join-Path $RepoRoot "scripts\env-backup"
$ManifestPath = Join-Path $EnvBackupDir "manifest.json"
$RecipientsPath = Join-Path $EnvBackupDir "recipients.txt"
$SecretsRepoUrl = "https://github.com/tnnrhpwd/MX5-Telemetry-secrets.git"
$SecretsRepoDir = Join-Path $env:USERPROFILE ".mx5-telemetry-secrets"

if (-not (Test-Path $ManifestPath)) { throw "Manifest not found: $ManifestPath" }
if (-not (Test-Path $RecipientsPath)) { throw "Recipients file not found: $RecipientsPath" }

$manifest = (Get-Content $ManifestPath -Raw | ConvertFrom-Json).files

if (-not (Test-Path (Join-Path $SecretsRepoDir ".git"))) {
    Write-Host "Cloning $SecretsRepoUrl into $SecretsRepoDir ..."
    git clone $SecretsRepoUrl $SecretsRepoDir
} else {
    Write-Host "Updating local secrets repo clone..."
    git -C $SecretsRepoDir pull --ff-only
}

$backedUp = 0
foreach ($entry in $manifest) {
    $sourcePath = Join-Path $RepoRoot $entry.source
    if (-not (Test-Path $sourcePath)) {
        Write-Warning "Skipping missing file: $($entry.source)"
        continue
    }
    $destPath = Join-Path $SecretsRepoDir $entry.encrypted
    Write-Host "Encrypting $($entry.source) -> $($entry.encrypted)"
    age -R $RecipientsPath -o $destPath $sourcePath
    $backedUp++
}

if ($backedUp -eq 0) {
    Write-Host "Nothing to back up (no source files found on this machine)."
    exit 0
}

Push-Location $SecretsRepoDir
try {
    git add -A
    $status = git status --porcelain
    if ([string]::IsNullOrWhiteSpace($status)) {
        Write-Host "No changes since last backup - secrets repo already up to date."
    } else {
        $timestamp = Get-Date -Format "yyyy-MM-dd HH:mm:ss"
        git commit -m "Backup env files ($timestamp)" | Out-Null
        git push
        Write-Host "Backup pushed to $SecretsRepoUrl"
    }
} finally {
    Pop-Location
}
