package com.mx5.remote;

import android.content.Context;
import android.view.View;
import android.view.ViewGroup;
import android.widget.LinearLayout;

/**
 * The g-force scatter, plus the peaks.
 *
 * Peaks are tracked here rather than on the Pi because they are a property of the
 * session you are looking at, and they reset when you leave the screen. That is
 * deliberate: a peak that survives a restart is a number you cannot attribute.
 */
public class GForceScreen extends Screen {

    private GForceView view;
    private Ui.Stat now, peakLateral, peakLongitudinal, peakTotal, lap, best;
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
        view.setColors(p.text, p.textDim, p.track, p.accent);
        body.addView(view, new LinearLayout.LayoutParams(0,
                ViewGroup.LayoutParams.MATCH_PARENT, 1f));

        LinearLayout side = Ui.column(c);
        now = new Ui.Stat(c, p, "NOW", "g");
        peakTotal = new Ui.Stat(c, p, "PEAK TOTAL", "g");
        peakLateral = new Ui.Stat(c, p, "PEAK LATERAL", "g");
        peakLongitudinal = new Ui.Stat(c, p, "PEAK LONG", "g");
        side.addView(now, Ui.stack(c, 3));
        side.addView(peakTotal, Ui.stack(c, 3));
        side.addView(peakLateral, Ui.stack(c, 3));
        side.addView(peakLongitudinal, Ui.stack(c, 3));

        lap = new Ui.Stat(c, p, "LAP", "");
        best = new Ui.Stat(c, p, "BEST", "");
        side.addView(grid(c, lap, best), Ui.stack(c, 0));

        bar = new Ui.Bar(c, p, "Cornering load", p.primary);
        side.addView(bar, Ui.stack(c, 3));

        body.addView(side, new LinearLayout.LayoutParams(0,
                ViewGroup.LayoutParams.MATCH_PARENT, 0.55f));

        panel.body.addView(body, new LinearLayout.LayoutParams(
                ViewGroup.LayoutParams.MATCH_PARENT, 0, 1f));
        return panel;
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
        // A zero lap time means there is no lap yet, and the dash clock reads as noise
        // in a tile this narrow, so say so instead.
        lap.set(t.lapTimeMs > 0 ? Telemetry.clock(t.lapTimeMs) : "none");
        best.set(t.bestLapMs > 0 ? Telemetry.clock(t.bestLapMs) : "none");
        bar.set((float) (total / 1.2), String.format("%.2f g", total));
    }
}
