# Security

This project is a personal, LAN-only telemetry system for a 2008 Mazda MX-5.
It is not hardened for public-internet exposure. This file documents how access
is controlled and how to respond if credentials leak.

## Web remote access token

The Flask/Socket.IO web remote (`pi/ui/src/web_server.py`) is fail-closed:

| State | Behavior |
|-------|----------|
| No token configured | Binds to `127.0.0.1` only (safe default) |
| `MX5_WEB_TOKEN` set | Binds `0.0.0.0` and requires the token on every API/Socket.IO call |

Configuration (all optional):

| Env var | Purpose |
|---------|---------|
| `MX5_WEB_TOKEN` | Secret PIN/token required for network access |
| `MX5_WEB_HOST` | Explicit bind address (overrides auto-selection) |
| `MX5_WEB_SECRET_KEY` | Flask signing key (auto-generated + persisted to `data/web_secret_key` if unset) |
| `MX5_WEB_CORS` | Comma-separated extra allowed origins (default: same-origin only) |

To enable phone access:

1. Create `pi/.web-env` (gitignored):
   ```
   MX5_WEB_TOKEN=choose-a-long-random-value
   ```
2. Uncomment the `EnvironmentFile=/home/pi/MX5-Telemetry/pi/.web-env` line in
   `pi/mx5-display.service`, then `sudo systemctl daemon-reload && sudo systemctl restart mx5-display`.
3. Access the remote at `http://<pi-ip>:5000/?token=<MX5_WEB_TOKEN>` (the token
   is stored in localStorage after first visit).

## SSH access to the Pi

Prefer key-based auth with host-key verification. The `tools/**` scripts use the
shared helper `tools/lib/pi_ssh.py`, which:

- uses `~/.ssh/id_ed25519` (or `PI_SSH_KEY`) key auth first;
- verifies host keys via `paramiko.RejectPolicy`;
- falls back to a password from `PI_PASSWORD` or `tools/lib/pi_config.json`.

Configuration (highest precedence first): env vars `PI_HOST` / `PI_USER` /
`PI_PASSWORD` / `PI_SSH_KEY`, then gitignored `tools/lib/pi_config.json`
(see `tools/lib/pi_config.json.example`), then defaults (`192.168.1.23`, `pi`).

## Secrets handling

- `pi/wpa_supplicant.conf` and `tools/lib/pi_config.json` are gitignored.
- Real secrets are encrypted with `age` and pushed to a private repo via
  `scripts/backup-env.ps1` (see `docs/guides/ENV_BACKUP_GUIDE.md`).
- CI runs TruffleHog on every push/PR and weekly (`.github/workflows/security.yml`),
  plus a hardcoded-credential guard (`scripts/check_hardcoded_secrets.py`) that
  catches Wi-Fi PSKs/passwords TruffleHog's `--only-verified` mode can miss, and
  `ruff` + `pip-audit` (`firmware-build.yml`).

## Incident: 2026-09 credential exposure

An audit found Wi-Fi and device passwords in git history (and one still in the
working tree, since removed). **Treat those credentials as compromised and
rotate them, then purge history.**

### 1. Rotate the credentials

- Change the home Wi-Fi PSK (router).
- Change the phone-hotspot PSK.
- On the Pi: `passwd` (new user password) and generate a new SSH key if one was reused.
- Update local `pi/wpa_supplicant.conf` and re-run `scripts/backup-env.ps1`.

### 2. Purge the passwords from git history

```bash
# One-time install
pip install git-filter-repo

# Create a LOCAL (gitignored) file with the literal secret strings, one per line:
#   <home-wifi-psk>
#   <phone-hotspot-psk>
#   <pi-ssh-password>
# (do NOT commit this file)

git filter-repo --replace-text secrets-patterns.txt --force

# Re-add the remote and force-push the rewritten history
git remote add origin <your-repo-url>
git push origin --force --all
git push origin --force --tags
```

After a force-push, every clone/checkout must be re-cloned (old SHAs no longer
exist), open PRs must be re-created, and any forks retain the old history until
deleted. GitHub may keep the old objects in forks and caches — those need to be
cleaned separately if they contain secrets.
