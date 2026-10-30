#!/usr/bin/env python3
"""Check that the simulator's settings are the strip's settings - and so is everyone's.

`parity_check.py` proves the *logic* matches by compiling the firmware. This proves the
*numbers* do: the defaults the simulator starts from, the ranges its sliders allow, and the
values the Pi and the phone send.

All of it is parsed out of the real sources rather than restated here, so the check fails
when any of the four places that hold a copy of a number drift apart:

    arduino/src/main.cpp                    the strip itself
    pi/ui/src/main.py                       the Pi's stored settings
    pi/ui/src/link_service.py               what the Pi will accept
    android/.../LedScreen.java, MainActivity.java   what the phone sends

    python test_settings_parity.py
"""

import os
import re
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
REPO = os.path.abspath(os.path.join(HERE, "..", "..", ".."))
sys.path.insert(0, HERE)

import led_engine as engine  # noqa: E402

FIRMWARE = os.path.join(REPO, "arduino", "src", "main.cpp")
PI_MAIN = os.path.join(REPO, "pi", "ui", "src", "main.py")
PI_LINK = os.path.join(REPO, "pi", "ui", "src", "link_service.py")
APP_LED = os.path.join(REPO, "android", "mx5-remote", "src", "main", "java",
                       "com", "mx5", "remote", "LedScreen.java")
APP_MAIN = os.path.join(REPO, "android", "mx5-remote", "src", "main", "java",
                        "com", "mx5", "remote", "MainActivity.java")
APP_PALETTE = os.path.join(REPO, "android", "mx5-remote", "src", "main", "java",
                           "com", "mx5", "remote", "Palette.java")
SIMULATOR = os.path.join(HERE, "led_simulator_v3.py")


def read(path):
    with open(path, encoding="utf-8") as handle:
        return handle.read()


def grab(pattern, text, what, flags=re.M):
    match = re.search(pattern, text, flags)
    if not match:
        raise SystemExit("could not find %s (pattern %r)" % (what, pattern))
    return match


# -- firmware -----------------------------------------------------------------

FW = read(FIRMWARE)

FW_LED_COUNT = int(grab(r"^#define\s+LED_COUNT\s+(\d+)", FW, "LED_COUNT").group(1))
FW_RAMP_STOP_COUNT = int(grab(r"^#define\s+RAMP_STOP_COUNT\s+(\d+)", FW,
                              "RAMP_STOP_COUNT").group(1))
FW_SELF_TEST_MS = int(grab(r"^#define\s+SELF_TEST_MS\s+(\d+)", FW, "SELF_TEST_MS").group(1))
FW_IDENTIFY_MS = int(grab(r"^#define\s+IDENTIFY_MS\s+(\d+)", FW, "IDENTIFY_MS").group(1))
FW_SNAP_DELTA = int(grab(r"^#define\s+RPM_SNAP_DELTA\s+(\d+)", FW, "RPM_SNAP_DELTA").group(1))
FW_ALPHA_RISING = float(grab(r"^#define\s+RPM_ALPHA_RISING\s+([\d.]+)f", FW,
                             "RPM_ALPHA_RISING").group(1))
FW_ALPHA_FALLING = float(grab(r"^#define\s+RPM_ALPHA_FALLING\s+([\d.]+)f", FW,
                              "RPM_ALPHA_FALLING").group(1))

_ramp_block = grab(r"RampStop rampStops\[RAMP_STOP_COUNT\]\s*=\s*\{(.*?)\n\};", FW,
                   "the default ramp", re.S).group(1)
FW_RAMP = tuple(
    (int(rpm), (int(r), int(g), int(b)))
    for rpm, r, g, b in re.findall(
        r"\{\s*(\d+),\s*(\d+),\s*(\d+),\s*(\d+)\s*\}", _ramp_block))

FW_FULL_RPM = int(grab(r"\buint16_t\s+rpmFull\s*=\s*(\d+)", FW, "rpmFull").group(1))
FW_THEME_DIM = int(grab(r"\buint8_t\s+themeDim\s*=\s*(\d+)", FW, "themeDim").group(1))
FW_ENABLED = grab(r"\bbool\s+stripEnabled\s*=\s*(true|false)", FW,
                  "stripEnabled").group(1) == "true"
FW_COLOR_MODE = int(grab(r"\buint8_t\s+colorMode\s*=\s*(\d+)", FW, "colorMode").group(1))
FW_SHIFT_RPM = int(grab(r"\buint16_t\s+shiftRpm\s*=\s*(\d+)", FW, "shiftRpm").group(1))
FW_SHIFT_HZ = int(grab(r"\buint8_t\s+shiftHz\s*=\s*(\d+)", FW, "shiftHz").group(1))
_shift_rgb = grab(r"\buint8_t\s+shiftR\s*=\s*(\d+),\s*shiftG\s*=\s*(\d+),\s*shiftB\s*=\s*(\d+)",
                  FW, "the shift color")
FW_SHIFT_RGB = tuple(int(v) for v in _shift_rgb.groups())
FW_BRIGHTNESS = int(grab(r"\buint8_t\s+currentBrightness\s*=\s*(\d+)", FW,
                         "currentBrightness").group(1))
FW_SEQUENCE_IS_CENTER_OUT = bool(re.search(r"\buint8_t\s+ledSequence\s*=\s*SEQ_CENTER_OUT",
                                           FW))
FW_DIM_SCALE = int(grab(r"#define\s+DIM_SCALE\s+(\d+)", FW, "DIM_SCALE").group(1))
FW_FULL_SCALE = int(grab(r"themeDim \? DIM_SCALE : (\d+)", FW, "the full scale").group(1))

# The CFG: parser's clamps - what the strip will actually accept.
_cfg_start = FW.index('else if (strncmp(cmdBuffer, "CFG:", 4) == 0)')
_cfg_end = FW.index('else if (strcmp(cmdBuffer, "CFG?")', _cfg_start)
_cfg = FW[_cfg_start:_cfg_end]
FW_FULL_MIN, FW_FULL_MAX = (int(v) for v in
                            re.search(r"\"full=\"[^}]*?if \(v < (\d+)\) v = \d+;[^}]*?"
                                      r"if \(v > (\d+)\)", _cfg, re.S).groups())
FW_HZ_MIN, FW_HZ_MAX = (int(v) for v in
                        re.search(r"\"hz=\"[^}]*?if \(v < (\d+)\) v = \d+;[^}]*?"
                                  r"if \(v > (\d+)\)", _cfg, re.S).groups())
FW_SHIFT_MIN, FW_SHIFT_MAX = (int(v) for v in
                              re.search(r"\"shift=\"[^}]*?if \(v != 0 && v < (\d+)\) v = \d+;"
                                        r"[^}]*?if \(v > (\d+)\)", _cfg, re.S).groups())

# -- the Pi -------------------------------------------------------------------

PI = read(PI_MAIN)


def pi_default(name):
    """One field of the Pi's Settings dataclass, resolving a symbolic default."""
    match = re.search(r"^\s+%s:\s*int\s*=\s*(-?\d+)" % name, PI, re.M)
    if match:
        return int(match.group(1))
    match = re.search(r"^\s+%s:\s*str\s*=\s*\"([^\"]*)\"" % name, PI, re.M)
    if match:
        return match.group(1)
    # `led_sequence: int = LED_SEQ_CENTER_OUT` - follow the constant to its value.
    match = re.search(r"^\s+%s:\s*int\s*=\s*([A-Z_][A-Z0-9_]*)" % name, PI, re.M)
    if match:
        symbol = re.search(r"^%s\s*=\s*(\d+)" % match.group(1), PI, re.M)
        if symbol:
            return int(symbol.group(1))
    raise SystemExit("could not find Pi default for %s" % name)


PI_DEFAULTS = {
    "led_enabled": int(pi_default("led_enabled")),
    "led_color_mode": int(pi_default("led_color_mode")),
    "led_sequence": int(pi_default("led_sequence")),
    "led_shift_rpm": int(pi_default("led_shift_rpm")),
    "led_shift_hz": int(pi_default("led_shift_hz")),
    "led_shift_color": pi_default("led_shift_color"),
    "led_brightness": int(pi_default("led_brightness")),
}

LINK = read(PI_LINK)
LINK_SHIFT = re.search(r"if rpm != 0 and not (\d+) <= rpm <= (\d+)", LINK)
LINK_HZ = re.search(r"if not (\d+) <= hz <= (\d+)", LINK)
LINK_COLOR_MODE = re.search(r"if mode not in \((\d+), (\d+)\)", LINK)
LINK_SEQUENCE = re.search(r"if not (\d+) <= seq <= (\d+)", LINK)
if not (LINK_SHIFT and LINK_HZ and LINK_COLOR_MODE and LINK_SEQUENCE):
    raise SystemExit("could not find the Pi's validation ranges in link_service.py")

# -- the phone ----------------------------------------------------------------

LED = read(APP_LED)
APP_FRACTIONS = tuple(float(v) for v in
                      grab(r"STOP_FRACTIONS = \{([^}]*)\}", LED,
                           "STOP_FRACTIONS").group(1).replace("f", "").split(","))
APP_FULL_RPM = int(grab(r"DEFAULT_FULL_RPM = (\d+)", LED, "DEFAULT_FULL_RPM").group(1))
APP_SEQ_VALUES = tuple(int(v) for v in
                       grab(r"SEQ_VALUES = \{([^}]*)\}", LED, "SEQ_VALUES").group(1).split(","))
APP_MODE_VALUES = tuple(int(v) for v in
                        grab(r"MODE_VALUES = \{([^}]*)\}", LED, "MODE_VALUES").group(1).split(","))
APP_RAMP_STOPS = len(re.findall(r'"[0-9a-fA-F]{6}"',
                                grab(r"DEFAULT_COLOURS =\s*\{([^}]*)\}", LED,
                                     "DEFAULT_COLOURS").group(1)))


def java_slider(label):
    """(min, max, step, initial, symbol) from a SliderRow in LedScreen.java.

    `initial` is None when the call passes a named constant; `symbol` then names it, and a
    separate check pins that constant to the firmware.
    """
    match = re.search(r'"%s",\s*(\d+),\s*(\d+),\s*(\d+),\s*(\d+|[A-Z_][A-Z0-9_]*)'
                      % re.escape(label), LED)
    if not match:
        raise SystemExit("could not find the %r slider in LedScreen.java" % label)
    low, high, step, initial = match.groups()
    if initial.isdigit():
        return int(low), int(high), int(step), int(initial), None
    return int(low), int(high), int(step), None, initial


APP_BRIGHTNESS = java_slider("Brightness")
APP_FULL_AT = java_slider("Full at")
APP_SHIFT = java_slider("Start at")
APP_HZ = java_slider("Flash rate")

APP_THEME_RPMS = tuple(int(v.strip()) for v in
                       grab(r"RAMP_RPMS\s*=\s*\{([^}]*)\}", read(APP_PALETTE),
                            "the theme ramp").group(1).split(","))


def sim_slider(label):
    """(low, high, default, symbol) for one slider in the simulator's source.

    The default may be a literal or a `self.engine.cfg.<field>` reference; the latter is
    better, because it means there is one source of truth. Both are accepted, and which
    one it is gets checked.
    """
    text = read(SIMULATOR)
    match = re.search(r'Slider\([^,]+,\s*"%s",\s*(\d+),\s*(\d+),\s*'
                      r'(\d+|self\.engine\.cfg\.[a-z_]+)' % re.escape(label), text)
    if not match:
        raise SystemExit("could not find the %r slider in led_simulator_v3.py" % label)
    low, high, initial = match.groups()
    if initial.isdigit():
        return int(low), int(high), int(initial), None
    return int(low), int(high), None, initial.rsplit(".", 1)[-1]


SIM_BRIGHTNESS = sim_slider("Brightness")
SIM_FULL_AT = sim_slider("Full at")
SIM_SHIFT = sim_slider("Start at")
SIM_HZ = sim_slider("Flash rate")


# -- the checks ---------------------------------------------------------------

CHECKS = []


def check(what, actual, expected, where):
    CHECKS.append((what, actual, expected, where))


# The simulator's engine must describe the strip's boot state exactly.
check("LED count", engine.DEFAULT_LED_COUNT, FW_LED_COUNT, "main.cpp LED_COUNT")
check("ramp stops", len(engine.DEFAULT_RAMP), FW_RAMP_STOP_COUNT, "main.cpp RAMP_STOP_COUNT")
check("default ramp", engine.DEFAULT_RAMP, FW_RAMP, "main.cpp rampStops[]")
check("full-at rpm", engine.LedConfig().full_rpm, FW_FULL_RPM, "main.cpp rpmFull")
check("theme dim", engine.LedConfig().theme_dim, bool(FW_THEME_DIM), "main.cpp themeDim")
check("strip enabled", engine.LedConfig().enabled, FW_ENABLED, "main.cpp stripEnabled")
check("color mode", engine.LedConfig().color_mode, FW_COLOR_MODE, "main.cpp colorMode")
check("sequence", engine.LedConfig().sequence, engine.SEQ_CENTER_OUT,
      "main.cpp ledSequence")
check("shift rpm", engine.LedConfig().shift_rpm, FW_SHIFT_RPM, "main.cpp shiftRpm")
check("shift rate", engine.LedConfig().shift_hz, FW_SHIFT_HZ, "main.cpp shiftHz")
check("shift color", engine.LedConfig().shift_color, FW_SHIFT_RGB,
      "main.cpp shiftR/G/B")
check("brightness", engine.LedConfig().brightness, FW_BRIGHTNESS,
      "main.cpp currentBrightness")
check("dim scale", engine.DIM_SCALE, FW_DIM_SCALE, "main.cpp DIM_SCALE")
check("full scale", 255, FW_FULL_SCALE, "main.cpp themeDim ? DIM_SCALE : 255")
check("self-test length", engine.SELF_TEST_MS, FW_SELF_TEST_MS, "main.cpp SELF_TEST_MS")
check("identify length", engine.IDENTIFY_MS, FW_IDENTIFY_MS, "main.cpp IDENTIFY_MS")
check("rpm snap", engine.RPM_SNAP_DELTA, FW_SNAP_DELTA, "main.cpp RPM_SNAP_DELTA")
check("rpm rising alpha", engine.RPM_ALPHA_RISING, FW_ALPHA_RISING,
      "main.cpp RPM_ALPHA_RISING")
check("rpm falling alpha", engine.RPM_ALPHA_FALLING, FW_ALPHA_FALLING,
      "main.cpp RPM_ALPHA_FALLING")

# The simulator's sliders must be able to reach anything the strip accepts.
check("sim full-at range", (SIM_FULL_AT[0], SIM_FULL_AT[1]), (FW_FULL_MIN, FW_FULL_MAX),
      "main.cpp CFG:full clamp")
check("sim shift range", (SIM_SHIFT[0], SIM_SHIFT[1]), (FW_SHIFT_MIN, FW_SHIFT_MAX),
      "main.cpp CFG:shift clamp")
check("sim hz range", (SIM_HZ[0], SIM_HZ[1]), (FW_HZ_MIN, FW_HZ_MAX),
      "main.cpp CFG:hz clamp")
check("sim brightness range", (SIM_BRIGHTNESS[0], SIM_BRIGHTNESS[1]), (0, 255),
      "main.cpp CFG:bright clamp")
# A slider that seeds itself from LedConfig cannot drift from the firmware; one that seeds
# itself from a literal can, so either the literal is checked or the field name is.
check("sim full-at default source", SIM_FULL_AT[3], "full_rpm", "LedConfig().full_rpm")
check("sim shift default source", SIM_SHIFT[3], "shift_rpm", "LedConfig().shift_rpm")
check("sim hz default source", SIM_HZ[3], "shift_hz", "LedConfig().shift_hz")
check("sim brightness default", SIM_BRIGHTNESS[2], FW_BRIGHTNESS,
      "main.cpp currentBrightness")

# The Pi's stored defaults must agree with the strip's, where they overlap.
check("pi enabled", PI_DEFAULTS["led_enabled"], 1 if FW_ENABLED else 0, "main.cpp")
check("pi color mode", PI_DEFAULTS["led_color_mode"], FW_COLOR_MODE, "main.cpp")
check("pi sequence", PI_DEFAULTS["led_sequence"], engine.SEQ_CENTER_OUT, "main.cpp")
check("pi shift rpm", PI_DEFAULTS["led_shift_rpm"], FW_SHIFT_RPM, "main.cpp")
check("pi shift rate", PI_DEFAULTS["led_shift_hz"], FW_SHIFT_HZ, "main.cpp")
check("pi shift color", PI_DEFAULTS["led_shift_color"],
      engine.hex_of(FW_SHIFT_RGB), "main.cpp shiftR/G/B")

# ...and the Pi must accept exactly what the strip accepts.
check("pi shift range", (int(LINK_SHIFT.group(1)), int(LINK_SHIFT.group(2))),
      (FW_SHIFT_MIN, FW_SHIFT_MAX), "main.cpp CFG:shift clamp")
check("pi hz range", (int(LINK_HZ.group(1)), int(LINK_HZ.group(2))),
      (FW_HZ_MIN, FW_HZ_MAX), "main.cpp CFG:hz clamp")
check("pi color mode values", tuple(int(v) for v in LINK_COLOR_MODE.groups()), (0, 1),
      "main.cpp colorMode")
check("pi sequence range", (int(LINK_SEQUENCE.group(1)), int(LINK_SEQUENCE.group(2))),
      (1, 4), "main.cpp LEDSequence enum")

# The phone: same ramp derivation, same scale, same ranges.
check("app ramp fractions", APP_FRACTIONS, engine.STOP_FRACTIONS,
      "led_engine.STOP_FRACTIONS")
check("app full-at rpm", APP_FULL_RPM, FW_FULL_RPM, "main.cpp rpmFull")
check("app theme-ramp rpms", APP_THEME_RPMS, tuple(rpm for rpm, _ in engine.DEFAULT_RAMP),
      "main.cpp rampStops[] rpms")
check("app full-at range", (APP_FULL_AT[0], APP_FULL_AT[1]), (FW_FULL_MIN, FW_FULL_MAX),
      "main.cpp CFG:full clamp")
check("app shift range", (APP_SHIFT[0], APP_SHIFT[1]), (FW_SHIFT_MIN, FW_SHIFT_MAX),
      "main.cpp CFG:shift clamp")
check("app hz range", (APP_HZ[0], APP_HZ[1]), (FW_HZ_MIN, FW_HZ_MAX),
      "main.cpp CFG:hz clamp")
check("app brightness range", (APP_BRIGHTNESS[0], APP_BRIGHTNESS[1]), (0, 255),
      "main.cpp CFG:bright clamp")
check("app full-at default", APP_FULL_AT[3] if APP_FULL_AT[3] is not None else APP_FULL_RPM,
      FW_FULL_RPM, "main.cpp rpmFull")
check("app shift default", APP_SHIFT[3], FW_SHIFT_RPM, "main.cpp shiftRpm")
check("app hz default", APP_HZ[3], FW_SHIFT_HZ, "main.cpp shiftHz")
check("app brightness default", APP_BRIGHTNESS[3], FW_BRIGHTNESS,
      "main.cpp currentBrightness")
check("app mode values", APP_MODE_VALUES, (0, 1), "main.cpp colorMode")
check("app sequence values", APP_SEQ_VALUES, (1, 2, 3, 4), "main.cpp LEDSequence enum")
check("app swatch count", APP_RAMP_STOPS, len(engine.DEFAULT_RAMP),
      "main.cpp RAMP_STOP_COUNT")


def main():
    failures = [(what, actual, expected, where)
                for what, actual, expected, where in CHECKS if actual != expected]

    # The RAMP: contract, exercised rather than parsed: the simulator's parser must accept
    # and reject exactly what the Pi's validator does, or `--pi` would load something the
    # strip could not have been given.
    functional = []

    def accepts(text):
        try:
            engine.parse_ramp(text)
            return True
        except ValueError:
            return False

    ramp_cases = [
        ("2 stops", "0:0000ff,6800:ff0000", True),
        ("6 stops", engine.format_ramp(engine.DEFAULT_RAMP), True),
        ("1 stop", "0:0000ff", False),
        ("7 stops", ",".join("%d:000000" % (i * 100) for i in range(7)), False),
        ("5-digit hex", "0:00000,6800:ff0000", False),
        ("7-digit hex", "0:0000000,6800:ff0000", False),
        ("non-hex color", "0:zzzzzz,6800:ff0000", False),
        ("signed rpm", "-100:0000ff,6800:ff0000", False),
        ("empty rpm", ":0000ff,6800:ff0000", False),
        # Legal but odd: the Pi accepts any order, and so must the simulator, because that
        # is what the strip does.
        ("descending", "0:0000ff,3000:00ff00,1500:ff0000", True),
        ("duplicate rpm", "0:0000ff,2000:00ff00,2000:ff0000", True),
    ]
    for name, text, expected in ramp_cases:
        if accepts(text) != expected:
            functional.append(("ramp accepts %s" % name, accepts(text), expected,
                               "pi/ui/src/link_service.py led_ramp validation"))

    # ...and the Pi's own bounds, parsed earlier, must be the same 2-6.
    stop_bounds = re.search(r"if not (\d+) <= len\(parts\) <= (\d+)", LINK)
    if stop_bounds:
        if (int(stop_bounds.group(1)), int(stop_bounds.group(2))) != (2, len(FW_RAMP)):
            functional.append(("pi ramp stop bounds",
                               tuple(int(v) for v in stop_bounds.groups()),
                               (2, len(FW_RAMP)), "main.cpp RAMP_STOP_COUNT"))

    if not failures and not functional:
        print("%d settings match across firmware, Pi, app and simulator"
              % (len(CHECKS) + len(ramp_cases) + 1))
        return 0

    print("%d settings disagree:\n" % (len(failures) + len(functional)))
    for what, actual, expected, where in failures + functional:
        print("  %-24s simulator/Pi/app %r\n  %-24s firmware        %r   (%s)\n"
              % (what + ":", actual, "", expected, where))
    return 1


if __name__ == "__main__":
    sys.exit(main())
