#!/usr/bin/env python3
"""Fix degree-symbol encoding in ui_core.cpp to match the original firmware."""
from pathlib import Path

P = Path(r"c:\Users\tanne\Documents\Github\MX5-Telemetry\display\src\ui_core\ui_core.cpp")
text = P.read_text(encoding="utf-8")

repls = [
    ('"2.5\\xB0"', '"2.5\\xF8"'),
    ('"5\\xB0"', '"5\\xF8"'),
    ('"10\\xB0"', '"10\\xF8"'),
    ('"Pitch:%+.1f\\xB0"', '"Pitch:%+.1f\\xF8"'),
    ('"Roll:%+.1f\\xB0"', '"Roll:%+.1f\\xF8"'),
    ('"%.0f\\xB0""F"', '"%.0f\u00b0F"'),
]

for old, new in repls:
    n = text.count(old)
    if n == 0:
        print(f"[WARN] not found: {old!r}")
    text = text.replace(old, new)
    print(f"[OK] {n}x {old!r} -> {new!r}")

assert "\\xB0" not in text, "leftover \\xB0 remains"
P.write_text(text, encoding="utf-8")
print("wrote", P)
