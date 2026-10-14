package com.mx5.remote;

import android.content.Context;
import android.view.View;
import android.view.ViewGroup;
import android.widget.LinearLayout;
import android.widget.ScrollView;
import android.widget.TextView;

/** Everything the webapp's settings panel exposes, plus the Pi's own state. */
public class SettingsScreen extends Screen {

    private Host host;
    private Palette palette;
    private Ui.Panel panel;

    private SliderRow brightness, volume, shiftRpm, redlineRpm, tireLow, tireHigh, coolantWarn;
    private Chips ledSequence, clutchMode;
    private Ui.Pill useMph, demoMode;

    private static final String[] LED_NAMES = {"Center out", "Left to right", "Right to left", "Center in"};
    private static final int[] LED_VALUES = {1, 2, 3, 4};
    private static final String[] CLUTCH_NAMES = {"Gear", "C for clutch", "S for shifting", "Dash"};
    private static final int[] CLUTCH_VALUES = {0, 1, 2, 3};

    @Override
    public String title() {
        return "Settings";
    }

    @Override
    public String shortTitle() {
        return "Setup";
    }

    @Override
    public String eyebrow() {
        return "Configuration";
    }

    @Override
    public int piScreen() {
        return 7;
    }

    @Override
    public View build(Context c, Palette p, Host h) {
        host = h;
        palette = p;
        panel = new Ui.Panel(c, p, "CONFIGURATION", "Settings", p.accent);

        LinearLayout columns = Ui.row(c);
        columns.setGravity(android.view.Gravity.TOP);
        columns.setLayoutParams(Ui.fillHeight());

        // -- left: display, sound, units ------------------------------------
        LinearLayout left = Ui.column(c);
        left.addView(sectionLabel(c, p, "DISPLAY AND SOUND"));

        brightness = new SliderRow(c, p, "Brightness", 0, 100, 5, 80, "%", p.accent,
                v -> push("brightness", v));
        volume = new SliderRow(c, p, "Volume", 0, 100, 5, 70, "%", p.accent,
                v -> push("volume", v));
        left.addView(brightness);
        left.addView(volume);

        useMph = new Ui.Pill(c, p, p.accent);
        useMph.setOnClickListener(v -> {
            useMph.setOn(!useMph.isOn());
            push("use_mph", useMph.isOn() ? 1 : 0);
        });
        left.addView(pillRow(c, p, "Speed in mph", useMph));

        demoMode = new Ui.Pill(c, p, p.primary);
        // The Pi ships with demo mode off, and nothing has been read yet, so the
        // pill must not claim ON before the first status arrives.
        demoMode.setOn(false);
        demoMode.setOnClickListener(v -> {
            demoMode.setOn(!demoMode.isOn());
            push("demo_mode", demoMode.isOn() ? 1 : 0);
        });
        left.addView(pillRow(c, p, "Demo mode", demoMode));

        left.addView(sectionGap(c, p, "SHIFT LIGHT", 1));
        shiftRpm = new SliderRow(c, p, "Shift at", 3000, 8000, 100, 6500, " rpm", p.primary,
                v -> push("shift_rpm", v));
        redlineRpm = new SliderRow(c, p, "Redline", 4000, 9000, 100, 7200, " rpm", p.primary,
                v -> push("redline_rpm", v));
        left.addView(shiftRpm);
        left.addView(redlineRpm);
        // The left column holds fewer sections than the right, so its share of the slack
        // is split 1:2 between the one gap and the tail: that keeps the gap the same size
        // as the right column's three and lets the remainder fall below the last row.
        left.addView(spacer(c, 2));

        // Both halves are attached at the end, because how they are arranged depends on the
        // width, and that is not known until here.

        // -- right: vehicle thresholds and LED behaviour ---------------------
        LinearLayout right = Ui.column(c);
        right.addView(sectionLabel(c, p, "TIRE PRESSURE"));

        tireLow = new SliderRow(c, p, "Low warning", 15, 40, 1, 28, " psi", p.warn,
                v -> push("tire_low_psi", v));
        tireHigh = new SliderRow(c, p, "High warning", 25, 55, 1, 36, " psi", p.warn,
                v -> push("tire_high_psi", v));
        right.addView(tireLow);
        right.addView(tireHigh);

        right.addView(sectionGap(c, p, "ENGINE WARNING", 1));
        coolantWarn = new SliderRow(c, p, "Coolant warn", 180, 260, 5, 220, "\u00b0F", p.bad,
                v -> push("coolant_warn", v));
        right.addView(coolantWarn);

        right.addView(sectionGap(c, p, "LED STRIP", 1));
        ledSequence = new Chips(c, p, LED_NAMES, LED_VALUES, p.accent,
                v -> push("led_sequence", v));
        right.addView(ledSequence, wrap(c));

        right.addView(sectionGap(c, p, "CLUTCH DISPLAY", 1));
        clutchMode = new Chips(c, p, CLUTCH_NAMES, CLUTCH_VALUES, p.primary,
                v -> push("clutch_display_mode", v));
        right.addView(clutchMode, wrap(c));

        // Both halves are attached here rather than as they are built, because how they are
        // arranged depends on the width.
        if (isNarrow(c)) {
            // One column on a phone. Two columns of sliders do not fit 380dp: the left
            // slider's value label lands on top of the right column's heading and the track
            // runs underneath it, which reads as a broken screen.
            LinearLayout stack = Ui.column(c);
            stack.addView(left);
            stack.addView(right);

            // Eleven settings are taller than a phone screen, so the list scrolls rather
            // than being silently cut off at the bottom.
            ScrollView scroller = new ScrollView(c);
            scroller.setFillViewport(false);
            scroller.addView(stack, new LinearLayout.LayoutParams(
                    ViewGroup.LayoutParams.MATCH_PARENT,
                    ViewGroup.LayoutParams.WRAP_CONTENT));
            panel.body.addView(scroller, Ui.fillHeight());
        } else {
            columns.addView(left, new LinearLayout.LayoutParams(0,
                    ViewGroup.LayoutParams.MATCH_PARENT, 1f));
            columns.addView(right, new LinearLayout.LayoutParams(0,
                    ViewGroup.LayoutParams.MATCH_PARENT, 1f));
            panel.body.addView(columns);
        }
        return panel;
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

    /**
     * A section heading that also claims a share of the column's leftover height. Its text
     * sits at the bottom of that share, so the extra space reads as breathing room above
     * the heading rather than as a dead band under the last row.
     */
    private static TextView sectionGap(Context c, Palette p, String text, int weight) {
        TextView t = sectionLabel(c, p, text);
        if (isNarrow(c)) {
            // Inside a phone's scrolling column there is no leftover height to share, and a
            // height-0 weighted view measures to nothing, so the heading would vanish
            // rather than just lose its spacing.
            return t;
        }
        t.setGravity(android.view.Gravity.BOTTOM);
        t.setLayoutParams(new LinearLayout.LayoutParams(
                ViewGroup.LayoutParams.MATCH_PARENT, 0, weight));
        return t;
    }

    /** Empty space that absorbs leftover height without drawing anything. */
    private static View spacer(Context c, int weight) {
        View v = new View(c);
        v.setLayoutParams(new LinearLayout.LayoutParams(
                ViewGroup.LayoutParams.MATCH_PARENT, 0, weight));
        return v;
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

    /** Posts one setting update off the UI thread. */
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

    @Override
    public void applyStatus(org.json.JSONObject status) {
        org.json.JSONObject s = status.optJSONObject("settings");
        if (s == null) {
            return;
        }
        brightness.setValue(s.optInt("brightness", 80));
        volume.setValue(s.optInt("volume", 70));
        shiftRpm.setValue(s.optInt("shift_rpm", 6500));
        redlineRpm.setValue(s.optInt("redline_rpm", 7200));
        tireLow.setValue((int) Math.round(s.optDouble("tire_low_psi", 28)));
        tireHigh.setValue((int) Math.round(s.optDouble("tire_high_psi", 36)));
        coolantWarn.setValue(s.optInt("coolant_warn_f", 220));
        ledSequence.select(s.optInt("led_sequence", 1));
        clutchMode.select(s.optInt("clutch_display_mode", 0));
        useMph.setOn(s.optBoolean("use_mph", true));
        demoMode.setOn(s.optBoolean("demo_mode", false));
    }
}
