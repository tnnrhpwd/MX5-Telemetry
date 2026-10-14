package com.mx5.remote;

import org.json.JSONArray;
import org.json.JSONObject;

import java.util.ArrayList;
import java.util.List;

/**
 * One snapshot from GET /api/telemetry.
 *
 * Every field mirrors an attribute on TelemetryData in pi/ui/src/main.py. Values
 * default rather than throwing, so a Pi running an older build, or a partially
 * populated frame, degrades to zeros instead of killing the poll loop.
 */
public final class Telemetry {

    public int rpm;
    public int speedKmh;
    public int gear;
    public boolean gearEstimated;
    public boolean clutchEngaged;
    public int recommendedGear;
    public String gearColor = "green";
    public boolean inNeutral;
    public boolean inReverse;

    public int throttlePercent;
    public int brakePercent;

    public int coolantTempF;
    public int intakeTempF;
    public int ambientTempF;
    public double maf;
    public double fuelLevelPercent;
    public double voltage;

    public final List<Double> tirePressure = new ArrayList<>();
    public final List<Double> tireTemp = new ArrayList<>();
    public final List<String> tpmsUpdated = new ArrayList<>();
    public boolean tpmsConnected;

    public double gLateral;
    public double gLongitudinal;

    public int lapTimeMs;
    public int bestLapMs;
    public double instantMpg;
    public double averageMpg;
    public int rangeMiles;

    public boolean checkEngine;
    public boolean absWarning;
    public boolean tractionControlActive;
    public boolean tractionControlOff;
    public boolean oilWarning;
    public boolean batteryWarning;
    public boolean doorAjar;
    public boolean seatbeltWarning;
    public boolean airbagWarning;
    public boolean brakeWarning;
    public boolean headlightsOn;
    public boolean highBeamsOn;
    public boolean fogLightOn;
    public final List<String> dtcCodes = new ArrayList<>();
    public int dtcCount;

    public boolean canConnected;
    public boolean demoMode;
    public boolean sleeping;

    public static Telemetry from(JSONObject o) {
        Telemetry t = new Telemetry();
        if (o == null) {
            return t;
        }
        t.rpm = o.optInt("rpm");
        t.speedKmh = o.optInt("speed_kmh");
        t.gear = o.optInt("gear");
        t.gearEstimated = o.optBoolean("gear_estimated");
        t.clutchEngaged = o.optBoolean("clutch_engaged");
        t.recommendedGear = o.optInt("recommended_gear", 1);
        t.gearColor = o.optString("gear_color", "green");
        t.inNeutral = o.optBoolean("is_in_neutral");
        t.inReverse = o.optBoolean("is_in_reverse");

        t.throttlePercent = o.optInt("throttle_percent");
        t.brakePercent = o.optInt("brake_percent");

        t.coolantTempF = o.optInt("coolant_temp_f");
        t.intakeTempF = o.optInt("intake_temp_f");
        t.ambientTempF = o.optInt("ambient_temp_f");
        t.maf = o.optDouble("maf");
        t.fuelLevelPercent = o.optDouble("fuel_level_percent");
        t.voltage = o.optDouble("voltage");

        fillDoubles(o.optJSONArray("tire_pressure"), t.tirePressure);
        fillDoubles(o.optJSONArray("tire_temp"), t.tireTemp);
        JSONArray upd = o.optJSONArray("tpms_last_update_str");
        if (upd != null) {
            for (int i = 0; i < upd.length(); i++) {
                t.tpmsUpdated.add(upd.optString(i, "--:--:--"));
            }
        }
        t.tpmsConnected = o.optBoolean("tpms_connected");

        t.gLateral = o.optDouble("g_lateral");
        t.gLongitudinal = o.optDouble("g_longitudinal");

        t.lapTimeMs = o.optInt("lap_time_ms");
        t.bestLapMs = o.optInt("best_lap_ms");
        t.instantMpg = o.optDouble("instant_mpg");
        t.averageMpg = o.optDouble("average_mpg");
        t.rangeMiles = o.optInt("range_miles");

        t.checkEngine = o.optBoolean("check_engine_light");
        t.absWarning = o.optBoolean("abs_warning");
        t.tractionControlActive = o.optBoolean("traction_control_active");
        t.tractionControlOff = o.optBoolean("traction_control_off");
        // oil_status is TRUE when oil is present, so the warning is its inverse.
        t.oilWarning = !o.optBoolean("oil_status", true);
        t.batteryWarning = o.optBoolean("battery_warning");
        t.doorAjar = o.optBoolean("door_ajar");
        t.seatbeltWarning = o.optBoolean("seatbelt_warning");
        t.airbagWarning = o.optBoolean("airbag_warning");
        t.brakeWarning = o.optBoolean("brake_warning");
        t.headlightsOn = o.optBoolean("headlights_on");
        t.highBeamsOn = o.optBoolean("high_beams_on");
        t.fogLightOn = o.optBoolean("fog_light_on");

        JSONArray dtc = o.optJSONArray("dtc_codes");
        if (dtc != null) {
            for (int i = 0; i < dtc.length(); i++) {
                t.dtcCodes.add(dtc.optString(i));
            }
        }
        t.dtcCount = o.optInt("dtc_count", t.dtcCodes.size());

        t.canConnected = o.optBoolean("can_connected");
        t.demoMode = o.optBoolean("demo_mode");
        t.sleeping = o.optBoolean("sleeping");
        return t;
    }

    private static void fillDoubles(JSONArray src, List<Double> out) {
        out.clear();
        for (int i = 0; i < 4; i++) {
            out.add(src == null ? 0.0 : src.optDouble(i, 0.0));
        }
    }

    // -- derived helpers the screens use ------------------------------------

    public double speedMph() {
        return speedKmh * 0.621371;
    }

    public double speedFor(double useMph) {
        return useMph != 0 ? speedMph() : speedKmh;
    }

    public double gMagnitude() {
        return Math.sqrt(gLateral * gLateral + gLongitudinal * gLongitudinal);
    }

    /** Highest pressure reading, or 0 when TPMS has nothing yet. */
    public double maxTirePressure() {
        double max = 0;
        for (double p : tirePressure) {
            max = Math.max(max, p);
        }
        return max;
    }

    public double minTirePressure() {
        double min = Double.MAX_VALUE;
        for (double p : tirePressure) {
            min = Math.min(min, p);
        }
        return min == Double.MAX_VALUE ? 0 : min;
    }

    public static String clock(int ms) {
        if (ms <= 0) {
            return "--:--.--";
        }
        int total = ms / 10;
        int hundredths = total % 100;
        int seconds = (total / 100) % 60;
        int minutes = total / 6000;
        return String.format("%d:%02d.%02d", minutes, seconds, hundredths);
    }
}
