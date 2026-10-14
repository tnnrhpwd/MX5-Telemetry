package com.mx5.remote;

import android.content.Context;
import android.view.View;

/** The four corners of the car, with the low and high warnings from the settings. */
public class TpmsScreen extends Screen {

    private Host host;
    private Ui.Stat[] pressure = new Ui.Stat[4];
    private Ui.Stat[] temp = new Ui.Stat[4];
    private Ui.Stat[] age = new Ui.Stat[4];
    private Ui.Panel panel;
    private final double lowPsi = 28.0;
    private final double highPsi = 36.0;

    private static final String[] CORNERS = {"Front left", "Front right", "Rear left", "Rear right"};

    @Override
    public String title() {
        return "Tire Pressure";
    }

    @Override
    public String shortTitle() {
        return "TPMS";
    }

    @Override
    public String eyebrow() {
        return "TPMS";
    }

    @Override
    public int piScreen() {
        return 2;
    }

    @Override
    public View build(Context c, Palette p, Host h) {
        host = h;
        panel = new Ui.Panel(c, p, "TPMS", "Tire Pressure", p.primary);

        for (int i = 0; i < 4; i++) {
            pressure[i] = new Ui.Stat(c, p, CORNERS[i].toUpperCase(), "psi");
        }
        panel.body.addView(gridFill(c, pressure[0], pressure[1]));
        panel.body.addView(gridFill(c, pressure[2], pressure[3]));

        for (int i = 0; i < 4; i++) {
            temp[i] = new Ui.Stat(c, p, CORNERS[i].toUpperCase() + " TEMP", "\u00b0F");
        }
        panel.body.addView(gridFill(c, temp[0], temp[1]));
        panel.body.addView(gridFill(c, temp[2], temp[3]));

        for (int i = 0; i < 4; i++) {
            age[i] = new Ui.Stat(c, p, CORNERS[i].toUpperCase() + " SEEN", "");
        }
        panel.body.addView(gridFill(c, age[0], age[1]));
        panel.body.addView(gridFill(c, age[2], age[3]));

        return panel;
    }

    @Override
    public void bind(Telemetry t) {
        for (int i = 0; i < 4; i++) {
            double psi = i < t.tirePressure.size() ? t.tirePressure.get(i) : 0.0;
            double tf = i < t.tireTemp.size() ? t.tireTemp.get(i) : 0.0;
            String seen = i < t.tpmsUpdated.size() ? t.tpmsUpdated.get(i) : "waiting";

            int level = Ui.Stat.OK;
            if (psi > 0 && (psi < lowPsi || psi > highPsi)) {
                level = psi < lowPsi ? Ui.Stat.FAULT : Ui.Stat.CAUTION;
            }
            pressure[i].setLevel(psi > 0 ? String.format("%.1f", psi) : "\u2013", level);

            temp[i].setLevel(tf > 0 ? String.valueOf(Math.round(tf)) : "\u2013",
                    tf >= 140 ? Ui.Stat.CAUTION : Ui.Stat.OK);

            age[i].set(seen);
        }
        panel.setEyebrow(t.tpmsConnected ? "TPMS \u00b7 LINKED" : "TPMS \u00b7 NO DATA");
    }
}
