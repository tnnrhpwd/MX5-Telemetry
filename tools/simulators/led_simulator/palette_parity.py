#!/usr/bin/env python3
"""Prove the simulator's copy of the app's color schemes is the app's.

`app_palette.py` ports `Palette.java`, because the phone owns the strip's colors and the
simulator has to be able to show what the phone would push. A port of a color derivation is
easy to get subtly wrong - a rounding here, an alpha channel there - and the result would
look plausible and be wrong.

So this compiles the *real* `Palette.java` with a stub for `android.graphics.Color`, runs
`Palette.ramp()` for all twelve schemes in both modes, and requires the six-stop ramp to
match exactly. The derivation is called rather than transcribed, so the harness cannot
drift from the app; the stop rpms and `MainActivity`'s use of `ramp()` are parsed out of
the app sources as well.

Matching is not enough on its own, so it then checks what the ramp has to *mean*: the same
six colours in every scheme and mode, equal to the firmware's own `rampStops[]` default
(parsed from `arduino/src/main.cpp`), red at the top, no white stop, and a red shift flash.

    python palette_parity.py
    python palette_parity.py --keep     # keep the generated Java

Needs a JDK (javac + java). Without one it reports SKIPPED and exits 0.
"""

from __future__ import annotations

import argparse
import os
import re
import shutil
import subprocess
import sys
import tempfile
from typing import List, Optional, Tuple

HERE = os.path.dirname(os.path.abspath(__file__))
REPO = os.path.abspath(os.path.join(HERE, "..", "..", ".."))
PALETTE_JAVA = os.path.join(REPO, "android", "mx5-remote", "src", "main", "java",
                            "com", "mx5", "remote", "Palette.java")
MAIN_JAVA = os.path.join(REPO, "android", "mx5-remote", "src", "main", "java",
                         "com", "mx5", "remote", "MainActivity.java")

LED_SCREEN_JAVA = os.path.join(REPO, "android", "mx5-remote", "src", "main", "java",
                               "com", "mx5", "remote", "LedScreen.java")

sys.path.insert(0, HERE)

import app_palette  # noqa: E402

# Just enough of android.graphics.Color for Palette.java to compile. The arithmetic is
# trivial and unambiguous, which is what makes stubbing it safe.
COLOR_STUB = """
package android.graphics;

public class Color {
    public static final int BLACK = 0xFF000000;
    public static final int WHITE = 0xFFFFFFFF;

    public static int alpha(int color) { return (color >> 24) & 0xFF; }
    public static int red(int color)   { return (color >> 16) & 0xFF; }
    public static int green(int color) { return (color >> 8) & 0xFF; }
    public static int blue(int color)  { return color & 0xFF; }

    public static int argb(int alpha, int red, int green, int blue) {
        return (alpha << 24) | (red << 16) | (green << 8) | blue;
    }
}
"""

HARNESS = """
package com.mx5.remote;

public final class PrintRamps {
    public static void main(String[] args) {
        for (Palette.Scheme scheme : Palette.SCHEMES) {
            for (int dark = 1; dark >= 0; dark--) {
                Palette p = Palette.of(scheme.id, dark == 1);
                // The app's own derivation, called rather than transcribed.
                int[] colors = p.ramp();
                int[] rpms = Palette.RAMP_RPMS;
                StringBuilder line = new StringBuilder();
                line.append(scheme.id).append(' ').append(dark);
                for (int i = 0; i < colors.length; i++) {
                    line.append(' ').append(rpms[i]).append(':');
                    line.append(String.format("%06x", colors[i] & 0xFFFFFF));
                }
                line.append(" shift:").append(String.format("%06x", p.shiftColor() & 0xFFFFFF));
                System.out.println(line);
            }
        }
    }
}
"""


def read(path: str) -> str:
    with open(path, encoding="utf-8") as handle:
        return handle.read()


def parse_ramp_rpms() -> List[int]:
    """The stop rpms, straight out of `Palette.RAMP_RPMS`."""
    match = re.search(r"RAMP_RPMS\s*=\s*\{([^}]*)\}", read(PALETTE_JAVA))
    if not match:
        raise SystemExit("could not find Palette.RAMP_RPMS in Palette.java")
    return [int(part.strip()) for part in match.group(1).split(",")]


def check_main_uses_ramp() -> Optional[str]:
    """`ledRampFor()` must build its colors from `Palette.ramp()`, not its own list.

    The ramp used to be `{p.accent, p.primary, p.good, p.warn, p.bad, p.alert}` written
    inline here. If that comes back, every theme would send four identical stops again and
    none of the checks below would notice - they only look at `Palette.ramp()`.
    """
    text = read(MAIN_JAVA)
    body = re.search(r"private static String ledRampFor\(Palette p\)\s*\{(.*?)\n    \}",
                     text, re.S)
    if not body:
        return "could not find ledRampFor() in MainActivity.java"
    if "p.ramp()" not in body.group(1):
        return "MainActivity.ledRampFor() no longer takes its colors from Palette.ramp()"
    return None


def find_jdk() -> Optional[Tuple[str, str]]:
    javac = shutil.which("javac")
    java = shutil.which("java")
    if javac and java:
        return javac, java
    return None


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--keep", action="store_true")
    args = parser.parse_args()

    if not os.path.exists(PALETTE_JAVA):
        print("SKIPPED: %s not found" % PALETTE_JAVA)
        return 0
    jdk = find_jdk()
    if jdk is None:
        print("SKIPPED: no JDK found (need javac and java on PATH)")
        return 0
    javac, java = jdk
    print("javac:", javac)

    roles_stops = parse_ramp_rpms()

    work = tempfile.mkdtemp(prefix="mx5-palette-parity-")
    try:
        package = os.path.join(work, "com", "mx5", "remote")
        android = os.path.join(work, "android", "graphics")
        os.makedirs(package)
        os.makedirs(android)

        shutil.copy(PALETTE_JAVA, os.path.join(package, "Palette.java"))
        with open(os.path.join(android, "Color.java"), "w", encoding="utf-8") as handle:
            handle.write(COLOR_STUB)
        with open(os.path.join(package, "PrintRamps.java"), "w", encoding="utf-8") as handle:
            handle.write(HARNESS)

        sources = []
        for dirpath, _dirnames, filenames in os.walk(work):
            for name in filenames:
                if name.endswith(".java"):
                    sources.append(os.path.join(dirpath, name))
        compiled = subprocess.run([javac, "-d", os.path.join(work, "classes")] + sources,
                                  capture_output=True, text=True, timeout=300)
        if compiled.returncode != 0:
            raise SystemExit("javac failed:\n%s\n%s" % (compiled.stdout, compiled.stderr))

        run = subprocess.run([java, "-cp", os.path.join(work, "classes"),
                              "com.mx5.remote.PrintRamps"],
                             capture_output=True, text=True, timeout=120)
        if run.returncode != 0:
            raise SystemExit("java failed:\n%s" % run.stderr)

        problems = []
        lines = [line.split() for line in run.stdout.splitlines() if line.strip()]
        seen = set()
        for parts in lines:
            scheme_id, dark_flag = parts[0], parts[1] == "1"
            seen.add((scheme_id, dark_flag))
            java_stops = parts[2:]
            java_shift = java_stops[-1].split(":", 1)[1]
            java_stops = java_stops[:-1]

            pal = app_palette.palette(scheme_id, dark_flag)
            py_stops = ["%d:%02x%02x%02x" % (rpm, rgb[0], rgb[1], rgb[2])
                        for rpm, rgb in app_palette.ramp_for(pal)]
            py_shift = app_palette.shift_text(scheme_id, dark_flag)

            if java_stops != py_stops:
                problems.append("%s (%s):\n    java   %s\n    python %s"
                                % (scheme_id, "dark" if dark_flag else "light",
                                   " ".join(java_stops), " ".join(py_stops)))
            if java_shift != py_shift:
                problems.append("%s (%s) shift color: java %s, python %s"
                                % (scheme_id, "dark" if dark_flag else "light",
                                   java_shift, py_shift))

        expected = {(ident, dark) for ident, _n, _a, _b in app_palette.SCHEMES
                    for dark in (True, False)}
        if seen != expected:
            problems.append("scheme/mode coverage differs: missing %s"
                            % sorted(expected - seen))

        # The recipe itself must be the app's, not something convenient.
        misuse = check_main_uses_ramp()
        if misuse:
            problems.append(misuse)
        if list(app_palette.RAMP_RPMS) != roles_stops:
            problems.append("stop rpms: app uses %s, port uses %s"
                            % (roles_stops, list(app_palette.RAMP_RPMS)))

        problems.extend(check_ramp_is_the_engine())

        print("schemes: %d   modes: 2   ramps compared: %d"
              % (len(app_palette.SCHEMES), len(lines)))
        if not problems:
            print("PALETTE PARITY OK - every ramp matches Palette.java exactly")
            return 0
        for problem in problems:
            print("MISMATCH", problem)
        return 1
    finally:
        if args.keep:
            print("generated files kept in", work)
        else:
            shutil.rmtree(work, ignore_errors=True)


FIRMWARE = os.path.join(REPO, "arduino", "src", "main.cpp")


def firmware_ramp() -> List[Tuple[int, Tuple[int, int, int]]]:
    """The Nano's default `rampStops[]`, parsed out of the firmware source."""
    text = read(FIRMWARE)
    match = re.search(r"RampStop rampStops\[RAMP_STOP_COUNT\]\s*=\s*\{(.*?)\n\};", text, re.S)
    if not match:
        raise SystemExit("could not find rampStops[] in arduino/src/main.cpp")
    stops = [(int(rpm), (int(r), int(g), int(b)))
             for rpm, r, g, b in re.findall(
                 r"\{\s*(\d+)\s*,\s*(\d+)\s*,\s*(\d+)\s*,\s*(\d+)\s*\}", match.group(1))]
    if len(stops) != len(app_palette.RAMP_RPMS):
        raise SystemExit("firmware ramp has %d stops, the app has %d"
                         % (len(stops), len(app_palette.RAMP_RPMS)))
    return stops


def parse_led_screen_defaults() -> List[str]:
    """The LED editor's starting colours, straight out of `LedScreen.DEFAULT_COLOURS`.

    A fourth copy of the same six colours lives there, and nothing else compares it to
    anything - so it could drift to a different blue and red without a single test
    noticing, which is exactly what it had already done (`0a84ff`, `ef4444`).
    """
    match = re.search(r"DEFAULT_COLOURS\s*=\s*\{([^}]*)\}", read(LED_SCREEN_JAVA))
    if not match:
        raise SystemExit("could not find LedScreen.DEFAULT_COLOURS")
    return [value.strip().strip('"').lower()
            for value in match.group(1).split(",") if value.strip()]


def check_ramp_is_the_engine() -> List[str]:
    """The ramp must be the engine's, and identical everywhere.

    Matching `Palette.java` only proves the port is faithful. These are the properties the
    strip actually needs, and the ones the owner asked for after the 2026-11-26 drive:

      - every scheme and mode produces the *same* ramp, because the colours encode rpm;
      - that ramp is the firmware's own `rampStops[]` default, so the bar looks the same
        before and after the phone pushes one;
      - every stop and every colour *between* stops is fully saturated, because the bar is
        interpolated in RGB: a stop with a lifted channel drags both of its segments toward
        grey. The previous green (0x32d782, 77%) and yellow (0xffd23c, 76%) passed the old
        "is it white?" check and still measured 50% saturation at 3300 rpm on the strip;
      - the top of the bar is red and no stop is white;
      - the shift flash is red.
    """
    problems: List[str] = []
    fw = firmware_ramp()
    if [rpm for rpm, _rgb in fw] != list(app_palette.RAMP_RPMS):
        problems.append("stop rpms: app %s, firmware %s"
                        % (list(app_palette.RAMP_RPMS), [rpm for rpm, _rgb in fw]))
    want = [rgb for _rpm, rgb in fw]
    want_hex = ["%02x%02x%02x" % rgb for rgb in want]
    editor = parse_led_screen_defaults()
    if editor != want_hex:
        problems.append("LedScreen.DEFAULT_COLOURS is %s, firmware ramp is %s"
                        % (editor, want_hex))

    # Every stop, and every colour the renderer can produce between two stops. Saturation
    # here is the same quantity the eye judges: min channel over max channel. Full
    # saturation means one channel is zero, which also makes the interpolation preserve it.
    for rpm, rgb in fw:
        high, low = max(rgb), min(rgb)
        if low > 0 and high > 0:
            problems.append("stop %d rpm %s is only %d%% saturated (min channel %d)"
                            % (rpm, rgb, round(100 * (high - low) / high), low))
    for (rpm_a, a), (rpm_b, b) in zip(fw, fw[1:]):
        for step in range(1, 8):
            t = step / 8.0
            mid = tuple(round(a[i] + (b[i] - a[i]) * t) for i in range(3))
            if min(mid) > 0:
                problems.append("between %d and %d rpm, %d/%d of the way: %s is only "
                                "%d%% saturated (min channel %d)"
                                % (rpm_a, rpm_b, step, 8, mid,
                                   round(100 * (max(mid) - min(mid)) / max(max(mid), 1)),
                                   min(mid)))

    for ident, _name, _a, _b in app_palette.SCHEMES:
        for dark in (True, False):
            where = "%s/%s" % (ident, "dark" if dark else "light")
            got = [rgb for _rpm, rgb in app_palette.ramp_for(app_palette.palette(ident, dark))]
            if got != want:
                problems.append("%s: app ramp %s, firmware %s" % (where, got, want))
            top = got[-1]
            if not (top[0] >= 200 and top[1] < 60 and top[2] < 60):
                problems.append("%s: redline stop is %s, not red" % (where, top))
            for rgb in got:
                high, low = max(rgb), min(rgb)
                if high > 180 and high - low < 20:
                    problems.append("%s: stop %s is white" % (where, rgb))
            shift = app_palette.shift_text(ident, dark).upper()
            if shift != "FF0000":
                problems.append("%s: shift color is %s, not red" % (where, shift))
    return problems

if __name__ == "__main__":
    sys.exit(main())
