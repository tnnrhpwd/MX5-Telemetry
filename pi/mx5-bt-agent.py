#!/usr/bin/env python3
"""MX5 Pi Link Bluetooth agent - auto-accept pairing + hold the adapter class.

Two jobs, both of which BlueZ on this Pi will not do for us, sharing one process so
there is only a single thing running.

1. AUTO-ACCEPT PAIRING
   Without a registered org.bluez.Agent1, an incoming pair from the phone dies with
       bluetoothd: No agent available for request type 2
   Request type 2 is RequestConfirmation: Android asks "confirm this code" and nothing
   is registered to answer, so the pair is rejected and the phone just says it cannot
   pair. That is intermittent only because it succeeds on the occasions when a
   bluetoothctl session happens to be open, which registers a temporary agent.

   bluez-tools' bt-agent registers an agent but then blocks on an interactive
       Authorize this device pairing (yes/no)?
   prompt read from stdin. Under systemd stdin is /dev/null, nobody ever answers, and
   the operation fails at the timeout instead - quieter, but just as broken.

   Pairing is not the security boundary here. BtTransport.authenticate() on the Android
   side requires a shared token in the hello message, so auto-accepting a pair grants
   nothing beyond an encrypted link.

2. HOLD THE ADAPTER DEVICE CLASS
   bluetoothd clears the class while it initializes the adapter, and BlueZ 5.50 does not
   persist it: no Class key is ever written to /var/lib/bluetooth/<id>/settings (checked
   - the key is simply absent), and Class in /etc/bluetooth/main.conf is misapplied as
   0x00000100. A class of 0x000000 is not cosmetic: Android filters class-0 devices out
   of its pairing list entirely, so the Pi never appears and the only remaining way to
   pair is from inside the app, which lists only devices the phone is ALREADY bonded to.
   That deadlock is why any one-shot fix is worse than useless - it races bluetoothd and
   loses on some boots.
"""

import logging
import subprocess
import sys
import time

import dbus
import dbus.service
from dbus.mainloop.glib import DBusGMainLoop

AGENT_PATH = "/mx5/pi_link_agent"
ADAPTER_PATH = "/org/bluez/hci0"
WANT_CLASS = 0x120103

DISPLAY_UNIT = "mx5-display.service"
ADV_STALE_TICKS = 9  # 9 x 10s = 90s with no advertiser before acting
ADV_MAX_RESTARTS = 3

# How often to look for the SPP service record, in ticks. `sdptool browse local` costs a
# D-Bus round trip, so it is checked every sixth tick (60s) rather than every tick.
SDP_CHECK_EVERY = 6
SDP_UUID = "00001101-0000-1000-8000-00805F9B34FB"

# The settings in /etc/bluetooth/main.conf that decide whether a reconnect is quick and
# whether a phone can re-pair without being forgotten first. Checked once at startup and
# reported, because there is no runtime property to set any of them from here.
MAIN_CONF = "/etc/bluetooth/main.conf"
ADVISED = (
    ("FastConnectable", "true",
     "reconnects from the phone are slow: BlueZ pages on a 1.28s interval without it"),
    ("AutoEnable", "true",
     "the adapter will not power on after a reboot without `bluetoothctl power on`"),
    ("JustWorksRepairing", "always",
     "a phone that lost its bond must be forgotten and re-paired by hand"),
)

log = logging.getLogger("mx5-bt-agent")


class Agent(dbus.service.Object):
    """Accepts everything: Android uses Just Works, so there is no code to compare."""

    @dbus.service.method("org.bluez.Agent1", in_signature="", out_signature="")
    def Release(self):
        log.info("agent released")

    @dbus.service.method("org.bluez.Agent1", in_signature="os", out_signature="")
    def DisplayPinCode(self, device, pincode):
        log.info("display pin for %s", device)

    @dbus.service.method("org.bluez.Agent1", in_signature="ouq", out_signature="")
    def DisplayPasskey(self, device, passkey, entered):
        log.info("display passkey for %s", device)

    @dbus.service.method("org.bluez.Agent1", in_signature="ou", out_signature="")
    def RequestConfirmation(self, device, passkey):
        log.info("auto-confirming pair request from %s", device)

    @dbus.service.method("org.bluez.Agent1", in_signature="o", out_signature="")
    def RequestAuthorization(self, device):
        log.info("auto-authorizing %s", device)

    @dbus.service.method("org.bluez.Agent1", in_signature="os", out_signature="")
    def AuthorizeService(self, device, uuid):
        log.info("auto-authorizing service %s for %s", uuid, device)

    @dbus.service.method("org.bluez.Agent1", in_signature="o", out_signature="s")
    def RequestPinCode(self, device):
        log.info("pin requested by %s", device)
        return "0000"

    @dbus.service.method("org.bluez.Agent1", in_signature="o", out_signature="u")
    def RequestPasskey(self, device):
        log.info("passkey requested by %s", device)
        return dbus.UInt32(0)

    @dbus.service.method("org.bluez.Agent1", in_signature="", out_signature="")
    def Cancel(self):
        log.info("pairing canceled")


def register_agent(bus):
    """(Re)register as the default agent. Called at start and whenever bluetoothd restarts."""
    try:
        manager = dbus.Interface(
            bus.get_object("org.bluez", "/org/bluez"), "org.bluez.AgentManager1"
        )
    except dbus.exceptions.DBusException as exc:
        log.warning("cannot reach org.bluez yet: %s", exc.get_dbus_name())
        return False

    try:
        manager.RegisterAgent(AGENT_PATH, "NoInputNoOutput")
        log.info("agent registered")
    except dbus.exceptions.DBusException as exc:
        # AlreadyExists just means a previous registration survived; not an error.
        if exc.get_dbus_name() != "org.bluez.Error.AlreadyExists":
            log.warning("RegisterAgent failed: %s", exc.get_dbus_name())

    try:
        manager.RequestDefaultAgent(AGENT_PATH)
    except dbus.exceptions.DBusException as exc:
        log.warning("RequestDefaultAgent failed: %s", exc.get_dbus_name())

    return True


_warned = set()


def _once(key, level, message, *args):
    """Log something at most once per process.

    The periodic checks run every ten seconds for the life of the car. A warning that
    repeats on every tick is worse than useless: it hides the one line that mattered and
    fills the journal, so anything that is a permanent property of the install is said
    once and then left alone.
    """
    if key in _warned:
        return
    _warned.add(key)
    getattr(log, level)(message, *args)


def hold_class(bus):
    """Re-assert the device class whenever bluetoothd has cleared it."""
    try:
        props = dbus.Interface(
            bus.get_object("org.bluez", ADAPTER_PATH),
            "org.freedesktop.DBus.Properties",
        )
        current = int(props.Get("org.bluez.Adapter1", "Class"))
    except dbus.exceptions.DBusException:
        # Adapter or daemon not up yet; the next tick will try again.
        return True

    if current != WANT_CLASS:
        log.info("class was 0x%06x, setting 0x%06x", current, WANT_CLASS)
        # hciconfig comes from bluez-tools, which is not installed on every Pi. A missing
        # tool used to raise out of the timer callback, and PyGObject then drops the
        # timeout: the class would never be set again, and neither the advertisement
        # watchdog nor the SDP republish would ever run again either. That is a watchdog
        # dying silently, which is worse than the fault it was watching for.
        try:
            subprocess.call(
                ["hciconfig", "hci0", "class", "0x%06x" % WANT_CLASS],
                stdout=subprocess.DEVNULL,
                stderr=subprocess.DEVNULL,
            )
        except OSError as e:
            _once("hciconfig", "warning",
                  "cannot set the adapter class: %s. Install bluez-tools (`sudo apt "
                  "install bluez-tools`) so Android lists the Pi when pairing.", e)
    return True


_adv = {"stale": 0, "restarts": 0}
_sdp = {"missing": 0, "republished": 0, "failed": 0, "retry_at": 0.0}
_tick = {"n": 0}


def display_is_active():
    try:
        out = subprocess.check_output(
            ["systemctl", "is-active", DISPLAY_UNIT], stderr=subprocess.DEVNULL
        )
    except (OSError, subprocess.CalledProcessError):
        return False
    return out.strip() == b"active"


def display_env():
    """The environment of the running display app, or {} if it is not running.

    Read from the process rather than from a config file because this is the only place
    that says what the app is *actually* configured to do: MX5_BT may come from an
    EnvironmentFile, a unit override, or a hand-started shell, and a decision to restart
    the service based on the wrong one is worse than no decision.
    """
    try:
        out = subprocess.check_output(
            ["pgrep", "-f", "python.*main.py"], stderr=subprocess.DEVNULL)
    except (OSError, subprocess.CalledProcessError):
        return {}
    pid = out.split()[0].decode() if out.split() else ""
    if not pid:
        return {}
    try:
        with open("/proc/%s/environ" % pid, "rb") as f:
            raw = f.read()
    except OSError:
        return {}
    env = {}
    for item in raw.split(b"\0"):
        if b"=" in item:
            key, _, value = item.partition(b"=")
            env[key.decode("utf-8", "replace")] = value.decode("utf-8", "replace")
    return env


def transport_mode(env):
    """Which Bluetooth transports the display app was told to run."""
    mode = (env.get("MX5_BT") or "both").strip().lower()
    if mode not in ("off", "spp", "ble", "both"):
        mode = "both"
    return mode


def spp_channel(env):
    try:
        return int(env.get("MX5_BT_SPP_CHANNEL") or 3)
    except (TypeError, ValueError):
        return 3


def advise_main_conf():
    """Say what /etc/bluetooth/main.conf is missing, once, at startup.

    None of these can be set at runtime: bluetoothd reads them when it starts, so an
    operator has to change the file. Logging the exact `[General]` keys is the difference
    between "the link is flaky and I do not know why" and a two-line fix.
    """
    try:
        with open(MAIN_CONF, "r", encoding="utf-8", errors="replace") as f:
            text = f.read()
    except OSError as e:
        log.debug("cannot read %s: %s", MAIN_CONF, e)
        return

    settings = {}
    for line in text.splitlines():
        line = line.strip()
        if not line or line.startswith("#") or line.startswith("["):
            continue
        key, _, value = line.partition("=")
        settings[key.strip()] = value.strip()

    for key, wanted, why in ADVISED:
        have = settings.get(key, "")
        if have.lower() != wanted.lower():
            log.warning(
                "%s: %s is %r, so %s. Fix: set `%s = %s` under [General] in %s and "
                "run `sudo systemctl restart bluetooth`.",
                MAIN_CONF, key, have or "unset", why, key, wanted, MAIN_CONF)


def sdp_record_present():
    """Whether bluetoothd's SDP server knows about the SPP record.

    Returns True, False, or None when it cannot be determined (no `sdptool`, or a daemon
    that is not answering yet). The difference matters: a reachable server with no record
    is fixable by republishing, while an unreachable server cannot be republished into at
    all - on such an install SPP never works and BLE is the transport, so retrying every
    minute for ever would only fill the journal.

    The record lives in bluetoothd's memory, so a daemon restart takes it with it and the
    display app never notices: its RFCOMM listener is still bound, but Android's
    createRfcommSocketToServiceRecord() resolves the UUID through SDP first, so every
    connect fails with "service discovery failed" over a link that is otherwise fine.
    That is one of the ways this link used to need an app restart to recover.
    """
    try:
        out = subprocess.run(["sdptool", "browse", "local"],
                             capture_output=True, text=True, timeout=15)
    except (OSError, subprocess.SubprocessError) as e:
        log.debug("sdptool browse local failed: %s", e)
        return None
    combined = (out.stderr or "") + (out.stdout or "")
    if "Failed to connect to SDP server" in combined:
        return None
    return SDP_UUID.lower() in (out.stdout or "").lower()


def ensure_sdp(env):
    """Re-publish the SPP record after anything that would have dropped it."""
    if time.monotonic() < _sdp["retry_at"]:
        return False
    if not env:
        # No display app, so no listener behind the record. Publishing one now would
        # advertise a service that accepts connections and never answers.
        return True
    if transport_mode(env) not in ("spp", "both"):
        return True
    if not display_is_active():
        return True

    present = sdp_record_present()
    if present is True:
        if _sdp["failed"]:
            log.info("SPP record is back; clearing the republish backoff")
        _sdp.update(missing=0, failed=0, retry_at=0.0)
        return True

    if present is None:
        # Nothing can be republished into an SDP server that is not answering. Say it once
        # and then leave it alone: this is a permanent property of the install, and BLE is
        # the transport that works on it.
        _sdp["missing"] = 0
        _sdp["failed"] += 1
        if _sdp["failed"] == 1:
            log.warning(
                "the local SDP server does not answer, so the SPP record cannot be "
                "published or restored. Android cannot reach SPP on this install; BLE "
                "needs no SDP. Check `sdptool browse local`.")
        _sdp["retry_at"] = time.monotonic() + 3600
        return False

    _sdp["missing"] += 1
    if _sdp["missing"] < 2:
        # One miss is worth re-checking on the next round before shouting: `sdptool add`
        # is asynchronous inside bluetoothd.
        return False

    channel = spp_channel(env)
    try:
        result = subprocess.run(["sdptool", "add", "--channel=%d" % channel, "SP"],
                                capture_output=True, text=True, timeout=15)
    except (OSError, subprocess.SubprocessError) as e:
        result = None
        log.debug("sdptool add failed: %s", e)

    if result is None or result.returncode != 0:
        _sdp["failed"] += 1
        delay = min(60 * (2 ** min(_sdp["failed"], 5)), 1800)
        _sdp["retry_at"] = time.monotonic() + delay
        detail = ("could not run" if result is None
                  else "exited %d (%s)" % (result.returncode,
                                           (result.stderr or result.stdout or "").strip()
                                           or "no output"))
        log.warning(
            "sdptool add --channel=%d %s, so Android still cannot find SPP by UUID. "
            "Retrying in %ds; BLE needs no SDP.",
            channel, detail, delay)
        return False

    _sdp.update(missing=0, failed=0, retry_at=0.0)
    _sdp["republished"] += 1
    log.warning("republished the SPP record on channel %d (it had gone missing)",
                channel)
    return True


def watch_advertising(bus, env):
    """Restart the display service if the BLE advertisement has gone missing.

    bt_ble_server registers its advertisement once, when the display service starts.
    BlueZ releases that registration when bluetoothd shuts down, and nothing re-creates
    it - so after any bluetoothd restart the Pi is bonded, discoverable, pairable, and
    has ActiveInstances = 0. There is literally nothing to connect to, yet the phone's
    Bluetooth settings still say "connected" (that is the classic link), and the app
    just reports the Pi as offline. This is exactly what happened after the pairing work
    restarted bluetoothd several times.

    Deliberately conservative: 90s of continuous zero before acting, so a normal start
    (BLE takes up to ~25s to register) cannot trip it, and it gives up after a few
    attempts rather than restarting forever if BLE is switched off in the Pi's config.

    It only applies when the app was actually asked to run BLE. Restarting the display
    service tears down the CAN link, the display and every Bluetooth session, so doing it
    on a Pi configured `MX5_BT=spp` - where ActiveInstances is always 0 and always will be
    - meant a working SPP link was dropped out from under the phone every 90 seconds,
    three times, for no reason at all.
    """
    if transport_mode(env) not in ("ble", "both"):
        _adv["stale"] = 0
        return True
    if not env:
        # The app is not running, so there is nothing to restart and nothing advertising.
        _adv["stale"] = 0
        return True

    try:
        props = dbus.Interface(
            bus.get_object("org.bluez", ADAPTER_PATH),
            "org.freedesktop.DBus.Properties",
        )
        active = int(props.Get("org.bluez.LEAdvertisingManager1", "ActiveInstances"))
    except dbus.exceptions.DBusException:
        return True

    if active > 0:
        _adv["stale"] = 0
        return True

    if not display_is_active():
        return True

    _adv["stale"] += 1
    if _adv["stale"] < ADV_STALE_TICKS:
        return True

    _adv["stale"] = 0
    if _adv["restarts"] >= ADV_MAX_RESTARTS:
        if _adv["restarts"] == ADV_MAX_RESTARTS:
            _adv["restarts"] += 1
            log.error(
                "BLE advertisement still missing after %d restarts of %s; giving up",
                ADV_MAX_RESTARTS,
                DISPLAY_UNIT,
            )
        return True

    _adv["restarts"] += 1
    log.warning(
        "no BLE advertisement for %ds, restarting %s (%d/%d)",
        ADV_STALE_TICKS * 10,
        DISPLAY_UNIT,
        _adv["restarts"],
        ADV_MAX_RESTARTS,
    )
    # Popen, not call: blocking here would stall the GLib loop that has to answer
    # bluetoothd's Release() while it shuts down.
    subprocess.Popen(
        ["systemctl", "restart", DISPLAY_UNIT],
        stdout=subprocess.DEVNULL,
        stderr=subprocess.DEVNULL,
    )
    return True


def main():
    logging.basicConfig(
        level=logging.INFO,
        format="%(levelname)s %(message)s",
        stream=sys.stderr,
    )

    DBusGMainLoop(set_as_default=True)
    bus = dbus.SystemBus()

    # Hold one reference to the exported object for the life of the process.
    agent = Agent(bus, AGENT_PATH)  # noqa: F841

    register_agent(bus)
    hold_class(bus)

    def on_name_owner_changed(name, old_owner, new_owner):
        # bluetoothd restarting drops our registration with it, so re-register rather
        # than trusting a one-shot start.
        if name == "org.bluez" and new_owner:
            log.info("org.bluez reappeared, re-registering")
            register_agent(bus)
            hold_class(bus)

    bus.add_signal_receiver(
        on_name_owner_changed,
        signal_name="NameOwnerChanged",
        dbus_interface="org.freedesktop.DBus",
        bus_name="org.freedesktop.DBus",
        path="/org/freedesktop/DBus",
        arg0="org.bluez",
    )

    advise_main_conf()

    # bluetoothctl/BlueZ will not tell us when the class is cleared, so poll. One
    # property read every ten seconds is a rounding error even on a Pi.
    from gi.repository import GLib

    def tick():
        _tick["n"] += 1
        # Each step is isolated. Nothing here is allowed to raise out of the callback: a
        # single unhandled exception removes this timeout for the rest of the process,
        # which silently disables the advertisement watchdog and the SDP republish as
        # well as whatever failed.
        try:
            hold_class(bus)
        except Exception:
            log.exception("adapter class check failed; the rest of the tick continues")

        try:
            env = display_env()
        except Exception:
            log.exception("could not read the display app's environment")
            env = {}

        try:
            watch_advertising(bus, env)
        except Exception:
            log.exception("advertisement watchdog failed; the rest of the tick continues")

        if _tick["n"] % SDP_CHECK_EVERY == 0:
            try:
                ensure_sdp(env)
            except Exception:
                log.exception("SDP watchdog failed; the rest of the tick continues")

        return True

    GLib.timeout_add_seconds(10, tick)

    log.info("mx5-bt-agent running")
    GLib.MainLoop().run()


if __name__ == "__main__":
    main()
