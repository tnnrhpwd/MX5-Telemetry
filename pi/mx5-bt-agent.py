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
   bluetoothd clears the class while it initialises the adapter, and BlueZ 5.50 does not
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

import dbus
import dbus.service
from dbus.mainloop.glib import DBusGMainLoop

AGENT_PATH = "/mx5/pi_link_agent"
ADAPTER_PATH = "/org/bluez/hci0"
WANT_CLASS = 0x120103

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
        log.info("auto-authorising %s", device)

    @dbus.service.method("org.bluez.Agent1", in_signature="os", out_signature="")
    def AuthorizeService(self, device, uuid):
        log.info("auto-authorising service %s for %s", uuid, device)

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
        log.info("pairing cancelled")


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
        subprocess.call(
            ["hciconfig", "hci0", "class", "0x%06x" % WANT_CLASS],
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

    # bluetoothctl/BlueZ will not tell us when the class is cleared, so poll. One
    # property read every ten seconds is a rounding error even on a Pi.
    from gi.repository import GLib

    GLib.timeout_add_seconds(10, lambda: hold_class(bus))

    log.info("mx5-bt-agent running")
    GLib.MainLoop().run()


if __name__ == "__main__":
    main()
