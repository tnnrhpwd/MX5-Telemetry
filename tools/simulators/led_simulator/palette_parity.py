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

        problems.extend(check_theme_follows())

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


# The colors that must not follow the theme: they say "something is wrong" and have to read
# the same in every scheme. `alert` is the exception Palette.java documents by name.
ALARM_COLORS = {"warn": app_palette.WARN, "bad": app_palette.BAD}


def check_theme_follows() -> List[str]:
    """The ramp must actually be the theme's, which matching `Palette.java` does not prove.

    A faithful port of a ramp built from `good`, `warn`, `bad` and `alert` would pass every
    check above and still look identical in all twelve schemes - that is exactly what it
    used to do, with four of the six stops the same in every theme. So this asserts the two
    properties that make "the ramp follows the theme" true:

      - every scheme produces a different ramp, at every stop;
      - no stop is one of the fixed alarm colors.
    """
    problems = []
    ramps = {(ident, dark): app_palette.ramp_for(app_palette.palette(ident, dark))
             for ident, _n, _a, _b in app_palette.SCHEMES for dark in (True, False)}

    # Within a mode: the dark and light ramps of one scheme share their final stop by
    # design (it is the scheme's own seed), so comparing across modes would report that.
    for dark in (True, False):
        mode = "dark" if dark else "light"
        for index in range(len(app_palette.RAMP_RPMS)):
            rgb = {}
            for ident, _n, _a, _b in app_palette.SCHEMES:
                stops = ramps[(ident, dark)]
                rgb.setdefault(stops[index][1], []).append(ident)
            for color, owners in rgb.items():
                if len(owners) > 1:
                    problems.append("stop %d is %02x%02x%02x in %d %s schemes (%s) - the "
                                    "ramp is not following the theme"
                                    % ((index,) + tuple(color) + (len(owners), mode,
                                                                  ", ".join(sorted(owners)))))
                    break

    for (ident, dark), stops in ramps.items():
        for index, _rpm in enumerate(app_palette.RAMP_RPMS):
            color = stops[index][1]
            packed = (color[0] << 16) | (color[1] << 8) | color[2]
            for name, alarm in ALARM_COLORS.items():
                if packed == alarm:
                    problems.append("%s/%s stop %d is the fixed %s alarm color - alarm colors "
                                    "must not appear in the theme ramp"
                                    % (ident, "dark" if dark else "light", index, name))

    # The shift flash follows the theme too, so it must not be an alarm color either, and
    # every scheme must actually differ.
    shift = {(ident, dark): app_palette.shift_text(ident, dark)
             for ident, _n, _a, _b in app_palette.SCHEMES for dark in (True, False)}
    for (ident, dark), value in shift.items():
        packed = int(value, 16)
        for name, alarm in ALARM_COLORS.items():
            if packed == alarm:
                problems.append("%s/%s shift color is the fixed %s alarm color - the flash "
                                "follows the theme"
                                % (ident, "dark" if dark else "light", name))
        if value == "ff0000":
            problems.append("%s/%s shift color is the fixed red default - the flash is not "
                            "following the theme" % (ident, "dark" if dark else "light"))
    return problems


if __name__ == "__main__":
    sys.exit(main())
