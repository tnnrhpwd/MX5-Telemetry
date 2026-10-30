package com.mx5.remote;

import android.content.Context;
import android.content.SharedPreferences;
import android.graphics.Typeface;
import android.view.Gravity;
import android.view.View;
import android.view.ViewGroup;
import android.widget.LinearLayout;
import android.widget.ScrollView;
import android.widget.TextView;

import java.util.ArrayList;
import java.util.List;
import java.util.Locale;

/**
 * Everything the LED strip can be told to do, in one place.
 *
 * The strip used to be configured by editing constants in the Nano's sketch: pattern,
 * colours, redline and brightness were all compile-time, and the only control the app had
 * was a four-way pattern chip. This screen replaces that with the settings the firmware
 * now accepts at runtime, plus the strip's own STATUS: line so a dead strip stops looking
 * like a working one at zero rpm.
 *
 * Phone-only (piScreen() == -1): the Pi has no page for it, and nothing here is safe to
 * operate while driving.
 */
public class LedScreen extends Screen {

    /** Fill patterns, shared with the Settings page's row so the two cannot drift. */
    public static final String[] SEQ_NAMES =
            {"Center out", "Left to right", "Right to left", "Center in"};
    public static final int[] SEQ_VALUES = {1, 2, 3, 4};

    private static final String[] MODE_NAMES = {"Gradient", "Wash"};
    private static final int[] MODE_VALUES = {0, 1};

    /**
     * The colours a ramp stop can take.
     *
     * Deliberately a short fixed list rather than a hue wheel: the strip is 8-bit colour,
     * and a driver has no business picking a hue at 70 mph.
     */
    private static final String[] SWATCHES = {
            "0a84ff", "00c1c1", "32d782", "ffd23c", "ff8000", "ef4444", "b44bff", "ffffff"
    };

    /** Where each of the six stops sits along the rev range, as a fraction of "full at". */
    private static final float[] STOP_FRACTIONS = {0f, 0.21f, 0.41f, 0.66f, 0.85f, 1f};

    private static final String[] DEFAULT_COLOURS =
            {"0a84ff", "00c1c1", "32d782", "ffd23c", "ff8000", "ef4444"};

    private static final int DEFAULT_FULL_RPM = 6800;

    private static final String PREF_FOLLOW_THEME = "led_follow_theme";

    private Host host;
    private Palette palette;
    private Ui.Panel panel;

    private Ui.Pill enabled, followTheme, shiftOn;
    private SliderRow brightness, fullAt, shiftRpm, shiftHz;
    private Chips sequence, colorMode;
    private final Swatches[] stopSwatches = new Swatches[6];
    private Swatches shiftColour;

    private TextView diagnostics, diagnostics2;

    /** The six stop colours as rrggbb, and the rpm the strip is completely full at. */
    private final String[] stopColours = DEFAULT_COLOURS.clone();
    private int fullRpm = DEFAULT_FULL_RPM;
    private String shiftHex = "ff0000";

    @Override
    public String title() {
        return "LED Strip";
    }

    @Override
    public String shortTitle() {
        return "LED";
    }

    @Override
    public String eyebrow() {
        return "Lighting";
    }

    @Override
    public int hue() {
        return 1;
    }

    @Override
    public int piScreen() {
        return -1;
    }

    @Override
    public View build(Context c, Palette p, Host h) {
        host = h;
        palette = p;
        panel = new Ui.Panel(c, p, "LIGHTING", "LED Strip", p.primary);

        LinearLayout left = Ui.column(c);
        LinearLayout right = Ui.column(c);

        // -- strip ------------------------------------------------------------
        left.addView(sectionLabel(c, p, "STRIP"));

        enabled = new Ui.Pill(c, p, p.accent);
        enabled.setOnClickListener(v -> {
            enabled.setOn(!enabled.isOn());
            push("led_enabled", enabled.isOn() ? 1 : 0);
        });
        left.addView(pillRow(c, p, "Strip on", enabled));

        brightness = new SliderRow(c, p, "Brightness", 0, 255, 5, 180, "", p.accent, null)
                .onRelease(() -> push("led_brightness", brightness.value()));
        left.addView(brightness);

        sequence = new Chips(c, p, SEQ_NAMES, SEQ_VALUES, p.accent,
                v -> push("led_sequence", v));
        left.addView(sequence, wrap(c));

        colorMode = new Chips(c, p, MODE_NAMES, MODE_VALUES, p.primary,
                v -> push("led_color_mode", v));
        left.addView(colorMode, wrap(c));

        // -- ramp -------------------------------------------------------------
        left.addView(sectionGap(c, p, "COLOUR RAMP", 1));

        followTheme = new Ui.Pill(c, p, p.primary);
        followTheme.setOn(prefs(c).getBoolean(PREF_FOLLOW_THEME, true));
        followTheme.setOnClickListener(v -> {
            boolean on = !followTheme.isOn();
            followTheme.setOn(on);
            // The shell is what derives a ramp from the palette, so it has to be asked.
            prefs(c).edit().putBoolean(PREF_FOLLOW_THEME, on).apply();
            if (on && host != null) {
                host.reapplyTheme();
            }
        });
        left.addView(pillRow(c, p, "Follow theme", followTheme));

        // "Full at" is the RPM scale the owner asked for: the engine speed at which the
        // strip is completely lit. Lowering it makes every LED cover fewer revs, which is
        // what makes the bar feel quicker as well as more granular.
        fullAt = new SliderRow(c, p, "Full at", 2000, 8000, 100, DEFAULT_FULL_RPM, " rpm",
                p.primary, v -> fullRpm = v)
                .onRelease(this::pushRamp);
        left.addView(fullAt);

        for (int i = 0; i < stopSwatches.length; i++) {
            final int index = i;
            stopSwatches[i] = new Swatches(c, p, SWATCHES, stopColours[i],
                    v -> {
                        stopColours[index] = v;
                        stopEditingLocally(c);
                        pushRamp();
                    });
            left.addView(stopRow(c, p, stopLabel(i), stopSwatches[i]));
        }

        // -- shift light ------------------------------------------------------
        right.addView(sectionLabel(c, p, "SHIFT LIGHT"));

        shiftOn = new Ui.Pill(c, p, p.bad);
        shiftOn.setOnClickListener(v -> {
            boolean on = !shiftOn.isOn();
            shiftOn.setOn(on);
            // Zero is the firmware's "no shift light" value; there is no second flag.
            push("led_shift_rpm", on ? shiftRpm.value() : 0);
        });
        right.addView(pillRow(c, p, "Flash on shift", shiftOn));

        shiftRpm = new SliderRow(c, p, "Start at", 3000, 7500, 100, 6300, " rpm", p.bad, null)
                .onRelease(() -> {
                    if (shiftOn.isOn()) {
                        push("led_shift_rpm", shiftRpm.value());
                    }
                });
        right.addView(shiftRpm);

        shiftHz = new SliderRow(c, p, "Flash rate", 2, 15, 1, 8, " Hz", p.bad, null)
                .onRelease(() -> push("led_shift_hz", shiftHz.value()));
        right.addView(shiftHz);

        shiftColour = new Swatches(c, p, SWATCHES, shiftHex, v -> {
            shiftHex = v;
            push("led_shift_color", v);
        });
        right.addView(stopRow(c, p, "Colour", shiftColour));

        // -- diagnostics ------------------------------------------------------
        right.addView(sectionGap(c, p, "DIAGNOSTICS", 1));

        diagnostics = Ui.label(c, 12f, p.text);
        diagnostics.setTypeface(Typeface.DEFAULT_BOLD);
        right.addView(diagnostics);

        diagnostics2 = Ui.label(c, 10f, p.textDim);
        right.addView(diagnostics2);

        LinearLayout actions = Ui.row(c);
        actions.addView(actionButton(c, p, "Self test", () -> command("SELFTEST")), Ui.cell(c, 3));
        actions.addView(actionButton(c, p, "Identify", () -> command("IDENTIFY")), Ui.cell(c, 3));
        right.addView(actions, wrap(c));

        if (isNarrow(c)) {
            LinearLayout stack = Ui.column(c);
            stack.addView(left);
            stack.addView(right);
            ScrollView scroller = new ScrollView(c);
            scroller.setFillViewport(false);
            scroller.addView(stack, new LinearLayout.LayoutParams(
                    ViewGroup.LayoutParams.MATCH_PARENT, ViewGroup.LayoutParams.WRAP_CONTENT));
            panel.body.addView(scroller, Ui.fillHeight());
        } else {
            LinearLayout columns = Ui.row(c);
            columns.setGravity(Gravity.TOP);
            columns.setLayoutParams(Ui.fillHeight());
            columns.addView(left, new LinearLayout.LayoutParams(0,
                    ViewGroup.LayoutParams.MATCH_PARENT, 1f));
            columns.addView(right, new LinearLayout.LayoutParams(0,
                    ViewGroup.LayoutParams.MATCH_PARENT, 1f));
            panel.body.addView(columns);
        }
        return panel;
    }

    /**
     * The strip's own view of itself, polled with the rest of the telemetry.
     *
     * This is the whole point of the STATUS: line: "not answering", "no CAN" and a real
     * zero rpm used to be indistinguishable from the phone.
     */
    @Override
    public void bind(Telemetry t) {
        if (diagnostics == null) {
            return;
        }
        Telemetry.Led led = t.led;
        String state;
        int colour;
        if (led == null || !led.connected) {
            state = "Strip: not answering";
            colour = palette == null ? 0xFFFF8C32 : palette.warn;
        } else if (!led.can) {
            state = "Strip: CAN controller down";
            colour = palette == null ? 0xFFEF4444 : palette.bad;
        } else if (led.error) {
            state = "Strip: no engine frames";
            colour = palette == null ? 0xFFEF4444 : palette.bad;
        } else if (!led.enabled) {
            state = "Strip: off";
            colour = palette == null ? 0xFF9BA1AB : palette.textDim;
        } else {
            state = "Strip: OK";
            colour = palette == null ? 0xFF22C55E : palette.good;
        }
        diagnostics.setText(state);
        diagnostics.setTextColor(colour);
        diagnostics2.setText(led == null || !led.connected
                ? "No status from the Nano"
                : String.format(Locale.US, "%d fps \u00b7 last %s \u00b7 full %d rpm \u00b7 %d Hz",
                        led.fps, led.lastId.isEmpty() ? "--" : led.lastId,
                        led.fullRpm, led.shiftHz));
    }

    @Override
    public void applyStatus(org.json.JSONObject status) {
        if (enabled == null) {
            return;
        }
        org.json.JSONObject s = status.optJSONObject("settings");
        if (s == null) {
            return;
        }
        enabled.setOn(s.optInt("led_enabled", 1) != 0);
        int level = s.optInt("led_brightness", 180);
        brightness.setValue(level < 0 ? 180 : level);
        sequence.select(s.optInt("led_sequence", 1));
        colorMode.select(s.optInt("led_color_mode", 0));

        int shift = s.optInt("led_shift_rpm", 6300);
        shiftOn.setOn(shift != 0);
        if (shift != 0) {
            shiftRpm.setValue(shift);
        }
        shiftHz.setValue(s.optInt("led_shift_hz", 8));
        shiftHex = s.optString("led_shift_color", "ff0000");
        shiftColour.select(shiftHex);

        applyRamp(s.optString("led_ramp", ""));
    }

    /** Parse "<rpm>:<rrggbb>,..." back into the six stop colours and the full-at rpm. */
    private void applyRamp(String ramp) {
        if (ramp == null || ramp.isEmpty()) {
            return;
        }
        String[] parts = ramp.split(",");
        int n = Math.min(parts.length, stopColours.length);
        if (n < 2) {
            return;
        }
        for (int i = 0; i < n; i++) {
            int colon = parts[i].indexOf(':');
            if (colon <= 0) {
                continue;
            }
            String colour = parts[i].substring(colon + 1).trim().toLowerCase(Locale.US);
            if (colour.length() == 6) {
                stopColours[i] = colour;
                stopSwatches[i].select(colour);
            }
        }
        try {
            int last = Integer.parseInt(parts[n - 1].substring(0, parts[n - 1].indexOf(':')));
            if (last >= 2000 && last <= 8000) {
                fullRpm = last;
                fullAt.setValue(last);
            }
        } catch (RuntimeException ignored) {
            // A malformed ramp leaves the previous scale alone rather than zeroing it.
        }
    }

    /**
     * A hand-picked colour means the user is no longer following the theme.
     *
     * Without this the next theme change would silently overwrite what they just chose,
     * which reads as the setting not working.
     */
    private void stopEditingLocally(Context c) {
        if (followTheme.isOn()) {
            followTheme.setOn(false);
            prefs(c).edit().putBoolean(PREF_FOLLOW_THEME, false).apply();
        }
    }

    private SharedPreferences prefs(Context c) {
        return c.getSharedPreferences("mx5", Context.MODE_PRIVATE);
    }

    /** Build the six stops and send them as one RAMP:, with "full at" as the last stop. */
    private void pushRamp() {
        StringBuilder sb = new StringBuilder();
        for (int i = 0; i < stopColours.length; i++) {
            int rpm = Math.round(fullRpm * STOP_FRACTIONS[i] / 100f) * 100;
            if (i == stopColours.length - 1) {
                rpm = fullRpm;
            }
            if (i > 0 && rpm <= 0) {
                rpm = 100;
            }
            if (i > 0) {
                sb.append(',');
            }
            sb.append(rpm).append(':').append(stopColours[i]);
        }
        push("led_ramp", sb.toString());
    }

    private static String stopLabel(int index) {
        return "S" + (index + 1) + " \u00b7 " + Math.round(STOP_FRACTIONS[index] * 100) + "%";
    }

    private void push(String name, Object value) {
        new Thread(() -> {
            try {
                org.json.JSONObject r = host.pi().updateSetting(name, value);
                if (!r.optBoolean("success")) {
                    String err = r.optString("error", "Rejected");
                    panel.post(() -> host.toast(err, true));
                }
            } catch (Exception e) {
                panel.post(() -> host.toast("Could not reach the Pi", true));
            }
        }).start();
    }

    private void command(String name) {
        new Thread(() -> {
            try {
                org.json.JSONObject r = host.pi().ledCommand(name);
                if (!r.optBoolean("success")) {
                    String err = r.optString("error", "Rejected");
                    panel.post(() -> host.toast(err, true));
                }
            } catch (Exception e) {
                panel.post(() -> host.toast("Could not reach the Pi", true));
            }
        }).start();
    }

    private static LinearLayout.LayoutParams wrap(Context c) {
        LinearLayout.LayoutParams p = new LinearLayout.LayoutParams(
                ViewGroup.LayoutParams.MATCH_PARENT, ViewGroup.LayoutParams.WRAP_CONTENT);
        p.topMargin = Ui.dp(c, 2);
        return p;
    }

    private static TextView sectionLabel(Context c, Palette p, String text) {
        TextView t = Ui.caps(c, 9f, p.textDim);
        t.setText(text);
        t.setPadding(0, Ui.dp(c, 10), 0, Ui.dp(c, 4));
        return t;
    }

    /** A heading that also claims a share of the column's leftover height. */
    private static TextView sectionGap(Context c, Palette p, String text, int weight) {
        TextView t = sectionLabel(c, p, text);
        if (isNarrow(c)) {
            return t;
        }
        t.setGravity(Gravity.BOTTOM);
        t.setLayoutParams(new LinearLayout.LayoutParams(
                ViewGroup.LayoutParams.MATCH_PARENT, 0, weight));
        return t;
    }

    private static LinearLayout pillRow(Context c, Palette p, String label, Ui.Pill pill) {
        LinearLayout r = Ui.row(c);
        r.setPadding(0, Ui.dp(c, 6), 0, 0);
        TextView t = Ui.label(c, 11f, p.text);
        t.setText(label);
        r.addView(t);
        r.addView(Ui.gap(c));
        r.addView(pill);
        return r;
    }

    private static LinearLayout stopRow(Context c, Palette p, String label, View swatches) {
        LinearLayout r = Ui.row(c);
        r.setGravity(Gravity.CENTER_VERTICAL);
        r.setPadding(0, Ui.dp(c, 2), 0, 0);
        TextView t = Ui.caps(c, 8f, p.textDim);
        t.setText(label);
        t.setMinWidth(Ui.dp(c, 52));
        r.addView(t);
        r.addView(swatches, new LinearLayout.LayoutParams(0,
                ViewGroup.LayoutParams.WRAP_CONTENT, 1f));
        return r;
    }

    private static TextView actionButton(Context c, Palette p, String label, Runnable action) {
        TextView b = Ui.label(c, 10f, p.text);
        b.setText(label);
        b.setTypeface(Ui.bold());
        b.setGravity(Gravity.CENTER);
        b.setPadding(Ui.dp(c, 6), Ui.dp(c, 11), Ui.dp(c, 6), Ui.dp(c, 11));
        b.setBackground(Ui.rounded(c, p.tile, 8f));
        b.setClickable(true);
        b.setFocusable(true);
        b.setOnClickListener(v -> action.run());
        return b;
    }

    /** A row of fixed colour choices; the picked one keeps a ring so it reads as selected. */
    static class Swatches extends LinearLayout {

        private final Palette palette;
        private final String[] colours;
        private final List<View> dots = new ArrayList<>();
        private String selected;

        Swatches(Context c, Palette p, String[] colours, String selected,
                 ScreenHostCallback onPick) {
            super(c);
            this.palette = p;
            this.colours = colours;
            setOrientation(HORIZONTAL);
            setGravity(Gravity.CENTER_VERTICAL);

            for (String hex : colours) {
                final String value = hex;
                View dot = new View(c);
                LinearLayout.LayoutParams lp = new LinearLayout.LayoutParams(0,
                        Ui.dp(c, 18), 1f);
                lp.setMargins(Ui.dp(c, 2), 0, Ui.dp(c, 2), 0);
                dot.setClickable(true);
                dot.setFocusable(true);
                dot.setOnClickListener(v -> {
                    select(value);
                    onPick.onPick(value);
                });
                addView(dot, lp);
                dots.add(dot);
            }
            select(selected);
        }

        /** Highlight this colour. An unknown colour selects nothing rather than lying. */
        void select(String hex) {
            selected = hex == null ? null : hex.toLowerCase(Locale.US);
            for (int i = 0; i < dots.size(); i++) {
                boolean on = colours[i].equalsIgnoreCase(selected);
                android.graphics.drawable.GradientDrawable bg =
                        Ui.rounded(getContext(), colourOf(colours[i]), 5f);
                if (on) {
                    bg.setStroke(Ui.dp(getContext(), 2), palette.text);
                }
                dots.get(i).setBackground(bg);
            }
        }

        private static int colourOf(String hex) {
            try {
                return 0xFF000000 | Integer.parseInt(hex, 16);
            } catch (NumberFormatException e) {
                return 0xFF808080;
            }
        }
    }

    /** The one callback a swatch row needs, so it does not depend on the whole screen. */
    interface ScreenHostCallback {
        void onPick(String hex);
    }
}
