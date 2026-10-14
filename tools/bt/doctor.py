#!/usr/bin/env python3
"""One-shot health check for the Bluetooth link.

Stages 0-4 of docs/BLUETOOTH_LINK.md are five separate SSH commands, and each one is a place
to misread a result. This runs them all in one pass and reports each as PASS / WARN / FAIL
next to the command it ran, so a failure is attributable instead of re-derived.

The check that earns its place is the token. Under systemd the display app only receives
MX5_WEB_TOKEN if its unit loads an EnvironmentFile, and nothing about a running app makes a
missing one visible: without it the web remote silently drops to localhost-only and the
Bluetooth link refuses to start. So this reads the token out of the running process's own
environment, not out of a config file that may not be the one in use.

Usage:
    python tools/bt/doctor.py                       # the configured Pi
    python tools/bt/doctor.py --host 10.62.26.67    # the hotspot address
"""

import argparse
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))

try:
    from tools.lib.pi_ssh import connect as pi_connect  # noqa: E402
except ImportError as e:
    # A traceback here would be indistinguishable from the doctor having found a fault, and
    # the whole point of this script is to remove that kind of ambiguity.
    print("Cannot import the SSH helper: %s" % e)
    print("This needs paramiko. Install the repo's requirements first:")
    print("    pip install -r requirements.txt")
    raise SystemExit(2)

# The remote output this prints carries the glyphs the display app uses for its link
# banner. A Windows console defaults to cp1252, which cannot encode them, so the doctor
# crashed while reporting a finding - losing exactly the message it exists to deliver.
if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")

PASS, WARN, FAIL = "PASS", "WARN", "FAIL"
TAG = {PASS: "PASS", WARN: "WARN", FAIL: "FAIL"}

# The app's words for the link *as a whole*, kept separate from the per-transport lines.
# "SPP link not started" appears even when the link came up happily on BLE, so matching
# every failure phrase reported a working link as broken.
LINK_FAILED = ("bluetooth link did not start", "bluetooth link unavailable")
LINK_STARTED = "bluetooth link started"
TRANSPORT_FAILED = "link not started"

# The app's own environment, which is the only place the answer is authoritative. Matches the
# service's ExecStart pattern, so a hand-started app is read the same way as a service one.
ENV_CMD = (
    "PID=$(pgrep -f 'python.*main.py' | head -1); "
    "if [ -z \"$PID\" ]; then echo __NOPID__; else "
    "tr '\\0' '\\n' < /proc/$PID/environ "
    "| grep -E '^MX5_(WEB_TOKEN|BT_TOKEN|BT|BT_ALLOW_NO_TOKEN|BT_SPP_CHANNEL|BT_NAME)=' "
    "|| echo __NOTOKEN__; fi"
)

PAIRED_CMD = (
    "for m in $(bluetoothctl devices 2>/dev/null | awk '{print $2}'); do "
    "p=$(bluetoothctl info \"$m\" 2>/dev/null); "
    "printf '%s|%s|%s\\n' \"$m\" \"$(echo \"$p\" | sed -n 's/.*Paired: //p')\" "
    "\"$(echo \"$p\" | sed -n 's/.*Name: //p')\"; done"
)

SDP_CMD = "sdptool browse local 2>/dev/null | grep -i -A8 'Serial Port'"


def run(ssh, cmd, timeout=25):
    """Run one command and return (exit_status, combined_output)."""
    _, out, err = ssh.exec_command(cmd, timeout=timeout)
    text = out.read().decode("utf-8", "replace")
    code = out.channel.recv_exit_status()
    noise = err.read().decode("utf-8", "replace").strip()
    return code, (text.strip() or noise)


def main():
    parser = argparse.ArgumentParser(description="Bluetooth link doctor")
    parser.add_argument("--host", default=os.environ.get("PI_HOST", "192.168.1.23"))
    parser.add_argument("--user", default=os.environ.get("PI_USER", "pi"))
    parser.add_argument("--channel", type=int, default=3, help="expected SPP channel")
    args = parser.parse_args()

    print("MX5 Bluetooth link doctor  (%s@%s)" % (args.user, args.host))
    print("=" * 70)

    try:
        ssh = pi_connect(host=args.host, user=args.user, timeout=10)
    except Exception as e:
        print("[%s] Pi reachable over SSH" % FAIL)
        print("       %s" % e)
        print("\nNothing else can be checked. Everything downstream of this is unknown, "
              "not broken.")
        return 1

    results = []

    def record(status, name, detail="", hint=""):
        results.append(status)
        print("[%s] %s" % (TAG[status], name))
        if detail:
            for line in str(detail).splitlines():
                print("       " + line)
        if hint:
            print("       -> " + hint)

    try:
        # -- 1. the app itself -------------------------------------------------
        code, out = run(ssh, "systemctl is-active mx5-display")
        if out.strip() == "active":
            _, pid = run(ssh, "pgrep -f 'python.*main.py' | head -1")
            record(PASS, "Display app is running", "mx5-display active, pid %s" % (pid or "?"))
        else:
            record(FAIL, "Display app is running", "mx5-display is %r" % out.strip(),
                   "nothing else can work until this starts; see Stage 0")

        # -- 2. the token, read from the running process -----------------------
        code, out = run(ssh, ENV_CMD)
        if "__NOPID__" in out:
            record(WARN, "Token reaches the display app",
                   "no main.py process, so this cannot be answered",
                   "start the app first, then re-run")
            env = {}
        elif "__NOTOKEN__" in out:
            record(FAIL, "Token reaches the display app",
                   "the process environment has no MX5_* variables at all",
                   "the unit's EnvironmentFile is commented out. See setup step 3")
            env = {}
        else:
            env = dict(line.split("=", 1) for line in out.splitlines() if "=" in line)
            have = "MX5_BT_TOKEN" if "MX5_BT_TOKEN" in env else "MX5_WEB_TOKEN"
            if "MX5_BT_ALLOW_NO_TOKEN" in env and env["MX5_BT_ALLOW_NO_TOKEN"] not in ("", "0"):
                record(WARN, "Token reaches the display app",
                       "%s is set (%d chars), but MX5_BT_ALLOW_NO_TOKEN is on"
                       % (have, len(env.get(have, ""))),
                       "the link accepts commands with no token. Fine on a bench, not in a car")
            else:
                record(PASS, "Token reaches the display app",
                       "%s present, %d chars (value not printed)"
                       % (have, len(env.get(have, ""))))
            for key in ("MX5_BT", "MX5_BT_SPP_CHANNEL", "MX5_BT_NAME"):
                if key in env:
                    print("       %s=%s" % (key, env[key]))

        # -- 3. the radio ------------------------------------------------------
        _, out = run(ssh, "systemctl is-active bluetooth")
        record(PASS if out.strip() == "active" else FAIL,
               "bluetooth.service is active", out.strip() or "(no output)",
               "" if out.strip() == "active" else "sudo systemctl enable --now bluetooth")

        _, out = run(ssh, "hciconfig -a 2>/dev/null | grep -E 'BD Address|UP RUNNING'")
        if "BD Address" in out:
            record(PASS, "Adapter has a BD Address", out)
        else:
            record(FAIL, "Adapter has a BD Address", out or "(hciconfig printed nothing)",
                   "the adapter is down or the kernel has no driver; nothing below can work")

        # -- 4. SPP, whose fragile part is the SDP record ----------------------
        _, out = run(ssh, "command -v sdptool || echo MISSING")
        if "MISSING" in out:
            record(WARN, "sdptool installed", "not found",
                   "bluez-tools is missing, so SPP cannot publish. BLE still works.")
        else:
            record(PASS, "sdptool installed", out)

            # sdptool can only publish if the daemon's own SDP server answers. When it does
            # not, no channel or MAC change can help, so surface that cause once here
            # instead of letting the record check below imply a fixable fault.
            _, srv = run(ssh, "sdptool browse local 2>&1 | head -2")
            if "Failed to connect to SDP server" in srv or "No such file" in srv:
                record(FAIL, "Local SDP server reachable", srv.strip(),
                       "nothing can publish an SDP record without it, so SPP cannot work "
                       "on this install at all. Use BLE (MX5_BT=ble); a different channel "
                       "or address will not fix this.")
                sdp_server_ok = False
            else:
                record(PASS, "Local SDP server reachable")
                sdp_server_ok = True

            _, sdp = run(ssh, SDP_CMD)
            if "Channel: %d" % args.channel in sdp:
                channel = [l.strip() for l in sdp.splitlines() if "Channel:" in l]
                record(PASS, "SDP Serial Port record on channel %d" % args.channel,
                       channel[0] if channel else "")
            else:
                # Only suggest sdptool when the server it talks to is actually up;
                # otherwise the advice cannot work and wastes a trip.
                hint = ("Android will not connect over SPP without it. "
                        "Try: sudo sdptool add --channel=%d SP" % args.channel
                        if sdp_server_ok else
                        "Android will not connect over SPP without it, and the SDP server "
                        "it would be published to is unreachable (see above), so no "
                        "command here can fix it. Use BLE (MX5_BT=ble).")
                record(FAIL, "SDP Serial Port record on channel %d" % args.channel,
                       sdp or "(no Serial Port record found)", hint)

        # -- 5. BLE ------------------------------------------------------------
        _, out = run(ssh, "python3 -c 'import bless; print(\"ok\")' 2>&1 | tail -1")
        record(PASS if out.strip() == "ok" else WARN, "bless importable (BLE)",
               out if out.strip() != "ok" else "ok",
               "" if out.strip() == "ok" else "pip install bless (plus python3-dbus python3-gi)")

        # -- 6. the phone ------------------------------------------------------
        _, out = run(ssh, PAIRED_CMD)
        if not out.strip():
            record(WARN, "A phone is paired", "no paired devices",
                   "pair from the phone's Bluetooth settings; see Stage 4")
        else:
            rows = [line.split("|") for line in out.splitlines()]
            for row in rows:
                mac, state, name = (row + ["", ""])[:3]
                print("       %s  paired=%s  %s" % (mac, state or "?", name))
            paired = [r for r in rows if len(r) > 1 and r[1].strip().lower() == "yes"]
            record(PASS if paired else WARN, "A phone is paired",
                   "%d device(s) known" % len(rows),
                   "" if paired else "known but none marked Paired: yes")

        # -- 7. what the link said when it started ----------------------------
        # Filter by PID rather than by recency: a CAN transmit fault can print twenty
        # lines a second, which pushed the startup banner out of any fixed window and made
        # this check report "no link lines" against a link that had started fine.
        _, out = run(ssh, "PID=$(pgrep -f 'python.*main.py' | head -1); "
                          "if [ -z \"$PID\" ]; then echo __NOPID__; else "
                          "journalctl _PID=$PID --no-pager 2>/dev/null "
                          "| grep -iE 'bluetooth link|SPP link|BLE link|SPP peer' "
                          "| tail -12; fi")
        if "__NOPID__" in out:
            record(WARN, "The link reported itself started",
                   "no main.py process, so this cannot be answered",
                   "start the app first, then re-run")
        elif out.strip():
            lines = out.splitlines()
            failed = [l for l in lines if any(m in l.lower() for m in LINK_FAILED)]
            started = [l for l in lines if LINK_STARTED in l.lower()]
            degraded = [l for l in lines if TRANSPORT_FAILED in l.lower()]
            if failed:
                record(FAIL, "The link reported itself started", out,
                       "the app printed why it refused; fix that reason, not this check")
            elif started and degraded:
                # Working, but on a fallback transport. Worth a warning: failover now
                # depends entirely on whichever transport survived.
                record(WARN, "The link reported itself started", out,
                       "the link is up, but %d transport(s) did not start: fix those to "
                       "get the preferred path back" % len(degraded))
            elif started:
                record(PASS, "The link reported itself started", out)
            else:
                record(WARN, "The link reported itself started", out,
                       "the app started but said nothing about the link")
        else:
            record(WARN, "The link reported itself started",
                   "the running app printed nothing about a link",
                   "the running code may predate the Bluetooth link; git pull and restart")
    finally:
        ssh.close()

    print("=" * 70)
    fails = results.count(FAIL)
    warns = results.count(WARN)
    print("%d checks: %d pass, %d warn, %d fail"
          % (len(results), results.count(PASS), warns, fails))
    if fails:
        print("\nFix the FAILs in order, top down. The stages are ordered because each one "
              "assumes the one above it.")
    elif warns:
        print("\nNo blocking faults. The warnings are the things most likely to bite during "
              "the full test.")
    else:
        print("\nClean. Stage 0 is done; start the full test at Stage 4.")
    return 1 if fails else 0


if __name__ == "__main__":
    sys.exit(main())
