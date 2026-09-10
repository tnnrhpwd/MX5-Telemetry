#!/usr/bin/env python3
"""Detect hardcoded credentials in git-tracked files.

Complements TruffleHog (which runs with --only-verified and therefore misses
non-verifiable secrets such as Wi-Fi PSKs or Pi passwords). Scans every tracked
text file for obvious credential assignments and exits non-zero if any
non-placeholder value is found.

Usage:
    python scripts/check_hardcoded_secrets.py
"""

import re
import subprocess
import sys

# Values that are placeholders/templates and safe to commit.
ALLOWED = re.compile(
    r"REDACTED|YourHomeWiFi|YourPhone|example|EXAMPLE|<your-|change-me|CHANGE_ME|placeholder|\bxxx\b|XXXXX",
    re.IGNORECASE,
)

SKIP_PATHS = {
    "pi/wpa_supplicant.conf.example",
    "scripts/env-backup/recipients.txt",  # public keys only, but skip anyway
}

PATTERNS = [
    re.compile(r"\b(password|passwd|psk|api_key|apikey|secret|token)\b\s*[:=]\s*[\"'][^\"'|]{2,}[\"']", re.IGNORECASE),
    re.compile(r"\bPI_PASSWORD\s*=\s*[\"'][^\"'|]{2,}[\"']", re.IGNORECASE),
    re.compile(r"\bPI_PASS\s*=\s*[\"'][^\"'|]{2,}[\"']", re.IGNORECASE),
]


def tracked_files():
    out = subprocess.run(
        ["git", "ls-files", "-z"],
        capture_output=True,
        check=True,
    ).stdout
    return [f for f in out.decode("utf-8", "replace").split("\0") if f]


def main():
    issues = []
    for path in tracked_files():
        if path in SKIP_PATHS:
            continue
        try:
            with open(path, encoding="utf-8", errors="ignore") as fh:
                for lineno, line in enumerate(fh, 1):
                    for pattern in PATTERNS:
                        match = pattern.search(line)
                        if match and not ALLOWED.search(match.group(0)):
                            issues.append(f"{path}:{lineno}: {line.rstrip()}")
                            break
        except OSError:
            continue

    if issues:
        print("Hardcoded credentials detected:")
        for item in issues:
            print(f"  {item}")
        return 1

    print("OK: no hardcoded credentials detected")
    return 0


if __name__ == "__main__":
    sys.exit(main())
