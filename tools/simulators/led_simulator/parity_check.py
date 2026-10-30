#!/usr/bin/env python3
"""Prove the simulator's rendering is the firmware's rendering, by compiling both.

The port in `led_engine.py` was written by reading `arduino/src/main.cpp`, and reading is
exactly how a port drifts: a cast in the wrong place, a `<` that should be `<=`, a float
where the C is an integer. Hand-computed unit tests catch the mistakes the author thought
of. This catches the rest.

How it works
------------
1. The exact source text of the rendering functions is *extracted from main.cpp* - not
   retyped - and dropped into a small C++ translation unit with stubs for the Arduino bits
   (a pixel buffer instead of NeoPixel, a settable `millis()`).
2. That file is compiled with MSVC and run over a matrix of cases: every fill pattern, both
   color modes, dim on and off, several "full at" scales, ramps including the default and
   deliberately uneven ones, the idle/shift/offline/error/self-test states, and the
   brightness scale.
3. The same cases go through `led_engine.py`, and every pixel of every frame must match
   exactly.

Because the C++ side is extracted from `main.cpp`, editing the firmware without touching
the port makes this fail - which is the point.

    python parity_check.py                 # build, run, compare
    python parity_check.py --keep          # leave the generated files for inspection
    python parity_check.py --cases 400     # widen the matrix (default 120 random cases)

Needs a C++ compiler. MSVC is found through vswhere; set MX5_CL to an explicit cl.exe if
you have one somewhere else. A g++ (or clang++) on PATH is used when MSVC is absent, which
is what lets this run on the Pi alongside the rest of the checks. Without a compiler the
check reports SKIPPED and exits 0, so it can sit in a test run on a machine that only has
Python.
"""

from __future__ import annotations

import argparse
import json
import os
import random
import re
import shutil
import subprocess
import sys
import tempfile
from typing import List, Optional, Tuple

HERE = os.path.dirname(os.path.abspath(__file__))
REPO = os.path.abspath(os.path.join(HERE, "..", "..", ".."))
MAIN_CPP = os.path.join(REPO, "arduino", "src", "main.cpp")

sys.path.insert(0, HERE)

import led_engine as engine  # noqa: E402
from led_engine import LedConfig, LedEngine  # noqa: E402

# The functions under test. Order matters: later ones call earlier ones.
FUNCTIONS = [
    "rampColorAtRpm",
    "barRank",
    "barSlots",
    "predictRPM",
    "renderBar",
    "drawCanOffline",
    "drawSelfTest",
    "updateErrorAnimation",
    "updateLEDs",
]


# -- extraction ---------------------------------------------------------------

def _read_main() -> str:
    with open(MAIN_CPP, encoding="utf-8") as handle:
        return handle.read()


def extract_function(source: str, name: str) -> str:
    """Return the full text of a function *definition*, by brace matching.

    Deliberately textual: the point is to compile the firmware's own characters, so a
    retyped copy would defeat the exercise. Declarations (`void f(...);` in the forward
    block) are skipped - matching one of those and then brace-matching from the next `{`
    in the file silently swallows everything in between, which is how this first went
    wrong.
    """
    pattern = re.compile(r"^(?:inline\s+)?(?:void|bool|uint8_t|uint16_t|int)\s+" + name
                         + r"\s*\(", re.M)
    for match in pattern.finditer(source):
        # The first `{` or `;` after the signature decides: `;` means it was a prototype.
        cursor = match.end()
        brace = -1
        while cursor < len(source):
            char = source[cursor]
            if char == "{":
                brace = cursor
                break
            if char == ";":
                break
            cursor += 1
        if brace < 0:
            continue

        start = source.rfind("\n", 0, match.start()) + 1
        depth = 0
        for index in range(brace, len(source)):
            char = source[index]
            if char == "{":
                depth += 1
            elif char == "}":
                depth -= 1
                if depth == 0:
                    return source[start:index + 1]
    raise SystemExit("could not find a definition of %s in main.cpp" % name)


def extract_define(source: str, name: str) -> str:
    match = re.search(r"^#define\s+" + name + r"\s+(.+)$", source, re.M)
    if not match:
        raise SystemExit("could not find #define %s" % name)
    return match.group(1).strip()


def extract_enum_value(source: str, name: str) -> str:
    """Pull one enumerator's value out of its enum, so we compile the real number."""
    match = re.search(r"^\s*" + name + r"\s*=\s*(\d+)", source, re.M)
    if not match:
        raise SystemExit("could not find enumerator %s" % name)
    return match.group(1)


def extract_initializer(source: str, declaration: str) -> str:
    match = re.search(re.escape(declaration) + r"\s*=\s*(.+?);", source, re.S)
    if not match:
        raise SystemExit("could not find initializer for %r" % declaration)
    return match.group(1).strip()


# -- the generated harness ----------------------------------------------------

HARNESS_PRELUDE = r"""
// Generated by parity_check.py from arduino/src/main.cpp. Do not edit.
#include <stdint.h>
#include <stdio.h>
#include <stdlib.h>
#include <string.h>

// ---- Arduino stubs ---------------------------------------------------------
unsigned long millis_value = 0;
static unsigned long millis() { return millis_value; }

struct FakeStrip {
    uint8_t r[LED_COUNT], g[LED_COUNT], b[LED_COUNT];
    FakeStrip() { clear(); }
    uint32_t Color(uint8_t r_, uint8_t g_, uint8_t b_) {
        return ((uint32_t)r_ << 16) | ((uint32_t)g_ << 8) | (uint32_t)b_;
    }
    void setPixelColor(uint16_t i, uint32_t c) {
        if (i < LED_COUNT) {
            r[i] = (uint8_t)(c >> 16); g[i] = (uint8_t)(c >> 8); b[i] = (uint8_t)c;
        }
    }
    void clear() { memset(r, 0, sizeof r); memset(g, 0, sizeof g); memset(b, 0, sizeof b); }
    uint32_t getPixelColor(uint16_t i) {
        return ((uint32_t)r[i] << 16) | ((uint32_t)g[i] << 8) | (uint32_t)b[i];
    }
    void show() {}                      // the buffer is the state; show() is plumbing
};
FakeStrip strip;
static void showIfChanged() {}          // the buffer is the state; show() is plumbing

#define SET_LED(idx, r_, g_, b_) strip.setPixelColor(idx, strip.Color(r_, g_, b_))
#define CLEAR_LED(idx) strip.setPixelColor(idx, 0)

#define ENABLE_HAPTIC false
#define RPM_REDLINE 6800

// ---- globals the extracted functions read ----------------------------------
struct RampStop { uint16_t rpm; uint8_t r, g, b; };
RampStop rampStops[RAMP_STOP_COUNT];
uint8_t  rampStopCount = RAMP_STOP_COUNT;
uint16_t rpmFull;
uint8_t  themeDim;
bool     stripEnabled;
uint8_t  colorMode;
uint8_t  ledSequence;
uint16_t shiftRpm;
uint8_t  shiftHz;
uint8_t  shiftR, shiftG, shiftB;
uint8_t  currentBrightness;

bool canInitialized;
bool demoForced;
unsigned long demoExpiresAt;
uint16_t demoRPM;
bool displayErrorMode;
uint16_t currentRPM;
static uint16_t lastRenderedRPM;
static bool stripForceShow;
bool errorMode;

// Prediction state. The harness never sets it, so `predictRPM()` holds the sample and the
// frames below stay a pure function of `currentRPM`; the prediction itself is checked
// separately by check_prediction().
static uint16_t rpmLast = 0;
static uint16_t rpmPrev = 0;
static unsigned long rpmLastMs = 0;
static unsigned long rpmPrevMs = 0;
static bool rpmHaveHistory = false;

uint8_t  selfTestMode;
unsigned long selfTestStart;
uint8_t  errorScanPosition;
int8_t   errorScanDirection;
unsigned long lastErrorAnimation;
"""

HARNESS_MAIN = r"""
// ---- driver ----------------------------------------------------------------
static int read_ints(long* out, int count) {
    for (int i = 0; i < count; i++) {
        if (scanf("%ld", &out[i]) != 1) return 0;
    }
    return 1;
}

static void print_frame(void) {
    for (int i = 0; i < LED_COUNT; i++) {
        printf("%02x%02x%02x%c", strip.r[i], strip.g[i], strip.b[i],
               i == LED_COUNT - 1 ? '\n' : ' ');
    }
}

int main(void) {
    long v[32];
    for (;;) {
        if (!read_ints(v, 18)) return 0;
        currentRPM        = (uint16_t)v[0];
        ledSequence       = (uint8_t)v[1];
        colorMode         = (uint8_t)v[2];
        themeDim          = (uint8_t)v[3];
        rpmFull           = (uint16_t)v[4];
        shiftRpm          = (uint16_t)v[5];
        shiftHz           = (uint8_t)v[6];
        shiftR            = (uint8_t)v[7];
        shiftG            = (uint8_t)v[8];
        shiftB            = (uint8_t)v[9];
        stripEnabled      = v[10] != 0;
        canInitialized    = v[11] != 0;
        displayErrorMode  = v[12] != 0;
        errorMode         = displayErrorMode;
        demoForced        = v[13] != 0;
        demoRPM           = (uint16_t)v[14];
        demoExpiresAt     = demoForced ? 0xFFFFFFFFUL : 0;
        selfTestMode      = (uint8_t)v[15];
        selfTestStart     = (unsigned long)v[16];
        long frames       = v[17];

        if (!read_ints(v, 1)) return 0;
        int stops = (int)v[0];
        if (stops < 2 || stops > RAMP_STOP_COUNT) return 1;
        if (!read_ints(v, stops * 4)) return 1;
        for (int i = 0; i < stops; i++) {
            rampStops[i].rpm = (uint16_t)v[i * 4 + 0];
            rampStops[i].r    = (uint8_t)v[i * 4 + 1];
            rampStops[i].g    = (uint8_t)v[i * 4 + 2];
            rampStops[i].b    = (uint8_t)v[i * 4 + 3];
        }
        rampStopCount = (uint8_t)stops;

        // Deterministic animation state, set up once per case so a run of frames is a
        // continuous animation rather than N independent ones.
        lastRenderedRPM = 0xFFFF;
        stripForceShow  = true;
        errorScanPosition   = 0;
        errorScanDirection  = 1;
        lastErrorAnimation  = 0;
        strip.clear();

        // A case is a run of frames: updateLEDs() is called once per timestamp and the
        // buffer printed after each. That is what exercises the repaint gate and the
        // time-driven patterns (scanner, shift blink) instead of only their first frame.
        for (long f = 0; f < frames; f++) {
            if (!read_ints(v, 1)) return 0;
            millis_value = (unsigned long)v[0];
            updateLEDs();
            print_frame();
        }
    }
}
"""


def build_harness(source: str, led_count: int) -> str:
    parts = ["// Generated by parity_check.py from arduino/src/main.cpp. Do not edit.",
             "#define LED_COUNT %d" % led_count,
             "#define RAMP_STOP_COUNT %s" % extract_define(source, "RAMP_STOP_COUNT"),
             "#define DIM_SCALE %s" % extract_define(source, "DIM_SCALE"),
             "#define SELF_TEST_NONE %s" % extract_define(source, "SELF_TEST_NONE"),
             "#define SELF_TEST_SWEEP %s" % extract_define(source, "SELF_TEST_SWEEP"),
             "#define SELF_TEST_IDENTIFY %s" % extract_define(source, "SELF_TEST_IDENTIFY"),
             "#define SELF_TEST_MS %s" % extract_define(source, "SELF_TEST_MS"),
             "#define IDENTIFY_MS %s" % extract_define(source, "IDENTIFY_MS"),
             "#define SEQ_CENTER_OUT %s" % extract_enum_value(source, "SEQ_CENTER_OUT"),
             "#define SEQ_LEFT_TO_RIGHT %s" % extract_enum_value(source,
                                                               "SEQ_LEFT_TO_RIGHT"),
             "#define SEQ_RIGHT_TO_LEFT %s" % extract_enum_value(source,
                                                               "SEQ_RIGHT_TO_LEFT"),
             "#define SEQ_CENTER_IN %s" % extract_enum_value(source, "SEQ_CENTER_IN"),
             HARNESS_PRELUDE]
    for name in FUNCTIONS:
        parts.append("\n// ---- %s (verbatim from main.cpp) ----" % name)
        parts.append(extract_function(source, name))
    parts.append(HARNESS_MAIN)
    return "\n".join(parts)


def find_compiler() -> Optional[str]:
    explicit = os.environ.get("MX5_CL")
    if explicit and os.path.exists(explicit):
        return explicit
    if shutil.which("cl"):
        return "cl"
    vswhere = os.path.join(os.environ.get("ProgramFiles(x86)", r"C:\Program Files (x86)"),
                           "Microsoft Visual Studio", "Installer", "vswhere.exe")
    if os.path.exists(vswhere):
        try:
            roots = subprocess.run(
                [vswhere, "-latest", "-products", "*",
                 "-requires", "Microsoft.VisualStudio.Component.VC.Tools.x86.x64",
                 "-property", "installationPath"],
                capture_output=True, text=True, timeout=60).stdout.splitlines()
        except Exception:
            roots = []
        for root in roots:
            root = root.strip()
            if not root:
                continue
            tools = os.path.join(root, "VC", "Tools", "MSVC")
            if not os.path.isdir(tools):
                continue
            for version in sorted(os.listdir(tools), reverse=True):
                candidate = os.path.join(tools, version, "bin", "Hostx64", "x64", "cl.exe")
                if os.path.exists(candidate):
                    return candidate

    # No MSVC. This check is the strongest proof the LED port matches the firmware, so it
    # should not be Windows-only: the Pi that runs the simulator already has g++.
    for name in ("g++", "clang++", "c++"):
        found = shutil.which(name)
        if found:
            return found
    return None


def _is_msvc(compiler: str) -> bool:
    return os.path.basename(compiler).lower().split('.')[0] in ('cl', 'clang-cl')


def _compile(work: str, compiler: str, source: str, name: str) -> str:
    """Compile one harness source in `work` and return the executable's path.

    MSVC needs INCLUDE/LIB from vcvars loaded in the same cmd process; g++ and clang++
    need nothing. Everything else about the two is the same command shape, which is why
    the four harnesses below share this instead of each spelling out `cl`.
    """
    if _is_msvc(compiler):
        exe_name = name + ".exe"
        command = 'cl /nologo /std:c++17 /O2 /EHsc %s /Fe:%s' % (source, exe_name)
        if compiler != "cl":
            vcvars = _vcvars_for(compiler)
            if not vcvars:
                raise SystemExit("could not find vcvars64.bat above %s" % compiler)
            command = 'call "%s" >nul && %s' % (vcvars, command)
        result = subprocess.run(command, shell=True, cwd=work, capture_output=True,
                                text=True, timeout=300)
    else:
        # No extension on POSIX, and the returned path has to match what was built.
        exe_name = name + (".exe" if os.name == "nt" else "")
        result = subprocess.run([compiler, "-std=c++17", "-O2", source, "-o", name],
                                cwd=work, capture_output=True, text=True, timeout=300)

    exe = os.path.join(work, exe_name)
    if result.returncode != 0 or not os.path.exists(exe):
        raise SystemExit("%s compile failed:\n%s\n%s"
                         % (name, result.stdout, result.stderr))
    return exe


def _vcvars_for(cl_path: str) -> Optional[str]:
    """Walk up from cl.exe to the directory holding VC\\Auxiliary\\Build\\vcvars64.bat."""
    directory = os.path.dirname(os.path.abspath(cl_path))
    for _ in range(10):
        for candidate in (os.path.join(directory, "Auxiliary", "Build", "vcvars64.bat"),
                          os.path.join(directory, "VC", "Auxiliary", "Build",
                                       "vcvars64.bat")):
            if os.path.exists(candidate):
                return candidate
        parent = os.path.dirname(directory)
        if parent == directory:
            break
        directory = parent
    return None


def compile_harness(work: str, compiler: str) -> str:
    """Compile the main harness, which is where most of the comparison happens."""
    return _compile(work, compiler, "verify.cpp", "verify")


# -- cases --------------------------------------------------------------------

def _ramp_variants() -> List[Tuple[Tuple[int, engine.RGB], ...]]:
    variants = [engine.DEFAULT_RAMP]
    # Uneven and short tables: the piecewise lookup is where a port is most likely to
    # disagree, so exercise gaps and a two-stop ramp.
    variants.append(((0, (10, 20, 30)), (4000, (200, 100, 50))))
    variants.append(((0, (0, 0, 255)), (500, (255, 0, 0)), (8000, (0, 255, 0))))
    variants.append(((1000, (1, 2, 3)), (1200, (4, 5, 6)), (1300, (7, 8, 9)),
                     (7000, (250, 251, 252))))
    # Out-of-order and duplicated stops. `rampColorAtRpm` returns at the first stop whose
    # rpm is >= the request, so a descending table makes the later stops unreachable and a
    # duplicate pair collapses span to 0 (t = 1, so the later color wins). The Pi accepts
    # any order, so this is reachable in the car and worth pinning.
    variants.append(((0, (0, 0, 255)), (3000, (0, 255, 0)), (1500, (255, 0, 0))))
    variants.append(((0, (9, 9, 9)), (2000, (10, 20, 30)), (2000, (200, 100, 50))))
    variants.append(((500, (1, 1, 1)), (500, (2, 2, 2))))
    variants.append(((0, (255, 255, 255)), (1, (0, 0, 0)), (2, (255, 0, 0)),
                     (3, (0, 255, 0)), (4, (0, 0, 255)), (65535, (128, 128, 128))))
    return variants


def _case(nows=None, **kwargs) -> dict:
    """One case: a fixed configuration plus the timestamps to run it at."""
    case = dict(rpm=0, sequence=engine.SEQ_CENTER_OUT, color_mode=0, theme_dim=False,
                full_rpm=6800, shift_rpm=0, shift_hz=8, shift_color=(255, 0, 0),
                enabled=True, can=True, error=False, demo=None, self_test=0,
                self_test_start=0, ramp=engine.DEFAULT_RAMP)
    case.update(kwargs)
    case["nows"] = list(nows) if nows is not None else [kwargs.get("now", 0)]
    case.pop("now", None)
    return case


def build_cases(count: int, rng: random.Random) -> List[dict]:
    cases: List[dict] = []
    ramps = _ramp_variants()

    for case in cases:
        pass

    # Hand-picked edges: every fill pattern, both color modes, dim on and off, across the
    # rpm range including the frame boundaries.
    for sequence in (engine.SEQ_CENTER_OUT, engine.SEQ_LEFT_TO_RIGHT,
                     engine.SEQ_RIGHT_TO_LEFT, engine.SEQ_CENTER_IN):
        for mode in (0, 1):
            for dim in (False, True):
                for rpm in (0, 1, 10, 679, 680, 760, 3400, 6799, 6800, 8000):
                    cases.append(_case(rpm=rpm, sequence=sequence, color_mode=mode,
                                       theme_dim=dim))

    # Different "full at" scales, including one below the test rpm.
    for full in (2000, 3500, 4200, 8000):
        for rpm in (0, 500, 1000, 2000, 3000, 4199, 4200, 6800):
            cases.append(_case(rpm=rpm, full_rpm=full))

    # Every ramp variant, at several rpms and both modes.
    for ramp in ramps:
        for mode in (0, 1):
            for rpm in (0, 400, 1200, 2000, 2600, 3400, 5000, 7000, 9000):
                cases.append(_case(rpm=rpm, color_mode=mode, ramp=ramp,
                                   full_rpm=ramp[-1][0] if ramp[-1][0] > 0 else 6800))

    # Shift light: the trigger boundary and a full blink cycle, sampled over time.
    for rpm in (6299, 6300, 6301):
        for hz in (2, 8, 15):
            cases.append(_case(rpm=rpm, shift_rpm=6300, shift_hz=hz,
                               shift_color=(0, 255, 0),
                               nows=[0, 15, 31, 62, 63, 124, 125, 200]))

    # Time-driven patterns: the scanner walks the strip, the shift light blinks, the
    # self-test sweeps, and an unchanged bar must stay put through the repaint gate.
    cases.append(_case(error=True, rpm=5000, nows=list(range(0, 400, 17))))
    cases.append(_case(rpm=6500, shift_rpm=6300, nows=list(range(0, 200, 15))))
    cases.append(_case(rpm=3400, nows=[0, 33, 66, 99, 132]))
    cases.append(_case(rpm=0, nows=[0, 500, 999, 1000, 1499, 1500]))
    cases.append(_case(self_test=engine.SELF_TEST_SWEEP, rpm=5000, self_test_start=1000,
                       nows=[1000, 1500, 2000, 2500, 3000, 4000, 4999, 5001]))
    cases.append(_case(self_test=engine.SELF_TEST_IDENTIFY, rpm=5000,
                       self_test_start=1000,
                       nows=[1000, 1125, 1250, 3999, 4000, 4001]))
    cases.append(_case(can=False, rpm=5000, nows=[0, 400, 500, 999, 1000, 1400]))
    cases.append(_case(enabled=False, rpm=5000, nows=[0, 500, 1000]))

    # The remaining single-state cases.
    for now in (0, 100, 500, 999, 1000, 1500, 3000):
        cases.append(_case(enabled=False, rpm=5000, nows=[now]))
        cases.append(_case(can=False, rpm=5000, nows=[now]))
        cases.append(_case(error=True, rpm=5000, nows=[now]))
        # DEMO outranks both fault patterns, which is the only reason it is usable on a
        # bench: nothing here should show the offline or scanner pattern.
        cases.append(_case(can=False, rpm=0, demo=3000, nows=[now]))
        cases.append(_case(error=True, rpm=0, demo=3000, nows=[now]))
        cases.append(_case(rpm=0, demo=0, nows=[now]))
        cases.append(_case(rpm=0, demo=6800, shift_rpm=6300,
                           nows=[0, 31, 63, 94, 125]))
        cases.append(_case(self_test=engine.SELF_TEST_SWEEP, rpm=5000, nows=[now]))
        cases.append(_case(self_test=engine.SELF_TEST_IDENTIFY, rpm=5000, nows=[now]))

    # Random sweep over everything, with a random frame count so short animations are
    # covered as well as single frames.
    for _ in range(count):
        start = rng.randrange(0, 4000)
        length = rng.choice([1, 1, 2, 4, 8])
        step = rng.choice([8, 15, 33, 100])
        cases.append(_case(
            rpm=rng.choice([rng.randrange(0, 9000), rng.randrange(0, 200), 0, 6800]),
            sequence=rng.choice([1, 2, 3, 4]),
            color_mode=rng.choice([0, 1]),
            theme_dim=rng.choice([False, True]),
            full_rpm=rng.choice([2000, 3400, 5000, 6800, 8000]),
            shift_rpm=rng.choice([0, 0, 4000, 6300, 7000]),
            shift_hz=rng.choice([2, 5, 8, 15]),
            shift_color=rng.choice([(255, 0, 0), (0, 255, 0), (1, 2, 3)]),
            enabled=rng.random() > 0.1,
            can=rng.random() > 0.1,
            error=rng.random() > 0.85,
            self_test=rng.choice([0, 0, 0, engine.SELF_TEST_SWEEP,
                                  engine.SELF_TEST_IDENTIFY]),
            self_test_start=start,
            ramp=rng.choice(ramps),
            nows=[start + i * step for i in range(length)]))
    return cases


def run_cpp(exe: str, cases: List[dict], led_count: int) -> List[List[List[str]]]:
    """Every frame of every case, as the firmware renders it."""
    lines = []
    for case in cases:
        lines.append(" ".join(str(int(x)) for x in (
            case["rpm"], case["sequence"], case["color_mode"], int(case["theme_dim"]),
            case["full_rpm"], case["shift_rpm"], case["shift_hz"],
            case["shift_color"][0], case["shift_color"][1], case["shift_color"][2],
            int(case["enabled"]), int(case["can"]), int(case["error"]),
            int(case["demo"] is not None), case["demo"] or 0,
            case["self_test"], case["self_test_start"], len(case["nows"]))))
        ramp = case["ramp"]
        lines.append(" ".join([str(len(ramp))] + [
            "%d %d %d %d" % (rpm, rgb[0], rgb[1], rgb[2]) for rpm, rgb in ramp]))
        lines.append(" ".join(str(int(now)) for now in case["nows"]))
    stdin = "\n".join(lines) + "\n"
    result = subprocess.run([exe], input=stdin, capture_output=True, text=True,
                            timeout=300)
    if result.returncode != 0:
        raise SystemExit("harness exited %d: %s" % (result.returncode, result.stderr))
    flat = [line.split() for line in result.stdout.splitlines() if line.strip()]

    frames: List[List[List[str]]] = []
    cursor = 0
    for case in cases:
        block = flat[cursor:cursor + len(case["nows"])]
        if len(block) != len(case["nows"]):
            raise SystemExit("short output: expected %d frames, got %d"
                             % (len(case["nows"]), len(block)))
        frames.append(block)
        cursor += len(block)
    if cursor != len(flat):
        raise SystemExit("harness produced %d extra frames" % (len(flat) - cursor))
    return frames


def run_python(cases: List[dict], led_count: int) -> List[List[List[str]]]:
    """The same frames from the port, driven the same way."""
    out: List[List[List[str]]] = []
    for case in cases:
        cfg = LedConfig(led_count=led_count, sequence=case["sequence"],
                        color_mode=case["color_mode"], full_rpm=case["full_rpm"],
                        theme_dim=case["theme_dim"], enabled=case["enabled"],
                        brightness=255, shift_rpm=case["shift_rpm"],
                        shift_hz=case["shift_hz"], shift_color=case["shift_color"],
                        ramp=case["ramp"])
        elf = LedEngine(cfg=cfg, can_initialized=case["can"],
                        error_mode=case["error"], rpm=case["rpm"],
                        demo_rpm=case["demo"])
        # Set the bench-pattern state directly, exactly as the harness sets the globals:
        # `start_self_test` would also stamp the start time from the call.
        elf.self_test_mode = case["self_test"]
        elf.self_test_started = case["self_test_start"]
        out.append([[engine.hex_of(rgb) for rgb in elf.frame(int(now))]
                    for now in case["nows"]])
    return out


def _mutation_caught(cases: List[dict], cpp_frames, led_count: int) -> bool:
    """Perturb the port and confirm the comparison notices.

    A parity check that passes because both sides are inert (all zeros, say) is worse than
    no check: it manufactures confidence. So this changes one thing in the port at a time
    and requires the frames to diverge. Both mutations are on the frame path - mutating
    something the comparison does not exercise (the rpm filter, say) proves nothing.
    """
    caught = 0

    original_dim = engine.DIM_SCALE
    try:
        engine.DIM_SCALE = original_dim - 1
        if run_python(cases, led_count) != cpp_frames:
            caught += 1
    finally:
        engine.DIM_SCALE = original_dim

    # One step on the interpolated colour: the kind of off-by-one a hand-written port makes
    # when it rounds instead of truncating, or the other way round.
    original_ramp = engine.ramp_color_at_rpm
    try:
        def shifted(rpm, ramp):
            r, g, b = original_ramp(rpm, ramp)
            return ((r + 1) & 0xFF, g, b)
        engine.ramp_color_at_rpm = shifted
        if run_python(cases, led_count) != cpp_frames:
            caught += 1
    finally:
        engine.ramp_color_at_rpm = original_ramp

    return caught == 2


RPM_HARNESS = r"""
// Generated by parity_check.py from arduino/src/main.cpp. Do not edit.
#include <stdint.h>
#include <stdio.h>
#include <string.h>

#define CAN_OK 0
#define CAN_MSGAVAIL 1
#define CAN_MAX_FRAMES @FRAMES@
#define MAZDA_RPM_CAN_ID 0x201
#define RPM_SNAP_DELTA @SNAP@
#define RPM_ALPHA_RISING @RISING@f
#define RPM_ALPHA_FALLING @FALLING@f

// ---- Arduino / MCP2515 stubs ----------------------------------------------
unsigned long millis_value = 0;
static unsigned long millis() { return millis_value; }

static uint8_t  frame_data[8];
static uint8_t  frame_len = 8;
static int      frames_left = 0;          // frames the stub will hand out

struct FakeCan {
    int checkReceive() { return frames_left > 0 ? CAN_MSGAVAIL : 0; }
    int readMsgBuf(unsigned long* id, uint8_t* len, uint8_t* buf) {
        if (frames_left <= 0) return 1;
        frames_left--;
        *id = MAZDA_RPM_CAN_ID;
        *len = frame_len;
        memcpy(buf, frame_data, 8);
        return CAN_OK;
    }
};
FakeCan canBus;

// ---- globals readCANMessages() touches -------------------------------------
unsigned long lastCANData = 0;
unsigned long lastEngineFrame = 0;
bool errorMode = false;
bool displayErrorMode = false;
unsigned long lastCanIdSeen = 0;
uint16_t frameCount = 0;
float smoothedRPM = 0.0f;
uint16_t currentRPM = 0;
volatile uint8_t g_canDataReceived = 0;
// Sample history that readCANMessages() now maintains for the predictor.
uint16_t rpmLast = 0;
uint16_t rpmPrev = 0;
unsigned long rpmLastMs = 0;
unsigned long rpmPrevMs = 0;
bool rpmHaveHistory = false;
"""


def build_rpm_harness(source: str) -> str:
    return (RPM_HARNESS
            .replace("@SNAP@", extract_define(source, "RPM_SNAP_DELTA"))
            .replace("@FRAMES@", extract_define(source, "CAN_MAX_FRAMES").split()[0])
            .replace("@RISING@", extract_define(source, "RPM_ALPHA_RISING").rstrip("f"))
            .replace("@FALLING@", extract_define(source, "RPM_ALPHA_FALLING").rstrip("f"))
            + "\n// ---- readCANMessages (verbatim from main.cpp) ----\n"
            + extract_function(source, "readCANMessages")
            + r"""

int main(void) {
    // One line per reading: the raw 16-bit field, of which bytes 0-1 are rpm * 4.
    long raw;
    while (scanf("%ld", &raw) == 1) {
        uint16_t value = (uint16_t)raw;
        frame_data[0] = (uint8_t)(value >> 8);
        frame_data[1] = (uint8_t)(value & 0xFF);
        frames_left = 1;
        readCANMessages();
        printf("%u\n", (unsigned)currentRPM);
    }
    return 0;
}
""")


def check_rpm_filter(work: str, compiler: str, source: str) -> List[str]:
    """The 0x201 decode and the smoothing filter, against the compiled original."""
    path = os.path.join(work, "verify_rpm.cpp")
    with open(path, "w", encoding="utf-8") as handle:
        handle.write(build_rpm_harness(source))
    exe = _compile(work, compiler, "verify_rpm.cpp", "verify_rpm")

    # A drive-ish sequence: idle, a climb, a snap, a slow fall, another climb.
    readings = ([800] * 3 + [900, 1100, 1600, 2600, 3600, 4200]
                + [4200, 3000, 2600, 2500, 2450, 2400, 2350]
                + [2380, 2400, 3500, 6000, 6800, 6800, 1000, 950])
    # The firmware reads `rawRPM >> 2`, so the wire value is rpm * 4.
    stdin = "\n".join(str(min(0xFFFF, rpm * 4)) for rpm in readings) + "\n"
    result = subprocess.run([exe], input=stdin, capture_output=True, text=True,
                            timeout=120)
    cpp = [int(line) for line in result.stdout.split()]

    problems = []
    smoothed = 0.0
    for reading, expected in zip(readings, cpp):
        smoothed = engine.smooth_rpm(smoothed, float(reading))
        got = int(smoothed + 0.5)
        if got != expected:
            problems.append("rpm %d: C++ %d, python %d" % (reading, expected, got))
    if len(cpp) != len(readings):
        problems.append("harness returned %d readings for %d inputs"
                        % (len(cpp), len(readings)))
    return problems


# -- brightness, checked separately because it is not part of updateLEDs -------
BRIGHTNESS_PROBE = r"""
// Generated: the library's setBrightness()/show() scaling, as used by the firmware.
#include <stdint.h>
#include <stdio.h>
int main(void) {
    int b, v;
    while (scanf("%d %d", &b, &v) == 2) {
        uint8_t brightness = (uint8_t)(b + 1);      // Adafruit_NeoPixel::setBrightness
        uint8_t out = (uint8_t)v;
        if (brightness) {                            // `if (brightness)` in show()
            out = (uint8_t)((out * brightness) >> 8);
        }
        printf("%d\n", out);
    }
    return 0;
}
"""


def _neopixel_cpp() -> Optional[str]:
    """Path to the installed Adafruit_NeoPixel implementation, if there is one."""
    root = os.path.join(REPO, ".pio", "libdeps")
    if not os.path.isdir(root):
        return None
    for env in os.listdir(root):
        for directory in (os.path.join(root, env, "Adafruit NeoPixel"),
                          os.path.join(root, env, "Adafruit_NeoPixel")):
            path = os.path.join(directory, "Adafruit_NeoPixel.cpp")
            if os.path.exists(path):
                return path
    return None


def library_scale_problems() -> List[str]:
    """Check the brightness scale we emulate is the one in the installed library.

    `BRIGHTNESS_PROBE` is a transcription of two lines of Adafruit_NeoPixel. A transcription
    is exactly what this whole exercise distrusts, so verify it against the real source:
    `setBrightness` must store `b + 1`, and `show()` must scale `(v * brightness) >> 8`
    behind an `if (brightness)` guard (which is why 255 means *no* scaling).
    """
    path = _neopixel_cpp()
    if not path:
        return []

    problems = []
    with open(path, encoding="utf-8", errors="replace") as handle:
        text = handle.read()
    if "uint8_t newBrightness = b + 1;" not in text:
        problems.append("library no longer stores b + 1 in setBrightness() - the "
                        "brightness emulation in apply_brightness() is stale")
    if "(r * brightness) >> 8" not in text:
        problems.append("library no longer scales (v * brightness) >> 8 - the brightness "
                        "emulation in apply_brightness() is stale")
    if "if (brightness) {" not in text:
        problems.append("library no longer gates the scale on `if (brightness)` - the "
                        "255-means-no-scaling behavior may have changed")
    return problems


def _build_probe(work: str, compiler: str, source: str, name: str) -> Optional[str]:
    """Compile one probe in `work` and return its exe path."""
    return _compile(work, compiler, source, name)


def check_brightness(work: str, compiler: str) -> List[str]:
    with open(os.path.join(work, "brightness.cpp"), "w", encoding="utf-8") as handle:
        handle.write(BRIGHTNESS_PROBE)
    exe = _build_probe(work, compiler, "brightness.cpp", "brightness")

    pairs = [(b, v) for b in range(0, 256, 7) for v in (0, 1, 2, 127, 128, 200, 254, 255)]
    stdin = "\n".join("%d %d" % pair for pair in pairs) + "\n"
    result = subprocess.run([exe], input=stdin, capture_output=True, text=True, timeout=120)
    cpp = [int(line) for line in result.stdout.split()]

    problems = []
    for (level, value), expected in zip(pairs, cpp):
        got = engine.apply_brightness([(value, value, value)], level)[0][0]
        if got != expected:
            problems.append("brightness %d on %d: C++ %d, python %d"
                            % (level, value, expected, got))
    return problems


PREDICT_PROBE = r"""
#include <stdint.h>
#include <stdio.h>

#define RPM_EXTRAPOLATE_MS @EXTRAPOLATE@
#define RPM_MAX_SLOPE @MAXSLOPE@
#define RPM_MIN_SAMPLE_GAP @MINGAP@
#define RPM_MAX_SAMPLE_GAP @MAXGAP@
static uint16_t rpmFull = @FULL@;

@PREDICT_FN@

int main() {
    unsigned long now, last_ms, prev_ms;
    int last, prev, have;
    while (scanf("%lu %d %d %lu %lu %d", &now, &last, &prev, &last_ms, &prev_ms, &have) == 6) {
        printf("%d\n", (int)predictRPM(now, (uint16_t)last, (uint16_t)prev,
                                       last_ms, prev_ms, have != 0));
    }
    return 0;
}
"""


def check_prediction(work: str, compiler: str, source: str) -> List[str]:
    """The bar's sub-frame prediction: firmware against port, guards included.

    All the interesting behaviour is in the guards - stale sample, gap too short to trust,
    slope clamped - so the grid straddles every boundary rather than sweeping the happy
    path. A prediction that runs away is worse than no prediction: it draws an rpm the
    engine never had.
    """
    extrapolate = extract_define(source, "RPM_EXTRAPOLATE_MS").split()[0]
    max_slope = extract_define(source, "RPM_MAX_SLOPE").split()[0]
    min_gap = extract_define(source, "RPM_MIN_SAMPLE_GAP").split()[0]
    max_gap = extract_define(source, "RPM_MAX_SAMPLE_GAP").split()[0]
    full = 6800
    problems = []
    if (engine.EXTRAPOLATE_MS != int(extrapolate)
            or engine.MAX_SLOPE != int(max_slope)
            or engine.MIN_SAMPLE_GAP != int(min_gap)
            or engine.MAX_SAMPLE_GAP != int(max_gap)):
        problems.append("prediction constants: firmware says %s/%s/%s/%s, port says %s/%s/"
                        "%s/%s (horizon, slope, min gap, max gap)"
                        % (extrapolate, max_slope, min_gap, max_gap,
                           engine.EXTRAPOLATE_MS, engine.MAX_SLOPE,
                           engine.MIN_SAMPLE_GAP, engine.MAX_SAMPLE_GAP))

    body = (PREDICT_PROBE
            .replace("@EXTRAPOLATE@", extrapolate)
            .replace("@MAXSLOPE@", max_slope)
            .replace("@MINGAP@", min_gap)
            .replace("@MAXGAP@", max_gap)
            .replace("@FULL@", str(full))
            .replace("@PREDICT_FN@", extract_function(source, "predictRPM")))
    with open(os.path.join(work, "predict.cpp"), "w", encoding="utf-8") as handle:
        handle.write(body)
    exe = _build_probe(work, compiler, "predict.cpp", "predict")

    rows = []
    for now_gap in (0, 1, 3, 11, 12, 13, 40):
        for last, prev in ((3000, 3000), (3000, 2800), (3000, 3600), (900, 100),
                           (6800, 0), (50, 50), (1, 4000)):
            for prev_gap in (0, 3, 4, 20, 60, 100, 101, 150):
                for have in (0, 1):
                    last_ms = 10000
                    rows.append((last_ms + now_gap, last, prev, last_ms,
                                 last_ms - prev_gap, have))

    stdin = "\n".join("%d %d %d %d %d %d" % row for row in rows) + "\n"
    result = subprocess.run([exe], input=stdin, capture_output=True, text=True, timeout=120)
    cpp = [int(line) for line in result.stdout.split()]
    if len(cpp) != len(rows):
        return problems + ["predict probe returned %d rows for %d inputs"
                           % (len(cpp), len(rows))]

    for row, expected in zip(rows, cpp):
        now, last, prev, last_ms, prev_ms, have = row
        got = engine.predict_rpm(now, last, prev, last_ms, prev_ms, bool(have), full)
        if got != expected:
            problems.append("predict(now+%d last=%d prev=%d prev_gap=%d hist=%d): "
                            "C++ %d, python %d"
                            % (now - last_ms, last, prev, last_ms - prev_ms, have,
                               expected, got))
    print("prediction cases:", len(rows))
    return problems


# -- main ---------------------------------------------------------------------

def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--cases", type=int, default=120,
                        help="random cases on top of the fixed ones (default 120)")
    parser.add_argument("--led-count", type=int, default=engine.DEFAULT_LED_COUNT)
    parser.add_argument("--keep", action="store_true", help="keep the generated files")
    parser.add_argument("--mutate-check", action="store_true",
                        help="also prove a deliberate change to the port is detected")
    args = parser.parse_args()

    if not os.path.exists(MAIN_CPP):
        print("SKIPPED: %s not found" % MAIN_CPP)
        return 0

    compiler = find_compiler()
    if compiler is None:
        print("SKIPPED: no C++ compiler found (MSVC, g++ on PATH, or set MX5_CL)")
        return 0
    print("compiler:", compiler)
    library = _neopixel_cpp()
    print("neopixel library:", library if library else "not installed (scale check skipped)")

    work = tempfile.mkdtemp(prefix="mx5-led-parity-")
    try:
        source = _read_main()
        # 20 is the strip that exists; odd counts are where the mirrored geometry gets
        # interesting (the center pixel has no partner), so check those too.
        led_counts = sorted({args.led_count, 20, 21, 5})
        total_cases = 0
        total_frames = 0
        all_mismatches = []

        for led_count in led_counts:
            harness = build_harness(source, led_count)
            with open(os.path.join(work, "verify.cpp"), "w", encoding="utf-8") as handle:
                handle.write(harness)
            exe = compile_harness(work, compiler)

            # A fresh random stream per width, so the cases are reproducible but not the
            # same shape at every size.
            rng = random.Random(20261030 + led_count)
            cases = build_cases(args.cases, rng)
            cpp_frames = run_cpp(exe, cases, led_count)
            py_frames = run_python(cases, led_count)

            for index, (case, cpp, py) in enumerate(zip(cases, cpp_frames, py_frames)):
                if cpp == py:
                    continue
                differing = [(f, i) for f in range(min(len(cpp), len(py)))
                             for i in range(len(cpp[f]))
                             if cpp[f][i] != py[f][i]]
                all_mismatches.append((led_count, index, case, cpp, py, differing))

            total_cases += len(cases)
            total_frames += sum(len(case["nows"]) for case in cases)

            if args.mutate_check and not _mutation_caught(cases, cpp_frames, led_count):
                print("BUT the check would not notice a difference at %d LEDs - it is not "
                      "proving anything" % led_count)
                return 1

        brightness_problems = check_brightness(work, compiler) + library_scale_problems()
        rpm_problems = check_rpm_filter(work, compiler, source)
        predict_problems = check_prediction(work, compiler, source)

        print("LED counts: %s   cases: %d   frames compared: %d"
              % (", ".join(str(c) for c in led_counts), total_cases, total_frames))
        if (not all_mismatches and not brightness_problems and not rpm_problems
                and not predict_problems):
            print("PARITY OK - every pixel of every frame matches the firmware")
            if args.mutate_check:
                print("sensitivity confirmed: a deliberate change is detected at every width")
            return 0

        for problem in brightness_problems:
            print("MISMATCH (brightness)", problem)
        for problem in rpm_problems:
            print("MISMATCH (rpm filter)", problem)
        for problem in predict_problems:
            print("MISMATCH (prediction)", problem)
        for led_count, index, case, cpp, py, differing in all_mismatches[:8]:
            print("\nMISMATCH at %d LEDs, case %d: rpm=%s seq=%s mode=%s dim=%s full=%s "
                  "shift=%s@%sHz enabled=%s can=%s error=%s selftest=%s@%s ramp=%s"
                  % (led_count, index, case["rpm"], case["sequence"], case["color_mode"],
                     case["theme_dim"], case["full_rpm"], case["shift_rpm"],
                     case["shift_hz"], case["enabled"], case["can"], case["error"],
                     case["self_test"], case["self_test_start"],
                     [rpm for rpm, _ in case["ramp"]]))
            for frame_index, pixel in differing[:6]:
                print("   frame %2d pixel %2d  C++ %s  python %s"
                      % (frame_index, pixel, cpp[frame_index][pixel],
                         py[frame_index][pixel]))
        print("\n%d case(s) differ" % len(all_mismatches))
        return 1
    finally:
        if args.keep:
            print("generated files kept in", work)
        else:
            shutil.rmtree(work, ignore_errors=True)


if __name__ == "__main__":
    sys.exit(main())
