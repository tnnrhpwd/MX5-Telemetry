#!/usr/bin/env python3
"""Desk test for led_engine.py - the simulator's port of the firmware's LED rendering.

The simulator is only useful if it is the *same program* as arduino/src/main.cpp, so this
pins the port down against values worked out by hand from the C++ arithmetic. Each golden
case names the firmware expression it came from, so a disagreement points at whichever
side changed.

Runs as a plain script and under pytest:

    python led_engine.py --self-check      # prints a frame dump, for eyeballing
    python test_led_engine.py
"""

import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

import led_engine as engine  # noqa: E402
from led_engine import (  # noqa: E402
    SEQ_CENTER_IN, SEQ_CENTER_OUT, SEQ_LEFT_TO_RIGHT, SEQ_RIGHT_TO_LEFT,
    SELF_TEST_IDENTIFY, SELF_TEST_SWEEP, LedConfig, LedEngine,
)

BLACK = (0, 0, 0)


# -- rampColorAtRpm -----------------------------------------------------------

def test_a_ramp_stop_returns_its_own_colour_exactly():
    ramp = engine.DEFAULT_RAMP
    for rpm, colour in ramp:
        assert engine.ramp_color_at_rpm(rpm, ramp) == colour, rpm


def test_going_negative_wraps_as_a_uint16_before_the_lookup():
    """`rampColorAtRpm` takes a uint16_t, so -5 would arrive as 65531 -> the last stop.

    Nothing can actually pass a negative: every caller hands it an unsigned rpm. The
    assertion exists so nobody "fixes" the wrap and quietly changes the lookup.
    """
    assert engine.ramp_color_at_rpm(-5, engine.DEFAULT_RAMP) == (255, 0, 0)
    assert engine.ramp_color_at_rpm(0, engine.DEFAULT_RAMP) == (0, 0, 255)


def test_beyond_the_last_stop_returns_the_last_colour():
    assert engine.ramp_color_at_rpm(9000, engine.DEFAULT_RAMP) == (255, 0, 0)


def test_interpolation_matches_the_hand_computed_midpoint():
    """ramp[1] 1400 (0,220,255) -> ramp[2] 2800 (50,215,130); rpm 1511.

    t = (1511-1400)/1400 = 0.079285714...
    r = 0 + 50*t          = 3.964  -> +0.5 -> 4.464 -> (uint8_t) 4
    g = 220 + (-5)*t      = 219.60 -> +0.5 -> 220.10 -> (uint8_t) 220
    b = 255 + (-125)*t    = 245.09 -> +0.5 -> 245.59 -> (uint8_t) 245
    """
    assert engine.ramp_color_at_rpm(1511, engine.DEFAULT_RAMP) == (4, 220, 245)


def test_a_descending_channel_truncates_toward_zero_not_down():
    """g falls 220 -> 215 across 1400..2800. At 2266: 220 - 5*0.61857 = 216.907.

    +0.5 = 217.407, and (uint8_t) of that is 217 - not a floor to 216.
    """
    assert engine.ramp_color_at_rpm(2266, engine.DEFAULT_RAMP)[1] == 217


# -- barRank / barSlots -------------------------------------------------------

def test_center_out_fills_from_both_edges_to_the_middle():
    ranks = [engine.bar_rank(i, SEQ_CENTER_OUT, 20) for i in range(20)]
    assert ranks == [0, 1, 2, 3, 4, 5, 6, 7, 8, 9, 9, 8, 7, 6, 5, 4, 3, 2, 1, 0]
    assert engine.bar_slots(SEQ_CENTER_OUT, 20) == 10


def test_left_to_right_uses_the_whole_strip_as_its_length():
    assert [engine.bar_rank(i, SEQ_LEFT_TO_RIGHT, 20) for i in range(20)] == list(range(20))
    assert engine.bar_slots(SEQ_LEFT_TO_RIGHT, 20) == 20


def test_right_to_left_is_the_mirror_of_left_to_right():
    ltr = [engine.bar_rank(i, SEQ_LEFT_TO_RIGHT, 20) for i in range(20)]
    rtl = [engine.bar_rank(i, SEQ_RIGHT_TO_LEFT, 20) for i in range(20)]
    assert rtl == ltr[::-1]


def test_center_in_starts_at_the_middle_and_grows_outward():
    ranks = [engine.bar_rank(i, SEQ_CENTER_IN, 20) for i in range(20)]
    assert ranks == [9, 8, 7, 6, 5, 4, 3, 2, 1, 0, 0, 1, 2, 3, 4, 5, 6, 7, 8, 9]


# -- renderBar ----------------------------------------------------------------

def test_frame_at_3400_matches_the_hand_computed_bar():
    """Default config, 3400 rpm, center-out (10 slots), gradient mode.

    fill  = 1 + 3400*9/6800 = 5.5   -> full = 5, frac = 0.5, span = 4.5
    rank 0..4 are solid, rank 5 is the half-lit tip, rank 6..9 are off.
    colour position = (uint16_t)(p * rpm) with p = rank / 4.5
      rank 0: p 0.000 -> 0     -> ramp[0]  (0,0,255)
      rank 1: p 0.222 -> 755   -> (0,119,255)
      rank 2: p 0.444 -> 1511  -> (4,220,245)
      rank 3: p 0.667 -> 2266  -> (31,217,178)
      rank 4: p 0.889 -> 3022  -> (77,214,121)
      rank 5: p 1.111 clamps to 1.0 -> 3400 -> (122,213,105) at level 0.5
              -> (61,106,52)
    """
    cfg = LedConfig()
    frame = engine.render_bar(3400, cfg)

    assert frame[0] == (0, 0, 255)
    assert frame[1] == (0, 119, 255)
    assert frame[2] == (4, 220, 245)
    assert frame[3] == (31, 217, 178)
    assert frame[4] == (77, 214, 121)
    # The fractional tip is dimmed by `level`, not tinted.
    assert frame[5] == (61, 106, 52)
    for index in range(6, 10):
        assert frame[index] == BLACK, index
    # Mirrored copies on the right half.
    assert frame[14] == frame[5]
    assert frame[19] == frame[0]


def test_the_tip_is_dim_half_way_between_two_leds():
    """frac 0.5 > 0.05, so the leading LED is at 50% - and 50% of 122 is 61."""
    frame = engine.render_bar(3400, LedConfig())
    assert frame[5][0] == 61


def test_a_tiny_fraction_leaves_the_tip_dark_because_the_gate_is_0_05():
    """`if (rank == full && frac > 0.05)`: below the gate the LED is cleared, not dimmed.

    pick rpm so frac lands under 0.05: fill = 1 + rpm*9/6800, want fill just over 2.0.
    rpm = 760 -> fill = 1 + 1.00588 = 2.00588 -> full = 2, frac = 0.00588.
    """
    cfg = LedConfig()
    frame = engine.render_bar(760, cfg)
    assert frame[2] == BLACK, frame[:4]


def test_full_rpm_lights_every_slot_of_a_mirrored_sequence():
    frame = engine.render_bar(6800, LedConfig())
    assert all(rgb != BLACK for rgb in frame), frame


def test_above_full_rpm_is_clamped_rather_than_overflowing():
    at_full = engine.render_bar(6800, LedConfig())
    above = engine.render_bar(9000, LedConfig())
    assert at_full == above


def test_dim_mode_scales_every_led_by_170_over_255():
    """Compare a frame with no fractional tip, so every lit LED is at level 1.0.

    With a part-lit tip the bright and dim frames cannot be compared channel-by-channel:
    each is truncated separately, and truncating 213*0.5*170/255 (= 71.0) is not the same
    as truncating the already-truncated 106. `full_rpm=1800, rpm=1000` gives
    fill = 1 + 1000*9/1800 = 6.0 exactly, so frac is 0.
    """
    bright = engine.render_bar(1000, LedConfig(full_rpm=1800))
    dim = engine.render_bar(1000, LedConfig(full_rpm=1800, theme_dim=True))
    assert any(rgb != BLACK for rgb in bright)
    for bright_rgb, dim_rgb in zip(bright, dim):
        for index in range(3):
            assert dim_rgb[index] == int(bright_rgb[index] * 170 / 255)


def test_wash_mode_paints_the_whole_bar_one_colour():
    """One wash of colour, not a gradient - with no fractional tip to compare against."""
    frame = engine.render_bar(1000, LedConfig(full_rpm=1800, color_mode=1))
    lit = [rgb for rgb in frame if rgb != BLACK]
    assert lit, frame
    assert len(set(lit)) == 1, "wash mode must not produce a gradient"


def test_wash_mode_uses_the_tip_colour_of_the_ramp():
    frame = engine.render_bar(3400, LedConfig(color_mode=1))
    assert frame[0] == engine.ramp_color_at_rpm(3400, engine.DEFAULT_RAMP)


def test_the_fractional_tip_is_still_dimmed_in_wash_mode():
    """Wash changes the hue of the bar, not the fill: the tip keeps its partial level."""
    gradient = engine.render_bar(3400, LedConfig())
    wash = engine.render_bar(3400, LedConfig(color_mode=1))
    assert wash[5] != wash[0], "the tip should be a dimmed version of the bar colour"
    assert wash[5][0] < wash[0][0]
    assert gradient != wash


def test_lowering_full_at_makes_the_bar_longer_for_the_same_rpm():
    """This is the owner's "fully illuminated at different rpm" setting."""
    stock = engine.render_bar(3400, LedConfig(full_rpm=6800))
    short = engine.render_bar(3400, LedConfig(full_rpm=4000))
    lit = lambda f: sum(1 for rgb in f if rgb != BLACK)  # noqa: E731
    assert lit(short) > lit(stock)


# -- idle, shift, offline, bench patterns -------------------------------------

def test_idle_frame_puts_one_blue_pixel_per_fill_direction():
    assert engine.idle_frame(SEQ_CENTER_OUT, 20)[0] == (0, 0, 255)
    assert engine.idle_frame(SEQ_CENTER_OUT, 20)[19] == (0, 0, 255)
    assert sum(1 for c in engine.idle_frame(SEQ_CENTER_OUT, 20) if c != BLACK) == 2

    assert engine.idle_frame(SEQ_LEFT_TO_RIGHT, 20)[:2] == [(0, 0, 255), BLACK]
    assert engine.idle_frame(SEQ_RIGHT_TO_LEFT, 20)[19] == (0, 0, 255)
    # The firmware indexes LED_COUNT/2 for this one, i.e. 10, not 9.
    assert engine.idle_frame(SEQ_CENTER_IN, 20)[10] == (0, 0, 255)


def test_shift_light_blinks_at_the_configured_rate():
    cfg = LedConfig(shift_rpm=6300, shift_hz=8)
    # halfPeriod = 500/8 = 62 ms, and `on` is even half-periods.
    assert set(engine.shift_frame(0, cfg)) == {(255, 0, 0)}
    assert set(engine.shift_frame(62, cfg)) == {BLACK}
    assert set(engine.shift_frame(124, cfg)) == {(255, 0, 0)}


def test_shift_light_uses_its_own_colour():
    cfg = LedConfig(shift_rpm=6300, shift_hz=8, shift_color=(0, 255, 0))
    assert set(engine.shift_frame(0, cfg)) == {(0, 255, 0)}


def test_can_offline_shows_two_orange_pixels_on_the_on_half_of_the_second():
    assert engine.can_offline_frame(0, 20) == [BLACK] * 20
    on = engine.can_offline_frame(500, 20)
    assert on[0] == (255, 80, 0) and on[19] == (255, 80, 0)
    assert sum(1 for c in on if c != BLACK) == 2


def test_self_test_sweeps_one_pixel_at_a_time():
    start = engine.self_test_frame(0, SELF_TEST_SWEEP, 20)
    assert sum(1 for c in start if c != BLACK) == 1
    later = engine.self_test_frame(2000, SELF_TEST_SWEEP, 20)
    assert sum(1 for c in later if c != BLACK) == 11
    end = engine.self_test_frame(3999, SELF_TEST_SWEEP, 20)
    assert all(c != BLACK for c in end)


def test_identify_blinks_every_pixel_magenta():
    assert set(engine.self_test_frame(0, SELF_TEST_IDENTIFY, 20)) == {(255, 0, 255)}
    assert set(engine.self_test_frame(125, SELF_TEST_IDENTIFY, 20)) == {BLACK}


# -- brightness ---------------------------------------------------------------

def test_brightness_255_is_exactly_no_scaling():
    """setBrightness(255) stores 0, and the library skips the scale step entirely."""
    frame = [(10, 20, 30), (255, 255, 255)]
    assert engine.apply_brightness(frame, 255) == frame


def test_brightness_matches_the_library_shift():
    """Stored value is b+1, then `(v * stored) >> 8`: 200 -> 201 -> 0.7852."""
    assert engine.apply_brightness([(255, 0, 0)], 200) == [(200, 0, 0)]
    assert engine.apply_brightness([(255, 0, 0)], 0) == [(0, 0, 0)]
    assert engine.apply_brightness([(255, 0, 0)], 127) == [(127, 0, 0)]


# -- rpm smoothing ------------------------------------------------------------

def test_the_filter_snaps_on_a_big_jump():
    """absDelta >= RPM_SNAP_DELTA is a gear change: zero lag."""
    assert engine.smooth_rpm(3000.0, 3400.0) == 3400.0


def test_rising_rpm_has_no_filter_at_all():
    assert engine.smooth_rpm(3000.0, 3050.0) == 3050.0


def test_falling_rpm_keeps_a_light_settle():
    """delta = -100 below the snap threshold, alpha 0.75 -> 3000 - 75 = 2925."""
    assert engine.smooth_rpm(3000.0, 2900.0) == 2925.0


def test_the_first_reading_is_taken_as_is():
    assert engine.smooth_rpm(0.0, 812.0) == 812.0


# -- precedence, which is the whole of updateLEDs -----------------------------

def test_a_bench_pattern_outranks_everything_including_strip_off():
    elf = LedEngine(cfg=LedConfig(enabled=False), rpm=3000)
    elf.start_self_test(SELF_TEST_SWEEP, now_ms=1000)
    frame = elf.frame(now_ms=1200)
    assert any(rgb != BLACK for rgb in frame), "the sweep must be visible with the strip off"


def test_a_bench_pattern_expires_on_its_own():
    elf = LedEngine()
    elf.start_self_test(SELF_TEST_IDENTIFY, now_ms=0)
    # 3000//125 = 24, an even half-period, so the strip is lit right up to the limit.
    assert set(elf.frame(3000)) == {(255, 0, 255)}
    # Past IDENTIFY_MS it hands back to the normal renderer: 0 rpm, so the idle pixels.
    after = elf.frame(3001)
    assert elf.self_test_mode == engine.SELF_TEST_NONE
    assert sum(1 for c in after if c != BLACK) == 2


def test_strip_off_is_dark_but_leaves_the_rpm_alone():
    elf = LedEngine(cfg=LedConfig(enabled=False), rpm=5000)
    assert elf.frame(0) == [BLACK] * 20
    assert elf.rpm == 5000


def test_a_dead_can_controller_outranks_the_rpm():
    elf = LedEngine(can_initialized=False, rpm=5000)
    frame = elf.frame(500)
    assert sum(1 for c in frame if c != BLACK) == 2, "the CAN-offline pattern, not a bar"


def test_the_error_scanner_outranks_the_bar():
    elf = LedEngine(error_mode=True, rpm=5000)
    frame = elf.frame(0)
    assert any(rgb != BLACK for rgb in frame)
    assert frame != engine.render_bar(5000, elf.cfg)


def test_the_shift_light_outranks_the_bar():
    elf = LedEngine(cfg=LedConfig(shift_rpm=6300), rpm=6500)
    assert set(elf.frame(0)) == {(255, 0, 0)}


def test_zero_rpm_shows_the_idle_pixels_not_an_empty_bar():
    elf = LedEngine(rpm=0)
    assert sum(1 for c in elf.frame(0) if c != BLACK) == 2


def test_a_normal_frame_is_the_bar():
    elf = LedEngine(rpm=3400)
    assert elf.frame(0) == engine.render_bar(3400, elf.cfg)


# -- ramp payloads, shared with the app ---------------------------------------

def test_the_ramp_round_trips_through_the_wire_format():
    text = engine.format_ramp(engine.DEFAULT_RAMP)
    assert text.startswith("0:0000ff,")
    assert engine.parse_ramp(text) == engine.DEFAULT_RAMP


def test_the_app_fraction_table_reproduces_its_default_ramp_shape():
    """"Full at 6800" with the app's six colours must land on 0/1400/2800/4500/5800/6800."""
    colours = [rgb for _rpm, rgb in engine.DEFAULT_RAMP]
    stops = engine.ramp_from_fractions(6800, colours)
    assert [rpm for rpm, _ in stops] == [0, 1400, 2800, 4500, 5800, 6800]


def test_the_app_fraction_table_scales_with_full_at():
    colours = [rgb for _rpm, rgb in engine.DEFAULT_RAMP]
    stops = engine.ramp_from_fractions(4000, colours)
    assert [rpm for rpm, _ in stops] == [0, 800, 1600, 2600, 3400, 4000]


def test_describe_reports_what_the_frame_was_built_from():
    elf = LedEngine(cfg=LedConfig(), rpm=3400)
    info = elf.describe(0)
    assert info["fill"] == 5.5
    assert info["filled_units"] == 5
    assert info["mode"] == "gradient"
    assert info["shifting"] is False
    assert abs(info["fraction_of_full"] - 0.5) < 1e-9


# -- runner -------------------------------------------------------------------

def main():
    if "--self-check" in sys.argv:
        elf = LedEngine(rpm=3400)
        print("frame at 3400 rpm, default config:")
        for index, rgb in enumerate(elf.frame(0)):
            print("  %2d  rank %d  %s" % (
                index, engine.bar_rank(index, elf.cfg.sequence, 20), engine.hex_of(rgb)))
        print()
        print("describe:", elf.describe(0))
        return 0

    tests = [(name, fn) for name, fn in sorted(globals().items())
             if name.startswith("test_") and callable(fn)]
    failures = []
    for name, fn in tests:
        try:
            fn()
            print("  PASS  %s" % name)
        except Exception as exc:
            failures.append((name, exc))
            print("  FAIL  %s: %s: %s" % (name, type(exc).__name__, exc))

    print("\n%d/%d passed" % (len(tests) - len(failures), len(tests)))
    return 1 if failures else 0


if __name__ == "__main__":
    sys.exit(main())
