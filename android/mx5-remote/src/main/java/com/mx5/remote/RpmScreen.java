package com.mx5.remote;

import android.content.Context;
import android.view.View;
import android.view.ViewGroup;
import android.widget.LinearLayout;

/** The big dial, plus the numbers that go with it. */
public class RpmScreen extends Screen {

    private Host host;
    private GaugeView gauge;
    private Ui.Stat gear, speed, shift, redline;
    private Ui.Bar throttle;
    private Ui.Panel panel;

    @Override
    public String title() {
        return "RPM / Speed";
    }

    @Override
    public String shortTitle() {
        return "RPM";
    }

    @Override
    public String eyebrow() {
        return "Drive";
    }

    @Override
    public int piScreen() {
        return 1;
    }

    @Override
    public View build(Context c, Palette p, Host h) {
        host = h;
        panel = new Ui.Panel(c, p, "DRIVE", "RPM / Speed", p.accent);

        LinearLayout body = Ui.row(c);

        gauge = new GaugeView(c);
        gauge.setColors(p.text, p.textDim, p.track, p.accent);
        LinearLayout.LayoutParams gp = new LinearLayout.LayoutParams(0,
                ViewGroup.LayoutParams.MATCH_PARENT, 1f);
        body.addView(gauge, gp);

        LinearLayout side = Ui.column(c);
        gear = new Ui.Stat(c, p, "GEAR", "");
        speed = new Ui.Stat(c, p, "SPEED", "mph");
        shift = new Ui.Stat(c, p, "SHIFT AT", "rpm");
        redline = new Ui.Stat(c, p, "REDLINE", "rpm");
        // Filling rather than natural height: four short tiles at the top of a tall column
        // left the bottom half of the panel empty.
        side.addView(gear, Ui.stackFill(c, 3));
        side.addView(speed, Ui.stackFill(c, 3));
        side.addView(shift, Ui.stackFill(c, 3));
        side.addView(redline, Ui.stackFill(c, 3));
        throttle = new Ui.Bar(c, p, "Throttle", p.primary);
        // The bar keeps its natural height: it is a gauge, not a readout, so it should not
        // grow to match the tiles beside it.
        side.addView(throttle, Ui.stack(c, 3));
        body.addView(side, new LinearLayout.LayoutParams(0,
                ViewGroup.LayoutParams.MATCH_PARENT, 0.55f));

        panel.body.addView(body, new LinearLayout.LayoutParams(
                ViewGroup.LayoutParams.MATCH_PARENT, 0, 1f));
        return panel;
    }

    @Override
    public void bind(Telemetry t) {
        boolean mph = host == null || host.useMph();
        float shiftAt = 6500f;
        float redlineAt = 7200f;

        gauge.setCaption("RPM", "x1000");
        gauge.setValue(t.rpm, shiftAt, redlineAt);

        String gearText = t.inNeutral ? "N"
                : t.inReverse ? "R"
                : t.gear <= 0 ? "\u2013" : String.valueOf(t.gear);
        gear.set(gearText, OverviewScreen.gearColor(t));
        gear.setUnit(t.gearEstimated ? "est" : "");

        speed.set(String.valueOf(Math.round(t.speedFor(mph ? 1 : 0))));
        speed.setUnit(mph ? "mph" : "km/h");
        shift.set("6500");
        redline.set("7200");
        throttle.set(t.throttlePercent / 100f, t.throttlePercent + "%");
    }
}
