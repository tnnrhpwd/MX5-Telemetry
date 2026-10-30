#!/usr/bin/env python3
"""Desk test for the steering wheel control handler.

The wheel is the only input while driving, and it is the one input that cannot be
exercised by a unit test on the car, so the mapping and the debounce rules are pinned
here instead:

* every cruise button reaches the UI on a press+release cycle;
* ON/OFF is reported on *release*, because a hold toggles the navigation lock;
* a hold past the threshold toggles the lock and does not also fire Select;
* with navigation locked only ON/OFF is delivered;
* frames closer together than the debounce window do not repeat.

    python3 test_swc_handler.py
    pytest test_swc_handler.py
"""

import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

import swc_handler                                                # noqa: E402
from swc_handler import (                                         # noqa: E402
    SWCHandler, ButtonEvent, SWC_CRUISE_CAN_ID,
    SWC_ON_OFF, SWC_CANCEL, SWC_RES_PLUS, SWC_SET_MINUS,
    NAV_LOCK_HOLD_TIME_MS,
)

class Clock:
    """Deterministic millisecond clock, patched in where the handler reads time."""

    def __init__(self, start_ms=100000.0):
        self.ms = start_ms

    def time(self):
        return self.ms / 1000.0

    def advance(self, ms):
        self.ms += ms


def make_handler():
    clock = Clock()
    swc_handler.time = clock
    return SWCHandler(), clock


def press(handler, mask):
    handler.process_can_message(SWC_CRUISE_CAN_ID, bytes([mask]))


def release(handler):
    handler.process_can_message(SWC_CRUISE_CAN_ID, bytes([0x00]))


def tap(handler, clock, mask, gap_ms=100):
    """One press, a gap longer than the debounce window, then the release."""
    press(handler, mask)
    clock.advance(gap_ms)
    release(handler)
    clock.advance(gap_ms)


def names(buttons):
    return [b.name for b in buttons]


# -- the mapping -------------------------------------------------------------

def test_every_cruise_button_reaches_the_ui():
    handler, clock = make_handler()
    for mask, expected in ((SWC_RES_PLUS, 'RES_PLUS'),
                           (SWC_SET_MINUS, 'SET_MINUS'),
                           (SWC_CANCEL, 'CANCEL'),
                           (SWC_ON_OFF, 'ON_OFF')):
        tap(handler, clock, mask)
        assert names(handler.poll_buttons()) == [expected], expected


def test_select_is_reported_once_per_short_press():
    """Select used to be dropped entirely: it is queued on release, and the release
    branch compared against a field nothing ever set."""
    handler, clock = make_handler()
    tap(handler, clock, SWC_ON_OFF)
    assert names(handler.poll_buttons()) == ['ON_OFF']
    assert names(handler.poll_buttons()) == []


def test_a_release_without_a_press_reports_nothing():
    handler, clock = make_handler()
    release(handler)
    clock.advance(100)
    release(handler)
    assert handler.poll_buttons() == []


def test_frames_inside_the_debounce_window_do_not_repeat():
    handler, clock = make_handler()
    press(handler, SWC_RES_PLUS)
    release(handler)
    clock.advance(10)                      # inside DEBOUNCE_MS
    press(handler, SWC_RES_PLUS)
    clock.advance(10)
    release(handler)
    assert names(handler.poll_buttons()) == ['RES_PLUS']


def test_a_second_press_after_the_window_is_a_second_event():
    handler, clock = make_handler()
    tap(handler, clock, SWC_RES_PLUS)
    tap(handler, clock, SWC_RES_PLUS)
    assert names(handler.poll_buttons()) == ['RES_PLUS', 'RES_PLUS']


# -- the lock ----------------------------------------------------------------

def test_holding_select_toggles_the_lock_and_does_not_select():
    handler, clock = make_handler()
    press(handler, SWC_ON_OFF)
    clock.advance(NAV_LOCK_HOLD_TIME_MS + 200)   # held past the threshold
    press(handler, SWC_ON_OFF)                   # the frame that notices the hold
    assert handler.nav_locked is True
    release(handler)
    clock.advance(100)
    assert handler.poll_buttons() == [], "a lock hold must not also fire Select"


def test_a_short_select_press_does_not_lock():
    handler, clock = make_handler()
    tap(handler, clock, SWC_ON_OFF, gap_ms=NAV_LOCK_HOLD_TIME_MS // 4)
    assert handler.nav_locked is False
    assert names(handler.poll_buttons()) == ['ON_OFF']


def test_locked_ignores_every_short_press_including_select():
    """While locked, the only thing the wheel can do is unlock: a short press of any
    button - Select included - is dropped rather than acting on the dashboard."""
    handler, clock = make_handler()
    handler.set_nav_locked(True)

    for mask in (SWC_RES_PLUS, SWC_SET_MINUS, SWC_CANCEL, SWC_ON_OFF):
        tap(handler, clock, mask)
    assert handler.poll_buttons() == []


def test_holding_select_while_locked_unlocks():
    handler, clock = make_handler()
    handler.set_nav_locked(True)

    press(handler, SWC_ON_OFF)
    clock.advance(NAV_LOCK_HOLD_TIME_MS + 200)
    press(handler, SWC_ON_OFF)
    release(handler)
    clock.advance(100)

    assert handler.nav_locked is False
    assert handler.poll_buttons() == []


def test_unlocking_from_the_handler_reaches_the_callback():
    handler, clock = make_handler()
    seen = []
    handler.add_lock_callback(seen.append)

    press(handler, SWC_ON_OFF)
    clock.advance(NAV_LOCK_HOLD_TIME_MS + 200)
    press(handler, SWC_ON_OFF)
    release(handler)

    assert seen == [True]
    handler.toggle_nav_lock()
    assert seen == [True, False]


# -- other frames ------------------------------------------------------------

def test_frames_from_another_id_are_ignored():
    handler, clock = make_handler()
    handler.process_can_message(0x240, bytes([0x01]))    # audio buttons, not on this bus
    clock.advance(100)
    assert handler.poll_buttons() == []


def test_an_empty_frame_does_not_raise():
    handler, _ = make_handler()
    handler.process_can_message(SWC_CRUISE_CAN_ID, b'')
    assert handler.poll_buttons() == []


# -- runner ------------------------------------------------------------------

def main():
    tests = [(n, f) for n, f in sorted(globals().items())
             if n.startswith('test_') and callable(f)]
    failures = []
    for name, fn in tests:
        try:
            fn()
            print("  PASS  %s" % name)
        except Exception as e:
            failures.append((name, e))
            print("  FAIL  %s: %s: %s" % (name, type(e).__name__, e))

    print("\n%d/%d passed" % (len(tests) - len(failures), len(tests)))
    return 1 if failures else 0


if __name__ == '__main__':
    sys.exit(main())
