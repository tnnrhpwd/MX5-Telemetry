#!/usr/bin/env python3
"""Generate the mimic harness's design tokens from the Android sources.

The harness renders the car app in a browser at 800x480 so the design can be iterated and
screenshotted without a phone. The risk with any such replica is drift: hand-copying twelve
schemes and two modes into CSS guarantees that a later palette change lands in one place
and not the other, and then the harness is quietly lying.

So nothing is copied. The seeds, the per-mode surfaces, the fixed alert colours and the
blend fractions are all read out of Palette.java and Ui.java, and the derived colours are
computed by replicating Java's mix/lift/sink/alpha in JS at runtime. Change a seed in
Palette.java, re-run this, and the harness follows.

What this cannot extract is layout, so the DOM in mimic.js is written by hand to mirror the
Java view code. That is the one place the two can diverge, and it is why the Java app stays
the source of truth and the device stays the final check.

    python extract_tokens.py            # writes tokens.js next to index.html
"""

import json
import os
import re
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
JAVA_DIR = os.path.abspath(os.path.join(HERE, '..', 'mx5-remote', 'src', 'main', 'java',
                                        'com', 'mx5', 'remote'))

PALETTE = os.path.join(JAVA_DIR, 'Palette.java')
UI = os.path.join(JAVA_DIR, 'Ui.java')

OUT = os.path.join(HERE, 'tokens.js')


def read(path):
    with open(path, 'r', encoding='utf-8') as f:
        return f.read()


def parse_schemes(src):
    """The SCHEMES array: id, display name, and the two seed hues."""
    block = re.search(r'SCHEMES\s*=\s*\{(.*?)\n\s*\};', src, re.S)
    if not block:
        raise SystemExit("Could not find SCHEMES in Palette.java")
    schemes = []
    for m in re.finditer(
            r'new\s+Scheme\(\s*"([^"]+)"\s*,\s*"([^"]+)"\s*,\s*(0x[0-9A-Fa-f]+)\s*,\s*(0x[0-9A-Fa-f]+)\s*\)',
            block.group(1)):
        schemes.append({
            'id': m.group(1),
            'name': m.group(2),
            'a': m.group(3),
            'b': m.group(4),
        })
    if not schemes:
        raise SystemExit("SCHEMES parsed to nothing")
    return schemes


def parse_modes(src):
    """The dark and light surface colours, and the colours that do not vary by mode."""
    dark_block = re.search(r'if\s*\(dark\)\s*\{(.*?)\}\s*else\s*\{', src, re.S)
    light_block = re.search(r'\}\s*else\s*\{(.*?)\n\s*\}', src, re.S)
    if not dark_block or not light_block:
        raise SystemExit("Could not split the dark and light colour blocks")

    def colours(text):
        return {k: v for k, v in re.findall(r'(\w+)\s*=\s*(0x[0-9A-Fa-f]{8})\s*;', text)}

    dark = colours(dark_block.group(1))
    light = colours(light_block.group(1))
    if not dark or not light:
        raise SystemExit("No colours found in one of the mode blocks")

    fixed = {}
    for name in ('alert', 'good', 'bad', 'warn'):
        m = re.search(r'\b%s\s*=\s*(0x[0-9A-Fa-f]{8})\s*;' % name, src)
        if m:
            fixed[name] = m.group(1)
    return dark, light, fixed


def parse_fractions(src):
    """The blend amounts, so the harness does not hardcode a second copy of them."""
    out = {}

    m = re.search(r'float\s+amt\s*=\s*([\d.]+)f', src)
    out['seedAmount'] = float(m.group(1)) if m else 0.18

    def mode_pair(pattern, key):
        m = re.search(pattern, src, re.S)
        if not m:
            raise SystemExit("Could not find the fraction for %s" % key)
        out[key] = [float(m.group(1)), float(m.group(2))]

    mode_pair(r'panelHead\s*=\s*mix\(panel,\s*accent,\s*dark\s*\?\s*([\d.]+)f\s*:\s*([\d.]+)f\)',
              'panelHead')
    mode_pair(r'accentWash\(\)\s*\{\s*return\s+alpha\(accent,\s*dark\s*\?\s*([\d.]+)f\s*:\s*([\d.]+)f\)',
              'wash')
    mode_pair(r'washOf\(int c\)\s*\{\s*return\s+alpha\(c,\s*dark\s*\?\s*([\d.]+)f\s*:\s*([\d.]+)f\)',
              'wash')
    mode_pair(r'pageGlow\(\)\s*\{\s*return\s+mix\(page,\s*accent,\s*dark\s*\?\s*([\d.]+)f\s*:\s*([\d.]+)f\)',
              'pageGlow')
    return out


def parse_ui(src):
    """The type scale and spacing ramp."""
    types = {k: float(v) for k, v in
             re.findall(r'public\s+static\s+final\s+float\s+(\w+)\s*=\s*([\d.]+)f\s*;', src)}
    spaces = {k: int(v) for k, v in
              re.findall(r'public\s+static\s+final\s+int\s+(S\d)\s*=\s*(\d+)\s*;', src)}
    if 'TYPE_DISPLAY' not in types:
        raise SystemExit("Could not read the type scale from Ui.java")
    return types, spaces


def main():
    palette_src = read(PALETTE)
    ui_src = read(UI)

    schemes = parse_schemes(palette_src)
    dark, light, fixed = parse_modes(palette_src)
    fractions = parse_fractions(palette_src)
    types, spaces = parse_ui(ui_src)

    tokens = {
        'schemes': schemes,
        'modes': {'dark': dark, 'light': light},
        'fixed': fixed,
        'fractions': fractions,
        'type': types,
        'space': spaces,
        'source': {
            'palette': os.path.relpath(PALETTE, HERE).replace('\\', '/'),
            'ui': os.path.relpath(UI, HERE).replace('\\', '/'),
        },
    }

    body = json.dumps(tokens, indent=2, sort_keys=True)
    with open(OUT, 'w', encoding='utf-8') as f:
        f.write("// Generated by extract_tokens.py from the Android sources. Do not edit.\n")
        f.write("// Source: %s, %s\n" % (tokens['source']['palette'], tokens['source']['ui']))
        f.write("window.MX5_TOKENS = ")
        f.write(body)
        f.write(";\n")

    print("wrote %s" % OUT)
    print("  %d schemes" % len(schemes))
    print("  dark keys:  %s" % ', '.join(sorted(dark)))
    print("  light keys: %s" % ', '.join(sorted(light)))
    print("  fixed:      %s" % ', '.join('%s=%s' % kv for kv in sorted(fixed.items())))
    print("  fractions:  %s" % json.dumps(fractions, sort_keys=True))
    print("  type:       %s" % ', '.join('%s=%s' % kv for kv in sorted(types.items())))
    print("  space:      %s" % ', '.join('%s=%s' % kv for kv in sorted(spaces.items())))
    return 0


if __name__ == '__main__':
    sys.exit(main())
