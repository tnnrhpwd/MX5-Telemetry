# Env File Backup Guide

This guide explains how local secrets (`pi/wpa_supplicant.conf`) are backed up and restored
without ever exposing plaintext in the `MX5-Telemetry` repo (or anywhere else).

## Why

`pi/wpa_supplicant.conf` contains real WiFi SSIDs/passwords for connecting the Pi to your
home network and phone hotspot. It's gitignored -- it's never committed. But that means it
also isn't backed up anywhere. If this machine is lost, that config has to be recreated by
hand.

> **History note:** an earlier version of this repo accidentally committed
> `pi/wpa_supplicant.conf` with real passwords in plaintext. Git history has since been
> rewritten to scrub those values, and the file is no longer tracked -- see
> [`pi/wpa_supplicant.conf.example`](../../pi/wpa_supplicant.conf.example) for the template
> that's committed instead.

## How it works

- Secrets are encrypted client-side with [`age`](https://github.com/FiloSottile/age) against
  the SSH public key(s) in [`scripts/env-backup/recipients.txt`](../../scripts/env-backup/recipients.txt)
  (that file only contains **public** keys, so it's safe to commit here).
- The encrypted blobs (`*.age`) are pushed to a separate **private** GitHub repo,
  [`MX5-Telemetry-secrets`](https://github.com/tnnrhpwd/MX5-Telemetry-secrets) -- never to
  `MX5-Telemetry` itself.
- Only whoever holds the matching **private** SSH key can decrypt -- there's no shared
  password to remember, type, or leak. This is the same key that already protects your
  GitHub SSH access.
- [`scripts/env-backup/manifest.json`](../../scripts/env-backup/manifest.json) lists which
  local files map to which encrypted filenames, so new secret files can be added later
  without changing the scripts.

## Everyday use

```powershell
# After changing pi/wpa_supplicant.conf, back it up:
.\scripts\backup-env.ps1

# On any machine, restore pi/wpa_supplicant.conf from the latest backup:
.\scripts\restore-env.ps1
```

`restore-env.ps1` skips files that already exist locally (pass `-Force` to overwrite).

## Setting up a new laptop

1. Install prerequisites you'd need anyway: `git`, `gh` (authenticated with `gh auth login`),
   and `age` (`winget install --id FiloSottile.age -e --scope user`).
2. Clone `MX5-Telemetry` as normal.
3. If you copied your **existing** `~/.ssh` folder over from your old machine, just run:
   ```powershell
   .\scripts\restore-env.ps1
   ```
   and you're done -- that key is already an authorized recipient.
4. If this laptop has a **brand-new** SSH keypair (recommended practice: one key per
   device) that isn't authorized yet, `restore-env.ps1` will fail with a clear message. To
   authorize it:
   - Add the new key to GitHub as usual (`gh ssh-key add ~/.ssh/id_ed25519.pub`) so it can
     also pull the repos.
   - Copy the new machine's `*.pub` file to any machine that still has a working,
     decrypted `pi/wpa_supplicant.conf` (a "trusted" machine).
   - From the trusted machine, run:
     ```powershell
     .\scripts\add-env-recipient.ps1 -PublicKey "C:\path\to\new-laptop_id_ed25519.pub"
     ```
     This appends the key to `recipients.txt`, commits that (public-key-only) change to
     `MX5-Telemetry`, re-encrypts the current secrets for the expanded recipient list, and
     pushes the update to `MX5-Telemetry-secrets`.
   - Back on the new laptop, `git pull` (to get the updated `recipients.txt`) then run
     `.\scripts\restore-env.ps1`.

## Adding a new secret file to the backup

Add an entry to `scripts/env-backup/manifest.json`, e.g.:

```json
{ "source": "pi/some_other_secret.conf", "encrypted": "some_other_secret.conf.age" }
```

Then run `.\scripts\backup-env.ps1` -- it will pick up the new file automatically.
