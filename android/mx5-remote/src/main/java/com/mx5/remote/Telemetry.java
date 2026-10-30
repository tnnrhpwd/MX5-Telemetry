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
    /** False when the Pi has no MAF/speed reading: the UI shows "--", not 0.0. */
    public boolean instantMpgValid;
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

    /**
     * The LED strip's own health, as reported by the Nano's STATUS: line.
     *
     * It exists because the strip used to be a black box: a dead CAN link, a strip that
     * had been switched off and a genuine 0 rpm all looked identical from the phone.
     */
    public static final class Led {
        public boolean connected;
        public boolean can;
        public boolean error;
        public boolean dim;
        public boolean enabled = true;
        public int rpm;
        public int fps;
        public int sequence;
        public int fullRpm;
        public int colorMode;
        public int shiftRpm;
        public int shiftHz;
        public String lastId = "";
    }

    public Led led = new Led();

    /**
     * Copy every field from a freshly parsed snapshot into this one.
     *
     * The shell keeps a long-lived Telemetry and copied the fields by hand, which is how
     * instantMpgValid came to be missed: the Engine page then showed "--" no matter what
     * the car sent. One method next to the fields cannot miss one.
     */
    public void copyFrom(Telemetry t) {
        rpm = t.rpm;
        speedKmh = t.speedKmh;
        gear = t.gear;
        gearEstimated = t.gearEstimated;
        clutchEngaged = t.clutchEngaged;
        recommendedGear = t.recommendedGear;
        gearColor = t.gearColor;
        inNeutral = t.inNeutral;
        inReverse = t.inReverse;
        throttlePercent = t.throttlePercent;
        brakePercent = t.brakePercent;
        coolantTempF = t.coolantTempF;
        intakeTempF = t.intakeTempF;
        ambientTempF = t.ambientTempF;
        maf = t.maf;
        fuelLevelPercent = t.fuelLevelPercent;
        voltage = t.voltage;
        tirePressure.clear();
        tirePressure.addAll(t.tirePressure);
        tireTemp.clear();
        tireTemp.addAll(t.tireTemp);
        tpmsUpdated.clear();
        tpmsUpdated.addAll(t.tpmsUpdated);
        tpmsConnected = t.tpmsConnected;
        gLateral = t.gLateral;
        gLongitudinal = t.gLongitudinal;
        lapTimeMs = t.lapTimeMs;
        bestLapMs = t.bestLapMs;
        instantMpg = t.instantMpg;
        instantMpgValid = t.instantMpgValid;
        averageMpg = t.averageMpg;
        rangeMiles = t.rangeMiles;
        checkEngine = t.checkEngine;
        absWarning = t.absWarning;
        tractionControlActive = t.tractionControlActive;
        tractionControlOff = t.tractionControlOff;
        oilWarning = t.oilWarning;
        batteryWarning = t.batteryWarning;
        doorAjar = t.doorAjar;
        seatbeltWarning = t.seatbeltWarning;
        airbagWarning = t.airbagWarning;
        brakeWarning = t.brakeWarning;
        headlightsOn = t.headlightsOn;
        highBeamsOn = t.highBeamsOn;
        fogLightOn = t.fogLightOn;
        dtcCodes.clear();
        dtcCodes.addAll(t.dtcCodes);
        dtcCount = t.dtcCount;
        canConnected = t.canConnected;
        demoMode = t.demoMode;
        sleeping = t.sleeping;
        led = t.led;
    }

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
        t.instantMpgValid = o.optBoolean("instant_mpg_valid", t.instantMpg > 0.0);
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
        t.led = ledFrom(o.optJSONObject("led"));
        return t;
    }

    private static Led ledFrom(JSONObject o) {
        Led led = new Led();
        if (o == null) {
            return led;
        }
        led.connected = o.optBoolean("connected");
        led.can = o.optBoolean("can");
        led.error = o.optBoolean("error");
        led.dim = o.optBoolean("dim");
        led.enabled = o.optBoolean("enabled", true);
        led.rpm = o.optInt("rpm");
        led.fps = o.optInt("fps");
        led.sequence = o.optInt("sequence");
        led.fullRpm = o.optInt("full_rpm");
        led.colorMode = o.optInt("color_mode");
        led.shiftRpm = o.optInt("shift_rpm");
        led.shiftHz = o.optInt("shift_hz");
        led.lastId = o.optString("last_id", "");
        return led;
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
