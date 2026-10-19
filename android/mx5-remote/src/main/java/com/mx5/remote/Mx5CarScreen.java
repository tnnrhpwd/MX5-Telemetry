package com.mx5.remote;

import android.content.Context;
import android.content.SharedPreferences;
import android.os.Handler;
import android.os.Looper;

import androidx.annotation.NonNull;
import androidx.car.app.CarContext;
import androidx.car.app.Screen;
import androidx.car.app.model.Action;
import androidx.car.app.model.Pane;
import androidx.car.app.model.PaneTemplate;
import androidx.car.app.model.Row;
import androidx.car.app.model.Template;
import androidx.lifecycle.Lifecycle;
import androidx.lifecycle.LifecycleEventObserver;

/**
 * The in-motion view.
 *
 * This exists because a parked "game" app is hidden by Android Auto as soon as the car
 * moves. A templated session is allowed to stay up, but only through host-rendered
 * templates: the app supplies text, the host decides the layout, the font sizes and how
 * much may be shown at once. That is deliberate - it is what keeps the screen glanceable
 * instead of turning the head unit into a second instrument cluster.
 *
 * The content mirrors the Android app's Overview page, minus the things that need
 * looking at rather than glancing at (the shift ladder, the fuel bar). Values come first
 * and labels second because the host draws the row title large: at a red light the eye
 * should land on "42 mph", not on the word "Speed".
 */
public class Mx5CarScreen extends Screen {

    private static final String PREFS = "mx5";
    private static final String DEFAULT_ADDRESS = "192.168.42.100:5000";
    private static final long POLL_MS = 1000;

    private final PiClient pi;
    private final SharedPreferences prefs;
    private final Handler handler = new Handler(Looper.getMainLooper());

    /** Last successful reading, or null before the first one arrives. */
    private volatile Telemetry latest;

    /** True while a fetch is in flight, so a slow link cannot pile up requests.
     *  Volatile: written by the worker thread and read by the main-thread poll, and a
     *  stale `true` here would stop polling for the rest of the session. */
    private volatile boolean fetching;

    private final Runnable poll = new Runnable() {
        @Override
        public void run() {
            fetchOnce();
            handler.postDelayed(this, POLL_MS);
        }
    };

    public Mx5CarScreen(@NonNull CarContext context) {
        super(context);

        SharedPreferences prefs = context.getSharedPreferences(PREFS, Context.MODE_PRIVATE);
        this.prefs = prefs;
        pi = PiLink.acquire();
        // Only configure the shared client when nobody has yet. configure() rebuilds the
        // transport chain, and the parked dashboard may be mid-request on the same client.
        if (!pi.isConfigured()) {
            pi.configure(prefs.getString("address", DEFAULT_ADDRESS),
                    prefs.getString("token", ""));
        }

        // Screen has no onDestroy() of its own in 1.4.0; its lifecycle is the hook.
        // Polling only runs while the screen is visible, and the shared client is
        // released when the host is finished with this screen.
        getLifecycle().addObserver((LifecycleEventObserver) (source, event) -> {
            if (event == Lifecycle.Event.ON_START) {
                handler.removeCallbacks(poll);
                handler.post(poll);
            } else if (event == Lifecycle.Event.ON_STOP) {
                handler.removeCallbacks(poll);
            } else if (event == Lifecycle.Event.ON_DESTROY) {
                handler.removeCallbacksAndMessages(null);
                PiLink.release(pi);
            }
        });
    }

    private void fetchOnce() {
        if (fetching || !pi.isConfigured()) {
            return;
        }
        fetching = true;
        new Thread(() -> {
            Telemetry fetched = null;
            try {
                fetched = Telemetry.from(pi.telemetry());
            } catch (Exception ignored) {
                // Offline: keep the previous reading rather than blanking the screen.
            } finally {
                fetching = false;
            }
            if (fetched != null) {
                latest = fetched;
                handler.post(Mx5CarScreen.this::invalidate);
            }
        }, "car-poll").start();
    }

    @NonNull
    @Override
    public Template onGetTemplate() {
        Telemetry t = latest;
        // Re-read every time rather than caching at session start: the units toggle
        // lives on the phone, and a stale copy here would show mph until the car
        // session is restarted. SharedPreferences reads are served from memory.
        boolean mph = prefs.getBoolean("use_mph", true);
        String unit = mph ? "mph" : "km/h";

        Pane pane = new Pane.Builder()
                .addRow(row(value(t == null ? null : Math.round(t.speedFor(mph ? 1 : 0)) + " " + unit),
                           "Speed"))
                .addRow(row(value(t == null ? null : String.valueOf(t.rpm)), "RPM"))
                .addRow(row(value(t == null ? null : gearText(t)), "Gear"))
                .addRow(row(value(t == null ? null : t.coolantTempF + " \u00b0F"), "Coolant"))
                .addRow(row(value(t == null ? null : Math.round(t.fuelLevelPercent) + "%"), "Fuel"))
                .addRow(row(value(t == null ? null : t.rangeMiles + " mi"), "Range"))
                .addRow(row(value(t == null ? null : String.format("%.1f V", t.voltage)), "Battery"))
                .addRow(row(value(t == null ? null : Math.round(t.averageMpg) + " mpg"), "Average"))
                .build();

        return new PaneTemplate.Builder(pane)
                .setTitle("MX5")
                .setHeaderAction(Action.APP_ICON)
                .build();
    }

    private static String value(String v) {
        return v == null ? "--" : v;
    }

    /** Value first, label second: the host draws the title large. */
    private static Row row(String value, String label) {
        return new Row.Builder()
                .setTitle(value)
                .addText(label)
                .build();
    }

    private static String gearText(Telemetry t) {
        if (t.inNeutral) {
            return "N";
        }
        if (t.inReverse) {
            return "R";
        }
        return t.gear <= 0 ? "--" : String.valueOf(t.gear);
    }
}
