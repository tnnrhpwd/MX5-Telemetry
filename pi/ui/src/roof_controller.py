"""Driver for the MX5things RCNC-2 roof controller (Mazda MX-5 NC PRHT).

The controller exposes a plain-text ASCII console over USB CDC (Microchip
VID 04D8 / PID 000A).  The vendor's configuration program is Windows/macOS
only, but the protocol is simple, so the Pi - and the Pi web remote - can
read and change the settings directly.

Protocol (recovered from the vendor app and the device's own ``help``)::

    =            show current settings
    s <0-30>     speed limit in mph
    a <0|1>      Auto on/off
    m <0|1|2>    mode: 0 = Valet, 1 = One Touch, 2 = OEM
    t            test register
    help         list built-in commands
    reset        reset
    boot         firmware update (deliberately not exposed here)

Send ``"<command>\\n"``; the device echoes the command, prints its reply and
finishes with a ``>`` prompt.  The baud rate is nominal - USB CDC ignores it.

Port policy
-----------

The vendor's guide is explicit that "for normal operation, the USB cable must
be unplugged from the computer", and that a solid red LED means the module is
in its USB state rather than operating the roof.  Any host left on the module
can therefore leave the roof dead until the module is power cycled.

So this driver never holds the port open.  Every command opens the port, does
its one exchange and closes it again, which is what lets the Pi poll the
controller without taking it away from the car.  ``disconnect()`` goes one step
further and stops the Pi touching the module at all, which is the state to
leave the car in when the roof has to be guaranteed to work.

Requires pyserial.  Everything degrades gracefully: if pyserial is missing or
the device is not plugged in, ``status()`` raises ``RoofControllerError`` and
the caller is expected to report "not connected" rather than crash.
"""

import re
import threading
import time

try:
    import serial
    from serial.tools import list_ports
except ImportError:  # pragma: no cover - exercised only without pyserial
    serial = None
    list_ports = None

# MX5things RCNC-2 USB identity.
VID = "04D8"
PID = "000A"

BAUD = 115200  # nominal only; CDC ignores it
PROMPT = b">"

MODE_NAMES = {0: "Valet", 1: "One Touch", 2: "OEM"}
_MODE_FROM_TEXT = {"valet mode": 0, "one touch mode": 1, "oem mode": 2}

SPEED_MIN, SPEED_MAX = 0, 30

RELEASED_MESSAGE = ("roof controller released: the Pi is leaving the module "
                    "alone so the car keeps the roof")


class RoofControllerError(RuntimeError):
    """Raised when the controller is missing or a command fails."""


def _close_quietly(ser):
    """Close one exchange's handle. A failure here is not worth reporting."""
    try:
        ser.close()
    except Exception:
        pass


def find_port():
    """Return the serial port of an attached RCNC-2, or None."""
    if list_ports is None:
        return None
    ports = list(list_ports.comports())
    for p in ports:
        hwid = (p.hwid or "").upper()
        if "VID_%s" % VID in hwid and "PID_%s" % PID in hwid:
            return p.device
    # Fall back to the generic CDC name (Linux often reports it this way).
    for p in ports:
        if "USB Serial Device" in (p.description or ""):
            return p.device
    return None


def parse_status(text):
    """Parse the reply to ``=`` into a dict.

    Example payload::

        =\\r\\nRCNC2 Software Version 44\\r\\nOne touch mode\\r\\n
        Speed Limit(mph): 30, Auto: 1\\r\\n\\r\\n>
    """
    info = {
        "version": None,
        "mode": None,
        "mode_name": None,
        "speed_limit": None,
        "auto": None,
    }
    for line in text.replace("\r", "\n").split("\n"):
        line = line.strip()
        if not line or line == "=":
            continue
        if line.startswith("RCNC2 Software Version"):
            info["version"] = line.rsplit(" ", 1)[-1]
            continue
        low = line.lower()
        if low in _MODE_FROM_TEXT:
            info["mode"] = _MODE_FROM_TEXT[low]
            info["mode_name"] = MODE_NAMES[info["mode"]]
            continue
        m = re.match(r"Speed Limit\(mph\):\s*(\d+)\s*,\s*Auto:\s*(\d+)", line)
        if m:
            info["speed_limit"] = int(m.group(1))
            info["auto"] = int(m.group(2))
    return info


class RoofController:
    """Thread-safe client for the RCNC-2 console.

    The port is opened and closed around each exchange rather than held open,
    so polling for status cannot take the controller away from the car.
    """

    def __init__(self, port=None):
        self._lock = threading.RLock()
        self._port = port
        self._released = False

    # -- connection ------------------------------------------------------

    @property
    def port(self):
        return self._port

    @property
    def released(self):
        """True while the Pi is deliberately leaving the module alone."""
        return self._released

    def _open(self):
        """Open the port for a single exchange; never left open for anyone else."""
        if serial is None:
            raise RoofControllerError("pyserial is not installed")
        if self._released:
            raise RoofControllerError(RELEASED_MESSAGE)
        port = self._port or find_port()
        if not port:
            raise RoofControllerError("roof controller not found")
        self._port = port
        try:
            return serial.Serial(port, BAUD, timeout=0.3)
        except (serial.SerialException, OSError) as e:
            raise RoofControllerError("cannot open %s: %s" % (port, e))

    def connect(self):
        """Claim the module and prove it answers. Returns the parsed status.

        Only the claim flag changes: the confirmation exchange opens and closes
        the port by itself, so connecting does not hold the module.
        """
        with self._lock:
            self._released = False
            return self.status()

    def disconnect(self):
        """Hand the module back to the car so the roof keeps working.

        Nothing holds the port at rest anyway, so this is a promise rather than
        a cleanup: with the module released, every later command refuses without
        touching the hardware at all. This is the state to leave the car in when
        the roof has to be guaranteed to work.
        """
        with self._lock:
            self._released = True

    # ``close`` was the old name for letting go of the module; kept so callers
    # written against it keep working.
    close = disconnect

    # -- protocol --------------------------------------------------------

    def _transact(self, command, settle=0.35, timeout=2.0):
        """Send one console command and return the decoded reply.

        The port is opened for this exchange and closed again before returning,
        on the failure paths as well as the happy one. Holding it open is what
        put the module into its USB state and stopped the roof working, so no
        path out of here keeps a handle.
        """
        with self._lock:
            ser = self._open()
            try:
                try:
                    ser.reset_input_buffer()
                    ser.write(("%s\n" % command).encode("ascii"))
                    ser.flush()
                except (serial.SerialException, OSError) as e:
                    raise RoofControllerError("write failed: %s" % e)

                deadline = time.time() + timeout
                idle_since = time.time()
                buf = bytearray()
                try:
                    while time.time() < deadline:
                        chunk = ser.read(256)
                        if chunk:
                            buf += chunk
                            idle_since = time.time()
                            if bytes(buf).rstrip().endswith(PROMPT):
                                break
                        elif time.time() - idle_since > settle:
                            break
                except (serial.SerialException, OSError) as e:
                    raise RoofControllerError("read failed: %s" % e)
                return buf.decode("ascii", "replace")
            finally:
                _close_quietly(ser)

    # -- public API ------------------------------------------------------

    def status(self):
        """Return the current settings as a dict (raises if not connected)."""
        reply = self._transact("=")
        info = parse_status(reply)
        if info["speed_limit"] is None and info["mode"] is None:
            raise RoofControllerError("unexpected reply: %r" % reply.strip())
        info["port"] = self._port
        info["released"] = self._released
        return info

    def set_speed(self, mph):
        mph = int(mph)
        if not SPEED_MIN <= mph <= SPEED_MAX:
            raise RoofControllerError(
                "speed limit must be %d-%d mph" % (SPEED_MIN, SPEED_MAX))
        return self._transact("s %d" % mph)

    def set_auto(self, value):
        return self._transact("a %d" % (1 if value else 0))

    def set_mode(self, mode):
        mode = int(mode)
        if mode not in MODE_NAMES:
            raise RoofControllerError("mode must be 0 (Valet), 1 (One Touch) or 2 (OEM)")
        return self._transact("m %d" % mode)

    def help_text(self):
        return self._transact("help")
