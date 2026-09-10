"""Centralized, secure SSH connection helper for the MX5-Telemetry Pi.

Replaces the copy-pasted `paramiko.AutoAddPolicy()` + hardcoded password
pattern found across ~80 tool scripts.

Configuration precedence (highest wins):
  1. Environment variables: PI_HOST, PI_USER, PI_PASSWORD, PI_SSH_KEY
  2. tools/lib/pi_config.json (gitignored; see pi_config.json.example)
  3. Built-in defaults (host 192.168.1.23, user "pi")

Key-based auth is preferred. Host keys are verified against ~/.ssh/known_hosts
via paramiko.RejectPolicy, so MITM attacks are refused rather than auto-trusted.

Usage:
    from tools.lib.pi_ssh import connect

    ssh = connect()  # uses config/defaults
    _, stdout, _ = ssh.exec_command("hostname -I")
    print(stdout.read().decode())
    ssh.close()
"""

import json
import os
import sys

import paramiko

_CONFIG_PATH = os.path.join(os.path.dirname(__file__), 'pi_config.json')

DEFAULT_HOST = '192.168.1.23'
DEFAULT_USER = 'pi'


def _config():
    """Load tools/lib/pi_config.json, returning {} on any error."""
    try:
        with open(_CONFIG_PATH, 'r') as f:
            data = json.load(f)
            return data if isinstance(data, dict) else {}
    except (OSError, ValueError):
        return {}


def get_host():
    return os.environ.get('PI_HOST') or _config().get('host') or DEFAULT_HOST


def get_user():
    return os.environ.get('PI_USER') or _config().get('user') or DEFAULT_USER


def get_password():
    return os.environ.get('PI_PASSWORD') or _config().get('password') or None


def get_key_path():
    env = os.environ.get('PI_SSH_KEY')
    if env:
        return env
    cfg = _config().get('key')
    if cfg:
        return os.path.expanduser(cfg)
    return os.path.expanduser('~/.ssh/id_ed25519')


def _load_private_key(path):
    """Try common key types in turn; return None if the file can't be loaded."""
    if not os.path.exists(path):
        return None
    for loader in (
        paramiko.Ed25519Key,
        paramiko.ECDSAKey,
        paramiko.RSAKey,
    ):
        try:
            return loader.from_private_key_file(path)
        except Exception:
            continue
    return None


def connect(host=None, user=None, timeout=10):
    """Return a connected paramiko.SSHClient with host-key verification enabled."""
    host = host or get_host()
    user = user or get_user()

    ssh = paramiko.SSHClient()
    ssh.load_system_host_keys()
    ssh.load_host_keys(os.path.expanduser('~/.ssh/known_hosts'))
    ssh.set_missing_host_key_policy(paramiko.RejectPolicy())

    key = _load_private_key(get_key_path())
    if key is not None:
        ssh.connect(host, username=user, pkey=key, timeout=timeout,
                    look_for_keys=False, allow_agent=True)
        return ssh

    password = get_password()
    if not password:
        raise RuntimeError(
            "No SSH key found and no password configured for %s@%s. "
            "Set PI_PASSWORD or PI_SSH_KEY, or create tools/lib/pi_config.json "
            "(see pi_config.json.example)." % (user, host)
        )
    ssh.connect(host, username=user, password=password, timeout=timeout)
    return ssh
