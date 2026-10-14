package com.mx5.remote;

import android.content.Context;
import android.view.Gravity;
import android.view.View;
import android.widget.LinearLayout;
import android.widget.TextView;

/** Warning lamps and stored fault codes. */
public class DiagnosticsScreen extends Screen {

    private Ui.Panel panel;
    private Palette palette;
    private Lamp cel, abs, oil, battery, brake, airbag, door, seatbelt, traction;
    private TextView dtcText;
    private TextView dtcCount;

    @Override
    public String title() {
        return "Diagnostics";
    }

    @Override
    public String shortTitle() {
        return "Diag";
    }

    @Override
    public String eyebrow() {
        return "Faults";
    }

    @Override
    public int piScreen() {
        return 5;
    }

    @Override
    public View build(Context c, Palette p, Host h) {
        palette = p;
        panel = new Ui.Panel(c, p, "FAULTS", "Diagnostics", p.warn);

        cel = new Lamp(c, p, "CHECK ENGINE");
        abs = new Lamp(c, p, "ABS");
        oil = new Lamp(c, p, "OIL");
        battery = new Lamp(c, p, "BATTERY");
        brake = new Lamp(c, p, "BRAKE");
        airbag = new Lamp(c, p, "AIRBAG");
        door = new Lamp(c, p, "DOOR");
        seatbelt = new Lamp(c, p, "SEATBELT");
        traction = new Lamp(c, p, "TRACTION");

        panel.body.addView(gridFill(c, cel, abs, oil));
        panel.body.addView(gridFill(c, battery, brake, airbag));
        panel.body.addView(gridFill(c, door, seatbelt, traction));

        LinearLayout codeHead = Ui.row(c);
        codeHead.setPadding(Ui.dp(c, 3), Ui.dp(c, 3), Ui.dp(c, 3), 0);
        TextView codeLabel = Ui.caps(c, 9f, p.textDim);
        codeLabel.setText("Stored codes");
        dtcCount = Ui.label(c, 12f, p.text);
        dtcCount.setTypeface(Ui.bold());
        codeHead.addView(codeLabel);
        codeHead.addView(Ui.gap(c));
        codeHead.addView(dtcCount);
        panel.body.addView(codeHead);

        dtcText = Ui.label(c, 11f, p.text);
        dtcText.setPadding(Ui.dp(c, 3), Ui.dp(c, 3), Ui.dp(c, 3), 0);
        panel.body.addView(dtcText);

        return panel;
    }

    @Override
    public void bind(Telemetry t) {
        cel.set(t.checkEngine);
        abs.set(t.absWarning);
        oil.set(t.oilWarning);
        battery.set(t.batteryWarning);
        brake.set(t.brakeWarning);
        airbag.set(t.airbagWarning);
        door.set(t.doorAjar);
        seatbelt.set(t.seatbeltWarning);
        traction.set(t.tractionControlActive || t.tractionControlOff);

        dtcCount.setText(t.dtcCount + (t.dtcCount == 1 ? " code" : " codes"));
        dtcCount.setTextColor(t.dtcCount > 0 ? 0xFFEF4444 : 0xFF22C55E);
        dtcText.setText(t.dtcCodes.isEmpty() ? "None reported" : String.join("   ", t.dtcCodes));

        int issues = (t.checkEngine ? 1 : 0) + (t.absWarning ? 1 : 0) + (t.oilWarning ? 1 : 0)
                + (t.batteryWarning ? 1 : 0) + (t.brakeWarning ? 1 : 0) + (t.airbagWarning ? 1 : 0);
        panel.setEyebrow(issues == 0 ? "FAULTS \u00b7 ALL CLEAR" : "FAULTS \u00b7 " + issues + " ACTIVE");
        panel.setAccent(issues == 0 ? palette.good : palette.warn);
    }

    /** A single warning lamp: reads as a quiet tile until it is actually on. */
    static class Lamp extends LinearLayout {

        private final TextView state;
        private final Context ctx;
        private final Palette palette;

        Lamp(Context c, Palette p, String name) {
            super(c);
            ctx = c;
            palette = p;
            setOrientation(VERTICAL);
            setGravity(Gravity.CENTER);
            setPadding(Ui.dp(c, 8), Ui.dp(c, 6), Ui.dp(c, 8), Ui.dp(c, 6));

            TextView label = Ui.caps(c, 8f, p.textDim);
            label.setText(name);
            label.setGravity(Gravity.CENTER);

            state = Ui.label(c, 13f, p.textDim);
            state.setTypeface(Ui.bold());
            state.setGravity(Gravity.CENTER);

            addView(label);
            addView(state);
            set(false);
        }

        void set(boolean bad) {
            state.setText(bad ? "ON" : "OK");
            state.setTextColor(bad ? palette.bad : palette.good);
            // Idle lamps use the shared tile colour, not a hand-picked near-duplicate of
            // the panel: the previous 0xFF232324 sat one shade off panel's 0xFF212124, so
            // nine perfectly good tiles were invisible and the grid read as loose text.
            setBackground(Ui.rounded(ctx, bad
                    ? Palette.alpha(palette.bad, palette.dark ? 0.22f : 0.14f)
                    : palette.tile, 9f));
        }
    }
}
