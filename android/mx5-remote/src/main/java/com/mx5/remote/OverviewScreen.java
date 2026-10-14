package com.mx5.remote;

import android.content.Context;
import android.view.View;

/** Everything at a glance: the four things you watch while driving, then the rest. */
public class OverviewScreen extends Screen {

    private Host host;
    private Ui.Stat speed, rpm, gear, coolant, fuel, range, volts, mpg, throttle, brake;
    private Ui.Bar fuelBar, throttleBar, brakeBar;
    private Ui.Panel panel;

    @Override
    public String title() {
        return "Overview";
    }

    @Override
    public String eyebrow() {
        return "Telemetry";
    }

    @Override
    public int piScreen() {
        return 0;
    }

    @Override
    public View build(Context c, Palette p, Host h) {
        host = h;
        panel = new Ui.Panel(c, p, "TELEMETRY", "Overview", p.accent);

        speed = new Ui.Stat(c, p, "SPEED", "mph");
        rpm = new Ui.Stat(c, p, "RPM", "");
        gear = new Ui.Stat(c, p, "GEAR", "");
        coolant = new Ui.Stat(c, p, "COOLANT", "\u00b0F");
        panel.body.addView(gridFill(c, speed, rpm, gear, coolant));

        fuel = new Ui.Stat(c, p, "FUEL", "%");
        range = new Ui.Stat(c, p, "RANGE", "mi");
        volts = new Ui.Stat(c, p, "BATTERY", "V");
        mpg = new Ui.Stat(c, p, "AVG", "mpg");
        panel.body.addView(gridFill(c, fuel, range, volts, mpg));

        fuelBar = new Ui.Bar(c, p, "Fuel level", p.primary);
        throttleBar = new Ui.Bar(c, p, "Throttle", p.accent);
        brakeBar = new Ui.Bar(c, p, "Brake", p.warn);
        panel.body.addView(fuelBar, topMargin(c, 6));
        panel.body.addView(throttleBar, topMargin(c, 6));
        panel.body.addView(brakeBar, topMargin(c, 6));

        return panel;
    }

    private static android.widget.LinearLayout.LayoutParams topMargin(Context c, int dp) {
        android.widget.LinearLayout.LayoutParams p =
                new android.widget.LinearLayout.LayoutParams(
                        android.widget.LinearLayout.LayoutParams.MATCH_PARENT,
                        android.widget.LinearLayout.LayoutParams.WRAP_CONTENT);
        p.topMargin = Ui.dp(c, dp);
        return p;
    }

    @Override
    public void bind(Telemetry t) {
        boolean mph = host == null || host.useMph();
        speed.set(String.valueOf(Math.round(t.speedFor(mph ? 1 : 0))));
        speed.setUnit(mph ? "mph" : "km/h");
        rpm.setLevel(String.valueOf(t.rpm), t.rpm >= 6500 ? Ui.Stat.FAULT : Ui.Stat.OK);

        String gearText;
        if (t.inNeutral) {
            gearText = "N";
        } else if (t.inReverse) {
            gearText = "R";
        } else if (t.gear <= 0) {
            gearText = "\u2013";
        } else {
            gearText = String.valueOf(t.gear);
        }
        gear.set(gearText, gearColor(t));
        gear.setUnit(t.gearEstimated ? "est" : "");

        coolant.setLevel(String.valueOf(t.coolantTempF),
                t.coolantTempF >= 220 ? Ui.Stat.FAULT : Ui.Stat.OK);

        fuel.set(String.valueOf(Math.round(t.fuelLevelPercent)));
        range.set(String.valueOf(t.rangeMiles));
        volts.setLevel(String.format("%.1f", t.voltage),
                t.voltage > 0 && t.voltage < 12.0 ? Ui.Stat.CAUTION : Ui.Stat.OK);
        mpg.set(String.format("%.1f", t.averageMpg));

        fuelBar.set((float) (t.fuelLevelPercent / 100.0), Math.round(t.fuelLevelPercent) + "%");
        throttleBar.set(t.throttlePercent / 100f, t.throttlePercent + "%");
        brakeBar.set(t.brakePercent / 100f, t.brakePercent + "%");
    }

    static int gearColor(Telemetry t) {
        switch (t.gearColor == null ? "" : t.gearColor) {
            case "red":
                return 0xFFEF4444;
            case "blue":
                return 0xFF3B82F6;
            case "yellow":
                return 0xFFEAB308;
            case "cyan":
                return 0xFF22D3EE;
            default:
                return 0xFF22C55E;
        }
    }
}
