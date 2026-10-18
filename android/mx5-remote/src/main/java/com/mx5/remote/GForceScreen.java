package com.mx5.remote;

import android.content.Context;
import android.view.Gravity;
import android.view.View;
import android.view.ViewGroup;
import android.widget.LinearLayout;
import android.widget.TextView;

import org.json.JSONObject;

/**
 * The g-force scatter, plus the peaks.
 *
 * Peaks are tracked here rather than on the Pi because they are a property of the
 * session you are looking at, and they reset when you leave the screen. That is
 * deliberate: a peak that survives a restart is a number you cannot attribute.
 */
public class GForceScreen extends Screen {

    private GForceView view;
    private Ui.Stat now, peakLateral, peakLongitudinal, peakTotal;
    private Ui.Bar bar;

    private double maxLat;
    private double maxLong;

    @Override
    public String title() {
        return "G-Force";
    }

    @Override
    public String eyebrow() {
        return "Chassis";
    }

    @Override
    public int piScreen() {
        return 4;
    }

    @Override
    public View build(Context c, Palette p, Host h) {
        Ui.Panel panel = new Ui.Panel(c, p, "CHASSIS", "G-Force", p.accent);

        LinearLayout body = Ui.row(c);

        view = new GForceView(c);
        view.setColors(p.text, p.textDim, p.track, p.accent, p.tile);
        body.addView(view, new LinearLayout.LayoutParams(0,
                ViewGroup.LayoutParams.MATCH_PARENT, 1f));

        LinearLayout side = Ui.column(c);
        now = new Ui.Stat(c, p, "NOW", "g");
        peakTotal = new Ui.Stat(c, p, "PEAK TOTAL", "g");
        peakLateral = new Ui.Stat(c, p, "PEAK LATERAL", "g");
        peakLongitudinal = new Ui.Stat(c, p, "PEAK LONG", "g");
        // Filling, so the readouts spread down the column instead of bunching at the top.
        side.addView(now, Ui.stackFill(c, 3));
        side.addView(peakTotal, Ui.stackFill(c, 3));
        side.addView(peakLateral, Ui.stackFill(c, 3));
        side.addView(peakLongitudinal, Ui.stackFill(c, 3));

        bar = new Ui.Bar(c, p, "Cornering load", p.primary);
        side.addView(bar, Ui.stack(c, 3));

        body.addView(side, new LinearLayout.LayoutParams(0,
                ViewGroup.LayoutParams.MATCH_PARENT, 0.55f));

        panel.body.addView(body, new LinearLayout.LayoutParams(
                ViewGroup.LayoutParams.MATCH_PARENT, 0, 1f));

        // Zeroing belongs on this screen, not only on the System screen: you set the zero
        // while looking at the readout it affects, sitting in the car on the surface you
        // actually drive on.
        TextView calibrate = calibrateButton(c, p);
        calibrate.setOnClickListener(v -> runCalibrate(h));
        LinearLayout actionRow = Ui.row(c);
        actionRow.addView(calibrate, Ui.cell(c, 2));
        panel.body.addView(actionRow, Ui.stack(c, 1));

        return panel;
    }

    private static TextView calibrateButton(Context c, Palette p) {
        TextView t = Ui.label(c, 11f, p.primary);
        t.setText("Zero g-force");
        t.setGravity(Gravity.CENTER);
        t.setPadding(Ui.dp(c, 10), Ui.dp(c, 8), Ui.dp(c, 10), Ui.dp(c, 8));
        t.setClickable(true);
        t.setFocusable(true);
        t.setBackground(Ui.rounded(c, Palette.alpha(p.primary, 0.18f), 8f));
        return t;
    }

    /**
     * Ask the Pi to zero the IMU, then clear the peaks.
     *
     * The peaks have to go: they were measured against the old zero point, so keeping them
     * would compare two different scales in the same column.
     */
    private void runCalibrate(Host host) {
        host.toast("Zeroing g-force...", false);
        new Thread(() -> {
            String message;
            boolean failed;
            try {
                JSONObject r = host.pi().calibrateImu();
                boolean ok = r.optBoolean("success");
                message = ok ? "G-force zero set" : r.optString("message", "Rejected");
                failed = !ok;
            } catch (Exception e) {
                message = "Could not reach the Pi";
                failed = true;
            }
            if (!failed) {
                maxLat = 0;
                maxLong = 0;
                if (bar != null) {
                    bar.set(0f, "0.00 g");
                }
            }
            String shown = message;
            boolean err = failed;
            if (view != null) {
                view.post(() -> host.toast(shown, err));
            }
        }).start();
    }

    @Override
    public void bind(Telemetry t) {
        double lat = t.gLateral;
        double lng = t.gLongitudinal;
        maxLat = Math.max(maxLat, Math.abs(lat));
        maxLong = Math.max(maxLong, Math.abs(lng));

        view.setValue((float) lat, (float) lng);

        double total = t.gMagnitude();
        now.set(String.format("%.2f", total));
        peakTotal.set(String.format("%.2f", Math.max(total, Math.hypot(maxLat, maxLong))));
        peakLateral.set(String.format("%.2f", maxLat));
        peakLongitudinal.set(String.format("%.2f", maxLong));
        bar.set((float) (total / 1.2), String.format("%.2f g", total));
    }
}
