package com.mx5.remote;

import android.content.Context;
import android.view.View;

/** Temperatures, airflow and electrical, which is what the round display's engine page showed. */
public class EngineScreen extends Screen {

    private Ui.Stat coolant, intake, ambient, oil, maf, fuel, volts, mpg;
    private Ui.Bar coolantBar, intakeBar, fuelBar;
    private Ui.Panel panel;
    private Palette palette;

    @Override
    public String title() {
        return "Engine";
    }

    @Override
    public String eyebrow() {
        return "Powertrain";
    }

    @Override
    public int piScreen() {
        return 3;
    }

    @Override
    public View build(Context c, Palette p, Host h) {
        palette = p;
        panel = new Ui.Panel(c, p, "POWERTRAIN", "Engine", p.primary);

        coolant = new Ui.Stat(c, p, "COOLANT", "\u00b0F");
        intake = new Ui.Stat(c, p, "INTAKE", "\u00b0F");
        ambient = new Ui.Stat(c, p, "AMBIENT", "\u00b0F");
        oil = new Ui.Stat(c, p, "OIL", "");
        panel.body.addView(gridFill(c, coolant, intake, ambient, oil));

        maf = new Ui.Stat(c, p, "MAF", "g/s");
        fuel = new Ui.Stat(c, p, "FUEL", "%");
        volts = new Ui.Stat(c, p, "BATTERY", "V");
        mpg = new Ui.Stat(c, p, "INSTANT", "mpg");
        panel.body.addView(gridFill(c, maf, fuel, volts, mpg));

        coolantBar = new Ui.Bar(c, p, "Coolant", p.accent);
        intakeBar = new Ui.Bar(c, p, "Intake", p.accent);
        fuelBar = new Ui.Bar(c, p, "Fuel", p.primary);
        panel.body.addView(coolantBar);
        panel.body.addView(intakeBar);
        panel.body.addView(fuelBar);

        return panel;
    }

    @Override
    public void bind(Telemetry t) {
        // Coolant runs 60..260 F on a normal drive, so the bar is scaled to that
        // window rather than to 0..260, which would look inert most of the time.
        float coolantFraction = (t.coolantTempF - 60f) / 200f;
        int coolantColor = t.coolantTempF >= 220 ? 0xFFEF4444 : 0xFF22C55E;
        coolant.set(String.valueOf(t.coolantTempF), coolantColor);
        coolantBar.set(coolantFraction, t.coolantTempF + "\u00b0F", coolantColor);

        // Normal values take the theme's text colour. A literal white is invisible on
        // the light theme, where the tiles are near-white.
        int intakeColor = t.intakeTempF >= 150 ? palette.warn : palette.text;
        intake.set(String.valueOf(t.intakeTempF), intakeColor);
        intakeBar.set((t.intakeTempF - 40f) / 160f, t.intakeTempF + "\u00b0F", intakeColor);

        ambient.set(String.valueOf(t.ambientTempF));
        oil.set(t.oilWarning ? "LOW" : "OK", t.oilWarning ? 0xFFEF4444 : 0xFF22C55E);

        maf.set(String.format("%.1f", t.maf));
        fuel.set(String.valueOf(Math.round(t.fuelLevelPercent)));
        volts.set(String.format("%.2f", t.voltage),
                t.voltage > 0 && t.voltage < 12.0 ? palette.warn : palette.text);
        mpg.set(t.instantMpgValid ? String.format("%.1f", t.instantMpg) : "--");
        fuelBar.set((float) (t.fuelLevelPercent / 100.0), Math.round(t.fuelLevelPercent) + "%");
    }
}
