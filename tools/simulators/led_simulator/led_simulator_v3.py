#!/usr/bin/env python3
"""MX5 LED strip simulator - the same 20 pixels and the same ramp logic as the Nano.

This replaces the v1/v2 simulators, which drew a six-state program (white pepper, steady
green edges, orange stall pulse, red flashing gap) that no longer exists in the firmware.
The shipping strip has a runtime colour ramp the phone can replace, and every frame here
comes from `led_engine.py`, which is a line-by-line port of `arduino/src/main.cpp`.

The point of the tool is the one thing you cannot do on a bench with the engine off:
drag the RPM around and watch the bar, so the colour ramp, the fill pattern, the "full at"
scale and the shift point can be judged before they are flashed.

    python led_simulator_v3.py                  # 20 LEDs, defaults from the firmware
    python led_simulator_v3.py --leds 30        # if the strip was extended
    python led_simulator_v3.py --pi 192.168.42.100:5000
                                                # start from the car's live settings

Keys: Up/Down 100 rpm, PageUp/PageDown 500 rpm, Home/End 0 and full, Space sweeps,
S sequences, M colour mode, E enable, T self test, I identify, Esc quits.
"""

from __future__ import annotations

import argparse
import os
import sys
import time
import tkinter as tk
from tkinter import colorchooser, messagebox
from typing import List, Optional, Tuple

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

import led_engine as engine  # noqa: E402
from led_engine import (  # noqa: E402
    SEQ_CENTER_IN, SEQ_CENTER_OUT, SEQ_LEFT_TO_RIGHT, SEQ_RIGHT_TO_LEFT,
    SELF_TEST_IDENTIFY, SELF_TEST_SWEEP, RGB, LedConfig, LedEngine, SEQUENCE_NAMES,
)

# -- look ---------------------------------------------------------------------

BG = "#0d0d0f"
PANEL = "#17171a"
CARD = "#202024"
EDGE = "#2c2c32"
TEXT = "#f4f7fd"
DIM = "#9ba1ab"
ACCENT = "#00c1c1"
PRIMARY = "#ff379b"
GOOD = "#22c55e"
WARN = "#f59e0b"
BAD = "#ef4444"

LED_OFF = "#151518"
LED_RIM = "#26262b"

TICK_MS = 33          # the Nano repaints at 100 Hz; 30 fps is plenty for a person
PALETTE = ["0a84ff", "00c1c1", "32d782", "ffd23c", "ff8000", "ef4444",
           "b44bff", "ffffff", "0000ff", "808080"]


def _hex(rgb: RGB) -> str:
    return "#%02x%02x%02x" % (rgb[0], rgb[1], rgb[2])


class StripView(tk.Canvas):
    """The physical strip, drawn in index order: 0 at the left, the last at the right."""

    def __init__(self, master, led_count: int):
        super().__init__(master, bg=BG, highlightthickness=0, height=150)
        self.led_count = led_count
        self.cells: List[int] = []
        self.labels: List[int] = []
        self.ranks: List[int] = []
        self.bind("<Configure>", lambda _e: self._layout())
        self._layout()

    def set_count(self, led_count: int) -> None:
        if led_count == self.led_count:
            return
        self.led_count = led_count
        self._layout()

    def _layout(self) -> None:
        self.delete("all")
        self.cells, self.labels, self.ranks = [], [], []
        width = max(self.winfo_width(), 400)
        gap = max(2.0, min(6.0, width / (self.led_count * 8.0)))
        cell = (width - 24 - gap * (self.led_count - 1)) / self.led_count
        top, height = 14.0, 62.0
        for index in range(self.led_count):
            x = 12 + index * (cell + gap)
            self.cells.append(self.create_rectangle(
                x, top, x + cell, top + height, fill=LED_OFF, outline=LED_RIM, width=1))
            self.labels.append(self.create_text(
                x + cell / 2, top + height + 12, text=str(index),
                fill=DIM, font=("Segoe UI", 7)))
            self.ranks.append(self.create_text(
                x + cell / 2, top + height + 24, text="", fill="#4a4a55",
                font=("Segoe UI", 6)))
        self._cell_width = cell

    def show(self, frame: List[RGB], ranks: List[int]) -> None:
        if len(frame) != len(self.cells):
            self.set_count(len(frame))
            self._layout()
        for index, rgb in enumerate(frame):
            self.itemconfig(self.cells[index], fill=_hex(rgb) if any(rgb) else LED_OFF)
        # The rank tells you which way the fill is running, which is what the four
        # sequences actually change.
        for index, rank in enumerate(ranks):
            self.itemconfig(self.ranks[index], text=str(rank))


class RampLegend(tk.Canvas):
    """A picture of the ramp itself, with the stop rpms marked.

    The bar shows the colour the ramp returns at that rpm, evaluated the same way the
    strip does - so a mis-ordered stop or a colour that never gets reached is obvious
    without moving the RPM slider at all.
    """

    def __init__(self, master, cfg_getter):
        super().__init__(master, bg=BG, highlightthickness=0, height=54)
        self.cfg_getter = cfg_getter
        self.bind("<Configure>", lambda _e: self.redraw())

    def redraw(self) -> None:
        self.delete("all")
        cfg: LedConfig = self.cfg_getter()
        width = max(self.winfo_width(), 300)
        left, right, top, height = 12, width - 12, 8, 20
        steps = int(right - left)
        if steps <= 0:
            return
        for offset in range(0, steps, 2):
            rpm = int(cfg.full_rpm * offset / steps)
            colour = engine.ramp_color_at_rpm(rpm, cfg.ramp)
            self.create_rectangle(left + offset, top, left + offset + 2, top + height,
                                  fill=_hex(colour), outline="")
        self.create_rectangle(left, top, right, top + height, outline=EDGE)
        for rpm, _colour in cfg.ramp:
            x = left + (right - left) * (rpm / cfg.full_rpm if cfg.full_rpm else 0)
            self.create_line(x, top + height, x, top + height + 4, fill=DIM)
            self.create_text(x, top + height + 14, text=str(rpm), fill=DIM,
                             font=("Segoe UI", 6))
        if cfg.shift_rpm and cfg.full_rpm:
            x = left + (right - left) * min(1.0, cfg.shift_rpm / cfg.full_rpm)
            self.create_line(x, top - 3, x, top + height + 2, fill=BAD, dash=(3, 2))
            self.create_text(x, top - 8, text="shift %d" % cfg.shift_rpm, fill=BAD,
                             font=("Segoe UI", 7))


def _card(parent, title: str) -> tk.Frame:
    outer = tk.Frame(parent, bg=PANEL)
    tk.Label(outer, text=title.upper(), bg=PANEL, fg=DIM,
             font=("Segoe UI", 8, "bold")).pack(anchor="w", pady=(8, 2))
    inner = tk.Frame(outer, bg=CARD, padx=10, pady=8)
    inner.pack(fill="x")
    return outer, inner


class Section:
    """A titled block of controls inside the right-hand column."""

    def __init__(self, parent, title: str):
        self.outer, self.body = _card(parent, title)

    def pack(self, **kwargs):
        self.outer.pack(fill="x", padx=10, **kwargs)


class Slider(tk.Frame):
    """A label, a live value and a track you can drag.

    Deliberately not a `tk.Scale`: on Windows that widget paints its thumb in the widget
    background colour, so on a dark panel the thumb is invisible, and it fires its command
    for programmatic .set() as well as for real drags. A canvas gives the same control a
    filled track - which reads as "how much of the range is used" at a glance - and makes
    a drag unambiguous.
    """

    KNOB = 7

    def __init__(self, parent, label: str, low: int, high: int, value: int,
                 unit: str = "", step: int = 1, on_change=None, colour: str = ACCENT,
                 width: int = 240):
        super().__init__(parent, bg=CARD)
        self.low, self.high = low, high
        self.step = max(1, step)
        self.unit = unit
        self.colour = colour
        self.on_change = on_change
        self.value = self._snap(value)
        self.dragging = False

        row = tk.Frame(self, bg=CARD)
        row.pack(fill="x", pady=(4, 0))
        tk.Label(row, text=label, bg=CARD, fg=TEXT,
                 font=("Segoe UI", 9)).pack(side="left")
        self.value_label = tk.Label(row, text="", bg=CARD, fg=colour,
                                    font=("Segoe UI", 9, "bold"))
        self.value_label.pack(side="right")

        self.canvas = tk.Canvas(self, bg=CARD, highlightthickness=0, height=22,
                                cursor="hand2")
        self.canvas.pack(fill="x")
        self.canvas.bind("<Configure>", lambda _e: self._draw())
        self.canvas.bind("<Button-1>", self._press)
        self.canvas.bind("<B1-Motion>", self._motion)
        self.canvas.bind("<ButtonRelease-1>", self._release)
        self._render()

    # -- value ---------------------------------------------------------------

    def _snap(self, value: float) -> int:
        steps = round((value - self.low) / self.step)
        return int(max(self.low, min(self.high, self.low + steps * self.step)))

    def get(self) -> int:
        return self.value

    def set(self, value: int) -> None:
        self.value = self._snap(value)
        self._render()

    def _render(self) -> None:
        self.value_label.config(text="%d%s" % (self.value, self.unit))
        self._draw()

    # -- drawing -------------------------------------------------------------

    def _draw(self) -> None:
        self.canvas.delete("all")
        width = max(self.canvas.winfo_width(), 60)
        pad = self.KNOB + 2
        y = self.canvas.winfo_height() / 2 or 11
        span = max(1, self.high - self.low)
        fraction = (self.value - self.low) / span
        x = pad + (width - 2 * pad) * fraction

        self.canvas.create_line(pad, y, width - pad, y, fill="#2f2f36",
                                width=5, capstyle="round")
        if fraction > 0:
            self.canvas.create_line(pad, y, x, y, fill=self.colour,
                                    width=5, capstyle="round")
        knob = self.colour if (self.dragging or fraction > 0) else "#4a4a55"
        self.canvas.create_oval(x - self.KNOB, y - self.KNOB, x + self.KNOB, y + self.KNOB,
                                fill=knob, outline=BG, width=1)

    # -- dragging ------------------------------------------------------------

    def _value_at(self, x: int) -> int:
        width = max(self.canvas.winfo_width(), 60)
        pad = self.KNOB + 2
        fraction = (x - pad) / max(1, width - 2 * pad)
        return self._snap(self.low + fraction * (self.high - self.low))

    def _press(self, event) -> None:
        self.dragging = True
        self._apply(self._value_at(event.x))

    def _motion(self, event) -> None:
        if self.dragging:
            self._apply(self._value_at(event.x))

    def _release(self, _event) -> None:
        self.dragging = False
        self._render()

    def _apply(self, value: int) -> None:
        if value == self.value:
            self.dragging = True
            self._draw()
            return
        self.value = value
        self._render()
        if self.on_change:
            self.on_change(value)


class Chips(tk.Frame):
    """Mutually exclusive chips that carry their own value."""

    def __init__(self, parent, names: List[str], values: List[int], value: int,
                 on_pick, colour: str = ACCENT, columns: int = 2):
        super().__init__(parent, bg=CARD)
        self.names, self.values, self.on_pick = names, values, on_pick
        self.colour = colour
        self.buttons: List[tk.Label] = []
        for index, name in enumerate(names):
            label = tk.Label(self, text=name, bg=CARD, fg=TEXT, padx=8, pady=5,
                             font=("Segoe UI", 8), cursor="hand2")
            label.grid(row=index // columns, column=index % columns, sticky="ew", padx=1,
                       pady=1)
            label.bind("<Button-1>", lambda _e, v=values[index]: self._pick(v))
            self.buttons.append(label)
        for column in range(columns):
            self.grid_columnconfigure(column, weight=1)
        self.select(value)

    def _pick(self, value: int) -> None:
        self.select(value)
        self.on_pick(value)

    def select(self, value: int) -> None:
        for index, button in enumerate(self.buttons):
            on = self.values[index] == value
            button.config(bg=self.colour if on else "#2a2a30",
                          fg="#101014" if on else TEXT)


class Swatches(tk.Frame):
    """Ramp stops, each a colour button that opens a picker.

    There are always six buttons because the app's editor has six stops, but a ramp that
    arrived with fewer (or more) is shown honestly: `set()` only touches the swatches the
    ramp actually has, and the legend draws the real table.
    """

    def __init__(self, parent, colours: List[RGB], on_pick):
        super().__init__(parent, bg=CARD)
        self.on_pick = on_pick
        self.buttons: List[tk.Label] = []
        self.hexes: List[str] = []
        for index, rgb in enumerate(colours):
            label = tk.Label(self, text=str(index + 1), bg=_hex(rgb), fg="#101014",
                             width=3, pady=4, font=("Segoe UI", 8, "bold"),
                             cursor="hand2")
            label.grid(row=0, column=index, padx=1, sticky="ew")
            label.bind("<Button-1>", lambda _e, i=index: self._choose(i))
            self.grid_columnconfigure(index, weight=1)
            self.buttons.append(label)
            self.hexes.append(engine.hex_of(rgb))

    @property
    def colours(self) -> List[RGB]:
        """The six swatch colours, whatever the live ramp happens to contain."""
        return [engine.rgb_of_hex(value) for value in self.hexes]

    def _choose(self, index: int) -> None:
        initial = self.buttons[index].cget("bg")
        _rgb, chosen = colorchooser.askcolor(color=initial, parent=self,
                                             title="Ramp stop %d" % (index + 1))
        if not chosen:
            return
        value = engine.rgb_of_hex(chosen.lstrip("#"))
        self.buttons[index].config(bg=_hex(value))
        self.hexes[index] = engine.hex_of(value)
        self.on_pick(index, value)

    def set(self, colours: List[RGB]) -> None:
        """Show a ramp. Stops the ramp does not have keep their swatch, dimmed."""
        for index, button in enumerate(self.buttons):
            if index < len(colours):
                button.config(bg=_hex(colours[index]), fg="#101014")
                self.hexes[index] = engine.hex_of(colours[index])
            else:
                button.config(bg=CARD, fg=DIM)


class LedSimulator(tk.Tk):
    def __init__(self, led_count: int, pi: Optional[str], token: str):
        super().__init__()
        self.title("MX5 LED strip simulator")
        self.configure(bg=BG)
        self.geometry("1180x720")
        self.minsize(980, 640)

        self.pi_address = pi
        self.pi_token = token
        self.started = time.time()
        self.sweeping = False
        self.sweep_direction = 1
        self.sweep_speed = 900          # rpm per second
        self.last_tick = self.started
        # What the "engine" is reporting, before the firmware's filter. The filter is the
        # difference between a slider and a strip, so the target and the rendered value are
        # deliberately separate: with smoothing on, the bar chases this over a few frames
        # exactly as it does in the car.
        self.feed_target = 0

        self.engine = LedEngine(cfg=LedConfig(led_count=led_count), rpm=0)

        self._build()
        self._bind_keys()
        if pi:
            self.after(200, self.load_from_pi)
        self.after(TICK_MS, self._tick)

    # -- layout --------------------------------------------------------------

    def _build(self) -> None:
        header = tk.Frame(self, bg=BG)
        header.pack(fill="x", padx=14, pady=(10, 0))
        tk.Label(header, text="LED STRIP", bg=BG, fg=DIM,
                 font=("Segoe UI", 8, "bold")).pack(anchor="w")
        tk.Label(header, text="Simulator", bg=BG, fg=ACCENT,
                 font=("Segoe UI", 16, "bold")).pack(anchor="w")
        tk.Label(header,
                 text="Every frame is computed by led_engine.py, a port of "
                      "arduino/src/main.cpp - %d LEDs, firmware ramp defaults." %
                      self.engine.cfg.led_count,
                 bg=BG, fg=DIM, font=("Segoe UI", 9)).pack(anchor="w")

        body = tk.Frame(self, bg=BG)
        body.pack(fill="both", expand=True, padx=14, pady=8)

        left = tk.Frame(body, bg=BG)
        left.pack(side="left", fill="both", expand=True)

        self.strip = StripView(left, self.engine.cfg.led_count)
        self.strip.pack(fill="x", pady=(6, 2))

        self.legend = RampLegend(left, lambda: self.engine.cfg)
        self.legend.pack(fill="x", pady=(2, 8))

        self._build_rpm_card(left)
        self._build_readout(left)

        self.panel = tk.Frame(body, bg=BG, width=340)
        self.panel.pack(side="right", fill="y", padx=(14, 0))
        self.panel.pack_propagate(False)
        self._build_controls(self._scrollable(self.panel))

    def _scrollable(self, parent) -> tk.Frame:
        """A vertically scrolling column.

        The control surface is nine groups and will not fit a laptop window; without this
        the bottom of it is simply unreachable.
        """
        canvas = tk.Canvas(parent, bg=BG, highlightthickness=0)
        canvas.pack(side="left", fill="both", expand=True)
        bar = tk.Scrollbar(parent, orient="vertical", command=canvas.yview,
                           bg=PANEL, troughcolor=BG, bd=0, width=10)
        bar.pack(side="right", fill="y")
        canvas.configure(yscrollcommand=bar.set)

        content = tk.Frame(canvas, bg=BG)
        window = canvas.create_window((0, 0), window=content, anchor="nw")
        content.bind("<Configure>",
                     lambda _e: canvas.configure(scrollregion=canvas.bbox("all")))
        canvas.bind("<Configure>",
                    lambda e: canvas.itemconfigure(window, width=e.width))
        # Only while the pointer is over the column: a bind_all would also steal the wheel
        # from the per-pixel dump, which has its own scroll.
        canvas.bind("<Enter>", lambda _e: canvas.bind_all(
            "<MouseWheel>", lambda ev: canvas.yview_scroll(int(-ev.delta / 120), "units")))
        canvas.bind("<Leave>", lambda _e: canvas.unbind_all("<MouseWheel>"))
        return content

    def _build_rpm_card(self, parent) -> None:
        card = tk.Frame(parent, bg=CARD, padx=12, pady=8)
        card.pack(fill="x")

        top = tk.Frame(card, bg=CARD)
        top.pack(fill="x")
        tk.Label(top, text="RPM", bg=CARD, fg=DIM,
                 font=("Segoe UI", 8, "bold")).pack(side="left")
        self.rpm_label = tk.Label(top, text="0", bg=CARD, fg=TEXT,
                                  font=("Consolas", 26, "bold"))
        self.rpm_label.pack(side="left", padx=(10, 0))
        self.state_label = tk.Label(top, text="", bg=CARD, fg=DIM,
                                    font=("Segoe UI", 9))
        self.state_label.pack(side="right")

        self.rpm_control = Slider(card, "Engine speed", 0, 8000, 0, " rpm", step=10,
                                  on_change=self._on_rpm_drag, colour=ACCENT)
        self.rpm_control.pack(fill="x", pady=(2, 0))

        buttons = tk.Frame(card, bg=CARD)
        buttons.pack(fill="x", pady=(4, 0))
        for text, delta in (("-500", -500), ("-100", -100), ("-10", -10),
                            ("+10", 10), ("+100", 100), ("+500", 500)):
            tk.Button(buttons, text=text, bg="#2a2a30", fg=TEXT, bd=0, relief="flat",
                      font=("Segoe UI", 8), padx=8, pady=3, cursor="hand2",
                      command=lambda d=delta: self.nudge(d)).pack(side="left", padx=1)
        self.sweep_button = tk.Button(buttons, text="Sweep", bg="#2a2a30", fg=TEXT, bd=0,
                                      relief="flat", font=("Segoe UI", 8, "bold"),
                                      padx=10, pady=3, cursor="hand2",
                                      command=self.toggle_sweep)
        self.sweep_button.pack(side="right", padx=1)
        self.idle_button = tk.Button(buttons, text="Idle", bg="#2a2a30", fg=TEXT, bd=0,
                                     relief="flat", font=("Segoe UI", 8), padx=8, pady=3,
                                     cursor="hand2", command=lambda: self.set_rpm(0))
        self.idle_button.pack(side="right", padx=1)

    def _build_readout(self, parent) -> None:
        card = tk.Frame(parent, bg=PANEL, padx=12, pady=8)
        card.pack(fill="both", expand=True, pady=(10, 0))
        tk.Label(card, text="WHAT THE FIRMWARE COMPUTES", bg=PANEL, fg=DIM,
                 font=("Segoe UI", 8, "bold")).pack(anchor="w")
        self.readout = tk.Label(card, text="", bg=PANEL, fg=TEXT, justify="left",
                                anchor="w", font=("Consolas", 9))
        self.readout.pack(anchor="w", fill="x", pady=(2, 6))
        self.dump = tk.Text(card, height=20, bg=CARD, fg=DIM, bd=0, relief="flat",
                            font=("Consolas", 8), wrap="none")
        self.dump.pack(fill="both", expand=True)
        self.dump.configure(state="disabled")

    def _build_controls(self, parent) -> None:
        # -- strip
        section = Section(parent, "Strip")
        section.pack()
        row = tk.Frame(section.body, bg=CARD)
        row.pack(fill="x")
        tk.Label(row, text="Strip on", bg=CARD, fg=TEXT,
                 font=("Segoe UI", 9)).pack(side="left")
        self.enable_button = tk.Button(row, text="ON", bg=ACCENT, fg="#101014", bd=0,
                                       relief="flat", font=("Segoe UI", 8, "bold"),
                                       padx=12, pady=3, cursor="hand2",
                                       command=self.toggle_enable)
        self.enable_button.pack(side="right")

        self.brightness = Slider(section.body, "Brightness", 0, 255, 255,
                                 on_change=self._on_brightness, colour=ACCENT)
        self.brightness.pack(fill="x")
        self.sequence = Chips(section.body, [SEQUENCE_NAMES[v] for v in
                                             (SEQ_CENTER_OUT, SEQ_LEFT_TO_RIGHT,
                                              SEQ_RIGHT_TO_LEFT, SEQ_CENTER_IN)],
                              [SEQ_CENTER_OUT, SEQ_LEFT_TO_RIGHT,
                               SEQ_RIGHT_TO_LEFT, SEQ_CENTER_IN],
                              SEQ_CENTER_OUT, self._on_sequence, colour=ACCENT)
        self.sequence.pack(fill="x", pady=(6, 0))

        self.mode = Chips(section.body, ["Gradient", "Wash"], [0, 1], 0,
                          self._on_mode, colour=PRIMARY)
        self.mode.pack(fill="x", pady=(4, 0))

        row = tk.Frame(section.body, bg=CARD)
        row.pack(fill="x", pady=(6, 0))
        self.dim_button = tk.Button(row, text="Theme dim (dark mode)", bg="#2a2a30",
                                    fg=TEXT, bd=0, relief="flat",
                                    font=("Segoe UI", 8), padx=8, pady=3,
                                    cursor="hand2", command=self.toggle_dim)
        self.dim_button.pack(fill="x")

        # -- ramp
        section = Section(parent, "Colour ramp")
        section.pack(pady=(10, 0))
        self.full_at = Slider(section.body, "Full at", 2000, 8000,
                             self.engine.cfg.full_rpm, " rpm", step=100,
                             on_change=self._on_full_at, colour=PRIMARY)
        self.full_at.pack(fill="x")
        self.swatches = Swatches(section.body,
                                 [rgb for _rpm, rgb in self.engine.cfg.ramp],
                                 self._on_stop_colour)
        self.swatches.pack(fill="x", pady=(8, 2))
        tk.Label(section.body, text="Stop colours 1-6 \u00b7 click to change",
                 bg=CARD, fg=DIM, font=("Segoe UI", 7)).pack(anchor="w")
        tk.Button(section.body, text="Reset ramp to firmware defaults", bg="#2a2a30",
                  fg=TEXT, bd=0, relief="flat", font=("Segoe UI", 8), pady=3,
                  cursor="hand2", command=self.reset_ramp).pack(fill="x", pady=(6, 0))

        # -- shift light
        section = Section(parent, "Shift light")
        section.pack(pady=(10, 0))
        row = tk.Frame(section.body, bg=CARD)
        row.pack(fill="x")
        tk.Label(row, text="Flash on shift", bg=CARD, fg=TEXT,
                 font=("Segoe UI", 9)).pack(side="left")
        self.shift_button = tk.Button(row, text="ON", bg=BAD, fg="#101014", bd=0,
                                      relief="flat", font=("Segoe UI", 8, "bold"),
                                      padx=12, pady=3, cursor="hand2",
                                      command=self.toggle_shift)
        self.shift_button.pack(side="right")
        self.shift_rpm = Slider(section.body, "Start at", 2000, 8000,
                                self.engine.cfg.shift_rpm, " rpm", step=100,
                                on_change=self._on_shift_rpm, colour=BAD)
        self.shift_rpm.pack(fill="x")
        self.shift_hz = Slider(section.body, "Flash rate", 2, 15,
                               self.engine.cfg.shift_hz, " Hz",
                               on_change=self._on_shift_hz, colour=BAD)
        self.shift_hz.pack(fill="x")

        # -- bench
        section = Section(parent, "Bench")
        section.pack(pady=(10, 0))
        row = tk.Frame(section.body, bg=CARD)
        row.pack(fill="x")
        for text, command in (("Self test", lambda: self.self_test(SELF_TEST_SWEEP)),
                              ("Identify", lambda: self.self_test(SELF_TEST_IDENTIFY))):
            tk.Button(row, text=text, bg="#2a2a30", fg=TEXT, bd=0, relief="flat",
                      font=("Segoe UI", 8), padx=8, pady=4, cursor="hand2",
                      command=command).pack(side="left", expand=True, fill="x", padx=1)
        row = tk.Frame(section.body, bg=CARD)
        row.pack(fill="x", pady=(4, 0))
        self.can_button = tk.Button(row, text="CAN: online", bg="#2a2a30", fg=TEXT,
                                    bd=0, relief="flat", font=("Segoe UI", 8),
                                    padx=8, pady=4, cursor="hand2",
                                    command=self.toggle_can)
        self.can_button.pack(side="left", expand=True, fill="x", padx=1)
        self.error_button = tk.Button(row, text="No engine frames", bg="#2a2a30", fg=TEXT,
                                      bd=0, relief="flat", font=("Segoe UI", 8),
                                      padx=8, pady=4, cursor="hand2",
                                      command=self.toggle_error)
        self.error_button.pack(side="left", expand=True, fill="x", padx=1)

        # -- simulator
        section = Section(parent, "Simulator")
        section.pack(pady=(10, 0))
        self.smooth_var = tk.BooleanVar(value=True)
        tk.Checkbutton(section.body, text="RPM smoothing (as in the firmware)",
                       variable=self.smooth_var, bg=CARD, fg=TEXT, selectcolor=CARD,
                       activebackground=CARD, activeforeground=TEXT,
                       font=("Segoe UI", 8),
                       command=self._on_smooth).pack(anchor="w")
        self.leds = Slider(section.body, "LEDs", 5, 60, self.engine.cfg.led_count,
                           step=1, on_change=self._on_led_count, colour=DIM)
        self.leds.pack(fill="x")
        if self.pi_address:
            tk.Button(section.body,
                      text="Reload from the car (%s)" % self.pi_address,
                      bg="#2a2a30", fg=TEXT, bd=0, relief="flat",
                      font=("Segoe UI", 8), pady=4, cursor="hand2",
                      command=self.load_from_pi).pack(fill="x", pady=(6, 0))

    # -- state changes -------------------------------------------------------

    def _on_rpm_drag(self, value: int) -> None:
        """A drag on the RPM track: the user is driving, so stop any sweep."""
        self.sweeping = False
        self._render_sweep_button()
        self._set_target(value)

    def set_rpm(self, rpm: int, from_scale: bool = False) -> None:
        rpm = max(0, min(9000, int(rpm)))
        self.sweeping = False
        self._render_sweep_button()
        self._set_target(rpm)

    def _set_target(self, rpm: int) -> None:
        """Move the engine to this rpm and show it immediately.

        With smoothing on, `_tick` will run the value through the firmware's filter; a
        large jump snaps either way, and a small one settles over a frame or two, which is
        the behaviour the checkbox is there to demonstrate.
        """
        self.feed_target = rpm
        self.engine.set_rpm(rpm)
        self._set_rpm_scale(rpm)

    def _set_rpm_scale(self, rpm: int) -> None:
        self.rpm_control.set(rpm)

    def nudge(self, delta: int) -> None:
        # From the target, not the rendered value: with the filter on, the bar trails the
        # target for a frame, and nudging from the trail would compound the lag.
        self.set_rpm(self.feed_target + delta)

    def toggle_sweep(self) -> None:
        self.sweeping = not self.sweeping
        if self.sweeping:
            self.sweep_direction = 1 if self.feed_target < self.engine.cfg.full_rpm else -1
        self._render_sweep_button()

    def _render_sweep_button(self) -> None:
        self.sweep_button.config(bg=ACCENT if self.sweeping else "#2a2a30",
                                 fg="#101014" if self.sweeping else TEXT)

    def toggle_enable(self) -> None:
        self.engine.cfg.enabled = not self.engine.cfg.enabled
        self.enable_button.config(
            text="ON" if self.engine.cfg.enabled else "OFF",
            bg=ACCENT if self.engine.cfg.enabled else "#2a2a30",
            fg="#101014" if self.engine.cfg.enabled else TEXT)

    def toggle_shift(self) -> None:
        self.engine.cfg.shift_rpm = 0 if self.engine.cfg.shift_rpm else self.shift_rpm.get()
        self.shift_button.config(
            text="ON" if self.engine.cfg.shift_rpm else "OFF",
            bg=BAD if self.engine.cfg.shift_rpm else "#2a2a30",
            fg="#101014" if self.engine.cfg.shift_rpm else TEXT)
        self.legend.redraw()

    def toggle_dim(self) -> None:
        self.engine.cfg.theme_dim = not self.engine.cfg.theme_dim
        self.dim_button.config(
            bg=PRIMARY if self.engine.cfg.theme_dim else "#2a2a30",
            fg="#101014" if self.engine.cfg.theme_dim else TEXT)

    def toggle_can(self) -> None:
        self.engine.can_initialized = not self.engine.can_initialized
        self.can_button.config(
            text="CAN: online" if self.engine.can_initialized else "CAN: dead",
            bg="#2a2a30" if self.engine.can_initialized else BAD,
            fg=TEXT if self.engine.can_initialized else "#101014")

    def toggle_error(self) -> None:
        self.engine.error_mode = not self.engine.error_mode
        self.error_button.config(
            bg=CARD if self.engine.error_mode else "#2a2a30",
            fg=TEXT)
        if self.engine.error_mode:
            self.engine._scan_position = 0
            self.engine._scan_direction = 1

    def self_test(self, mode: int) -> None:
        self.engine.start_self_test(mode, self.now_ms())

    def reset_ramp(self) -> None:
        self.engine.cfg = LedConfig(
            led_count=self.engine.cfg.led_count,
            sequence=self.engine.cfg.sequence,
            color_mode=self.engine.cfg.color_mode,
            theme_dim=self.engine.cfg.theme_dim,
            enabled=self.engine.cfg.enabled,
            brightness=self.engine.cfg.brightness,
            shift_rpm=self.engine.cfg.shift_rpm,
            shift_hz=self.engine.cfg.shift_hz,
            shift_color=self.engine.cfg.shift_color)
        self.full_at.low, self.full_at.high = 2000, 8000
        self.full_at.set(self.engine.cfg.full_rpm)
        self.swatches.set([rgb for _rpm, rgb in self.engine.cfg.ramp])
        self.legend.redraw()

    def _on_sequence(self, value: int) -> None:
        self.engine.cfg.sequence = value

    def _on_mode(self, value: int) -> None:
        self.engine.cfg.color_mode = value

    def _on_brightness(self, value: int) -> None:
        self.engine.cfg.brightness = value

    def _on_shift_rpm(self, value: int) -> None:
        if self.engine.cfg.shift_rpm:
            self.engine.cfg.shift_rpm = value
        self.legend.redraw()

    def _on_shift_hz(self, value: int) -> None:
        self.engine.cfg.shift_hz = max(1, value)

    def _on_full_at(self, value: int) -> None:
        """Re-derive the stop rpms exactly as LedScreen.pushRamp() would.

        From the six swatch colours, always - the app's editor has six stops and scaling
        whatever happened to be loaded (a 3-stop ramp from a hand-written RAMP: line, say)
        would reshape it into something the app cannot produce.
        """
        self.engine.cfg.full_rpm = value
        self.engine.cfg.ramp = engine.ramp_from_fractions(value, self._swatch_colours())
        self.legend.redraw()

    def _swatch_colours(self) -> List[RGB]:
        return self.swatches.colours

    def _on_stop_colour(self, index: int, colour: RGB) -> None:
        """Edit one stop.

        Editing is what the app's six swatches do, so a ramp that arrived with fewer stops
        is promoted to the app's six-stop shape rather than being silently ignored for
        stops 4-6.
        """
        stops = list(self.engine.cfg.ramp)
        if index < len(stops):
            stops[index] = (stops[index][0], colour)
            self.engine.cfg.ramp = tuple(stops)
        if len(stops) != len(engine.STOP_FRACTIONS):
            self.engine.cfg.ramp = engine.ramp_from_fractions(self.engine.cfg.full_rpm,
                                                              self._swatch_colours())
        self.legend.redraw()

    def _on_smooth(self) -> None:
        """Turning the filter off drops straight to the target; on, it re-seeds from it."""
        self.engine.smoothed_rpm = float(self.engine.rpm)

    def _on_led_count(self, value: int) -> None:
        value = max(5, min(60, value))
        self.engine.cfg.led_count = value
        self.strip.set_count(value)
        self.strip._layout()

    # -- the car -------------------------------------------------------------

    def load_from_pi(self) -> None:
        """Start from the strip's live settings, read from the Pi's REST API."""
        try:
            import json
            import urllib.request
            url = "http://%s/api/status" % self.pi_address
            request = urllib.request.Request(url)
            if self.pi_token:
                request.add_header("Authorization", "Bearer " + self.pi_token)
            with urllib.request.urlopen(request, timeout=3) as response:
                status = json.loads(response.read().decode("utf-8"))
        except Exception as exc:
            messagebox.showerror("Could not reach the car",
                                 "%s\n\n%s" % (self.pi_address, exc), parent=self)
            return

        settings = status.get("settings") or {}
        cfg = self.engine.cfg
        cfg.sequence = int(settings.get("led_sequence", cfg.sequence) or cfg.sequence)
        cfg.enabled = int(settings.get("led_enabled", 1) or 1) != 0
        cfg.color_mode = int(settings.get("led_color_mode", cfg.color_mode) or 0)
        level = int(settings.get("led_brightness", -1))
        if level >= 0:
            cfg.brightness = level
        dim = int(settings.get("led_theme_dim", -1))
        if dim >= 0:
            cfg.theme_dim = dim != 0
        cfg.shift_rpm = int(settings.get("led_shift_rpm", cfg.shift_rpm) or 0)
        cfg.shift_hz = int(settings.get("led_shift_hz", cfg.shift_hz) or cfg.shift_hz)
        colour = settings.get("led_shift_color")
        if isinstance(colour, str) and len(colour) == 6:
            try:
                cfg.shift_color = engine.rgb_of_hex(colour)
            except ValueError:
                pass
        ramp = settings.get("led_ramp")
        if isinstance(ramp, str) and ramp:
            try:
                cfg.ramp = engine.parse_ramp(ramp)
                cfg.full_rpm = cfg.ramp[-1][0]
            except ValueError:
                pass

        self._sync_controls()
        messagebox.showinfo("Loaded", "Took the LED settings currently on the car.",
                            parent=self)
    def _sync_controls(self) -> None:
        cfg = self.engine.cfg
        self.enable_button.config(text="ON" if cfg.enabled else "OFF",
                                  bg=ACCENT if cfg.enabled else "#2a2a30",
                                  fg="#101014" if cfg.enabled else TEXT)
        self.brightness.set(cfg.brightness)
        self.sequence.select(cfg.sequence)
        self.mode.select(cfg.color_mode)
        self.dim_button.config(bg=PRIMARY if cfg.theme_dim else "#2a2a30",
                               fg="#101014" if cfg.theme_dim else TEXT)
        # The strip's "full at" is whatever the last RAMP: stop says, and a hand-written
        # ramp can end below the slider's usual floor. Widen the track rather than
        # clamping it, or the display would disagree with the table underneath it.
        self.full_at.low = min(2000, cfg.full_rpm)
        self.full_at.high = max(8000, cfg.full_rpm)
        self.full_at.set(cfg.full_rpm)
        self.swatches.set([rgb for _rpm, rgb in cfg.ramp])
        self.shift_button.config(text="ON" if cfg.shift_rpm else "OFF",
                                 bg=BAD if cfg.shift_rpm else "#2a2a30",
                                 fg="#101014" if cfg.shift_rpm else TEXT)
        if cfg.shift_rpm:
            self.shift_rpm.set(cfg.shift_rpm)
        self.shift_hz.set(max(2, cfg.shift_hz))
        self.rpm_control.high = max(8000, cfg.full_rpm)
        self.leds.set(cfg.led_count)
        self.legend.redraw()

    # -- the loop ------------------------------------------------------------

    def now_ms(self) -> int:
        return int((time.time() - self.started) * 1000)

    def _tick(self) -> None:
        now = time.time()
        elapsed = min(0.2, now - self.last_tick)
        self.last_tick = now

        if self.sweeping:
            span = self.engine.cfg.full_rpm
            target = self.feed_target + self.sweep_direction * self.sweep_speed * elapsed
            if target >= span:
                target, self.sweep_direction = span, -1
            elif target <= 0:
                target, self.sweep_direction = 0, 1
            self.feed_target = int(target)

        # The strip only ever sees rpm through this filter, so the simulator does too.
        if self.smooth_var.get():
            self.engine.feed_rpm(self.feed_target)
            self._set_rpm_scale(self.engine.rpm)
        else:
            self.engine.set_rpm(self.feed_target)

        self._paint()
        self.after(TICK_MS, self._tick)

    def _paint(self) -> None:
        cfg = self.engine.cfg
        now = self.now_ms()
        frame = self.engine.shown(now)
        ranks = [engine.bar_rank(i, cfg.sequence, cfg.led_count)
                 for i in range(cfg.led_count)]
        self.strip.show(frame, ranks)

        self.rpm_label.config(text=str(self.engine.rpm))
        info = self.engine.describe(now)
        if info["shifting"]:
            state, colour = "SHIFT LIGHT", BAD
        elif not cfg.enabled:
            state, colour = "strip off", DIM
        elif self.engine.self_test_mode:
            state, colour = "self test", PRIMARY
        elif not self.engine.can_initialized:
            state, colour = "CAN dead", BAD
        elif self.engine.error_mode:
            state, colour = "no engine frames", WARN
        elif self.engine.rpm == 0:
            state, colour = "idle", DIM
        else:
            state, colour = "%s \u00b7 %s" % (info["sequence"], info["mode"]), ACCENT
        self.state_label.config(text=state, fg=colour)

        self._paint_readout(frame, info)

    def _paint_readout(self, frame: List[RGB], info: dict) -> None:
        cfg = self.engine.cfg
        self.readout.config(text=(
            "fill     %5.2f of %d units\n"
            "rpm      %d / full %d  (%.0f%%)\n"
            "ramp tip %s  colour at this rpm\n"
            "root     %s  first lit pixel\n"
            "ramp     %d stops" % (
                info["fill"], info["slots"], self.engine.rpm, cfg.full_rpm,
                100.0 * info["fraction_of_full"],
                engine.hex_of(info["tip_colour"]),
                engine.hex_of(frame[0]),
                len(cfg.ramp))))

        if not hasattr(self, "_dump_tick") or info["rpm"] != self._dump_tick:
            self._dump_tick = info["rpm"]
            lines = []
            for index in range(min(cfg.led_count, 40)):
                lines.append("%2d  rank %2d  %s" % (
                    index, engine.bar_rank(index, cfg.sequence, cfg.led_count),
                    engine.hex_of(frame[index])))
            self.dump.configure(state="normal")
            self.dump.delete("1.0", "end")
            self.dump.insert("1.0", "\n".join(lines))
            self.dump.configure(state="disabled")

    # -- keys ----------------------------------------------------------------

    def _bind_keys(self) -> None:
        self.bind("<Up>", lambda _e: self.nudge(100))
        self.bind("<Down>", lambda _e: self.nudge(-100))
        self.bind("<Prior>", lambda _e: self.nudge(500))
        self.bind("<Next>", lambda _e: self.nudge(-500))
        self.bind("<Home>", lambda _e: self.set_rpm(0))
        self.bind("<End>", lambda _e: self.set_rpm(self.engine.cfg.full_rpm))
        self.bind("<space>", lambda _e: self.toggle_sweep())
        self.bind("s", lambda _e: self._cycle_sequence())
        self.bind("m", lambda _e: self._toggle_mode())
        self.bind("e", lambda _e: self.toggle_enable())
        self.bind("t", lambda _e: self.self_test(SELF_TEST_SWEEP))
        self.bind("i", lambda _e: self.self_test(SELF_TEST_IDENTIFY))
        self.bind("<Escape>", lambda _e: self.destroy())

    def _cycle_sequence(self) -> None:
        order = [SEQ_CENTER_OUT, SEQ_LEFT_TO_RIGHT, SEQ_RIGHT_TO_LEFT, SEQ_CENTER_IN]
        current = self.engine.cfg.sequence
        nxt = order[(order.index(current) + 1) % len(order)] if current in order else order[0]
        self.engine.cfg.sequence = nxt
        self.sequence.select(nxt)

    def _toggle_mode(self) -> None:
        self.engine.cfg.color_mode = 0 if self.engine.cfg.color_mode else 1
        self.mode.select(self.engine.cfg.color_mode)


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--leds", type=int, default=engine.DEFAULT_LED_COUNT,
                        help="how many pixels the strip has (default %d)" % engine.DEFAULT_LED_COUNT)
    parser.add_argument("--rpm", type=int, default=0,
                        help="start the slider here instead of at idle")
    parser.add_argument("--pi", default=None,
                        help="host:port of the car's Pi, to load its live LED settings")
    parser.add_argument("--token", default=os.environ.get("MX5_WEB_TOKEN", ""),
                        help="API token (or set MX5_WEB_TOKEN)")
    args = parser.parse_args()

    app = LedSimulator(max(5, min(60, args.leds)), args.pi, args.token)
    if args.rpm:
        app.set_rpm(args.rpm)
    app.mainloop()
    return 0


if __name__ == "__main__":
    sys.exit(main())
