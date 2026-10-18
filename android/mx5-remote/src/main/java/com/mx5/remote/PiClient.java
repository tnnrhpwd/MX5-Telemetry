package com.mx5.remote;

import android.content.Context;
import android.util.Log;

import org.json.JSONException;
import org.json.JSONObject;

import java.io.IOException;
import java.util.ArrayList;
import java.util.Collections;
import java.util.List;

/**
 * Talks to the Pi, over whichever transport currently works.
 *
 * The tether is tried first because it is fastest and charges the phone. If it is not
 * there, the Bluetooth transports take over, SPP before BLE. Whichever worked is
 * remembered, so the common case is a single attempt; only after that transport fails is
 * the rest of the chain re-tried.
 *
 * Every public method here is unchanged from when this was HTTP only, so no screen had to
 * be touched when Bluetooth was added. All of the transport choice is in request().
 */
public final class PiClient {

    /** How long to stop trying after every transport has failed, before escalation. */
    private static final long FAIL_BACKOFF_MIN_MS = 2000;

    /**
     * Ceiling for the "everything failed" backoff.
     *
     * This used to be a flat 4s. A link that had genuinely gone away was then re-walked
     * every 4s for ever, and every walk paid the tether's connect timeout plus a
     * connectGatt(), which is exactly the hammering that leaves Android's Bluetooth stack
     * refusing new connections until the app is restarted. It grows now and resets the
     * moment anything works.
     */
    private static final long FAIL_BACKOFF_MAX_MS = 20000;

    /**
     * How long a single transport sits out after it fails.
     *
     * Two things went wrong without this. A phone with no USB tether paid the 1.5s connect
     * timeout on the tether on every single chain walk, because the tether address is
     * always configured. And one dropped Bluetooth exchange cleared the sticky transport,
     * so the next request had to lose that same 1.5s before retrying the link that had
     * merely hiccuped. Both made a working link feel broken. The skip grows while a
     * transport keeps failing and is dropped the moment it answers.
     */
    private static final long COOLDOWN_MIN_MS = 10000;
    private static final long COOLDOWN_MAX_MS = 60000;

    /**
     * Why each transport failed is logged, not just stored.
     *
     * There was no logging in this app at all, so a link that failed left nothing behind
     * anywhere: no message on the screen, and nothing in logcat to read from a laptop.
     * That is the whole reason a failure here took an HCI capture to diagnose.
     */
    private static final String TAG = "MX5Link";

    private final HttpTransport http = new HttpTransport();
    private final List<LinkTransport> chain = new ArrayList<>();
    private SppTransport spp;
    private BleTransport ble;
    private String token = "";

    /** The transport that last worked. Tried first, so the normal case costs one attempt. */
    private volatile LinkTransport active;

    /** Set when everything failed, so a poll loop does not hammer dead links. */
    private volatile long retryAfter;
    private volatile String lastError = "";

    /**
     * Per-transport failure memory, keyed by identity.
     *
     * Identity, not equals: these are the three singletons in the chain and nothing else
     * is ever used as a key.
     */
    private final java.util.IdentityHashMap<LinkTransport, Health> health =
            new java.util.IdentityHashMap<>();

    private static final class Health {
        long skipUntil;
        int failures;
    }

    /** Consecutive "nothing reached the Pi" results, used to escalate the backoff. */
    private int failStreak;

    private boolean allowed(LinkTransport t) {
        synchronized (health) {
            Health h = health.get(t);
            return h == null || System.currentTimeMillis() >= h.skipUntil;
        }
    }

    private void markGood(LinkTransport t) {
        synchronized (health) {
            health.remove(t);
        }
        failStreak = 0;
    }

    private void markBad(LinkTransport t) {
        synchronized (health) {
            Health h = health.get(t);
            if (h == null) {
                h = new Health();
                health.put(t, h);
            }
            h.failures++;
            long delay = COOLDOWN_MIN_MS << Math.min(h.failures - 1, 3);
            if (delay > COOLDOWN_MAX_MS) {
                delay = COOLDOWN_MAX_MS;
            }
            h.skipUntil = System.currentTimeMillis() + delay;
        }
    }

    public void configure(String baseUrl, String token) {
        http.configure(baseUrl, token);
        this.token = token == null ? "" : token.trim();
        rebuildChain();
    }

    /**
     * Enable the Bluetooth half of the chain.
     *
     * Separate from configure() because it needs a Context and a device source, neither of
     * which the HTTP path has any use for.
     */
    public void setBluetooth(Context context, BtTransport.DeviceSource devices, String token) {
        this.token = token == null ? "" : token.trim();
        this.spp = new SppTransport(this.token, devices);
        this.ble = new BleTransport(context, this.token, devices);
        rebuildChain();
        active = null;
        retryAfter = 0;
    }

    /**
     * Whether the Bluetooth half of the chain exists yet.
     *
     * A second activity instance shares this client, and must not rebuild the transports:
     * that would drop the one already carrying the link and abandon its connection.
     */
    public boolean bluetoothConfigured() {
        return ble != null;
    }

    private void rebuildChain() {
        chain.clear();
        chain.add(http);
        if (spp != null) {
            chain.add(spp);
        }
        if (ble != null) {
            chain.add(ble);
        }
    }

    public String baseUrl() {
        return http.baseUrl();
    }

    /** True if there is anything to try: an address, or a paired Pi for Bluetooth. */
    public boolean isConfigured() {
        for (LinkTransport t : chain) {
            if (t.isReady()) {
                return true;
            }
        }
        return false;
    }

    /** Label of the transport currently in use, or "" before anything has worked. */
    public String activeTransport() {
        LinkTransport t = active;
        return t == null ? "" : t.label();
    }

    /** One line per transport: what it is and whether it can be used. */
    public List<String> transportReport() {
        List<String> out = new ArrayList<>();
        for (LinkTransport t : chain) {
            boolean isActive = t == active;
            String state = t.isReady() ? (isActive ? "in use" : "available") : t.unavailableReason();
            // A colon, not an em dash: the house style forbids an em dash in anything a
            // person reads, and this is rendered on the System screen.
            out.add(t.label() + ": " + state);
        }
        if (out.isEmpty()) {
            out.add("No transports configured");
        }
        // Why the last attempt failed. A transport can report itself ready and still fail
        // to open on every try, and without this line the screen showed OFFLINE with no
        // reason anywhere: the exception was caught, stored, and never read.
        if (!lastError.isEmpty()) {
            out.add("Last error: " + lastError);
        }
        return Collections.unmodifiableList(out);
    }

    /** Why the last attempt failed, or "" if the last one worked. */
    public String lastError() {
        return lastError;
    }

    /** Forget which transport worked, so the chain is walked from the top again. */
    public void resetTransports() {
        active = null;
        retryAfter = 0;
        lastError = "";
        failStreak = 0;
        synchronized (health) {
            health.clear();
        }
    }

    /**
     * Forget the recovery timers because the user is looking at the screen again.
     *
     * Coming back into view is a fresh start: the Pi may have been power-cycled while the
     * app was hidden, and making the first poll after a resume wait out a backoff that
     * built up in the background is the sort of thing that reads as "the app is stuck and
     * needs reopening". Keeps the sticky transport, so an already-good Bluetooth link is
     * still used first.
     */
    public void clearBackoff() {
        retryAfter = 0;
        failStreak = 0;
        synchronized (health) {
            health.clear();
        }
    }

    public void close() {
        for (LinkTransport t : chain) {
            try {
                t.close();
            } catch (Exception ignored) {
                // Nothing useful to do while shutting down.
            }
        }
        active = null;
    }

    public JSONObject status() throws IOException, JSONException {
        return new JSONObject(request("GET", "/api/status", null));
    }

    public JSONObject telemetry() throws IOException, JSONException {
        return new JSONObject(request("GET", "/api/telemetry", null));
    }

    public JSONObject roofStatus() throws IOException, JSONException {
        return new JSONObject(request("GET", "/api/roof/status", null));
    }

    public JSONObject setScreen(int screen) throws IOException, JSONException {
        return new JSONObject(request("POST", "/api/screen/" + screen, "{}"));
    }

    public JSONObject stepScreen(boolean forward) throws IOException, JSONException {
        return new JSONObject(request("POST", forward ? "/api/screen/next" : "/api/screen/prev", "{}"));
    }

    public JSONObject updateSetting(String name, Object value) throws IOException, JSONException {
        JSONObject body = new JSONObject();
        body.put("name", name);
        body.put("value", value);
        return new JSONObject(request("POST", "/api/settings/update", body.toString()));
    }

    public JSONObject roofSpeed(int mph) throws IOException, JSONException {
        return roofCommand("/api/roof/speed", mph);
    }

    public JSONObject roofAuto(int on) throws IOException, JSONException {
        return roofCommand("/api/roof/auto", on);
    }

    public JSONObject roofMode(int mode) throws IOException, JSONException {
        return roofCommand("/api/roof/mode", mode);
    }

    public JSONObject roofConnect() throws IOException, JSONException {
        return new JSONObject(request("POST", "/api/roof/connect", "{}"));
    }

    public JSONObject roofDisconnect() throws IOException, JSONException {
        return new JSONObject(request("POST", "/api/roof/disconnect", "{}"));
    }

    private JSONObject roofCommand(String path, int value) throws IOException, JSONException {
        JSONObject body = new JSONObject();
        body.put("value", value);
        return new JSONObject(request("POST", path, body.toString()));
    }

    public JSONObject calibrateImu() throws IOException, JSONException {
        return new JSONObject(request("POST", "/api/calibrate_imu", "{}"));
    }

    public JSONObject wake() throws IOException, JSONException {
        return new JSONObject(request("POST", "/api/wake", "{}"));
    }

    /**
     * One request, over the first transport that answers.
     *
     * A Refused is rethrown immediately and never causes fallback: the Pi answered, so the
     * transport is fine, and moving to a slower one because a value was out of range would
     * be both wrong and invisible.
     *
     * Synchronized, because more than one caller reaches this at once: the poll loop, the
     * refresh on resume, and the roof refresh each run on their own thread. That was fine
     * while there was one HTTP client per request, but a Bluetooth transport owns one
     * connection for the whole session. Three concurrent calls meant three connectGatt()
     * calls on one peripheral, and Android then refused the next write with status 201
     * (GATT write request busy) because another client still held the connection.
     */
    private synchronized String request(String method, String path, String body) throws IOException {
        if (System.currentTimeMillis() < retryAfter) {
            // Still backing off from a total failure; fail fast rather than re-walking the
            // whole chain on every poll.
            throw new IOException(lastError.isEmpty() ? "Waiting to retry" : lastError);
        }

        IOException failure = null;

        LinkTransport sticky = active;
        if (sticky != null && sticky.isReady()) {
            try {
                String out = sticky.request(method, path, body);
                if (retryAfter != 0) {
                    retryAfter = 0;
                }
                return out;
            } catch (LinkTransport.Refused e) {
                throw e;
            } catch (IOException e) {
                Log.w(TAG, sticky.label() + " failed: " + e);
                sticky.onFailure();
                markBad(sticky);
                active = null;
                failure = e;
            }
        }

        // Prefer transports that are not sitting out a cooldown. If every remaining
        // candidate is cooling down, ignore the cooldowns instead of declaring the Pi
        // unreachable: that is the difference between recovering slowly and staying dead
        // until the app is restarted.
        List<LinkTransport> ready = new ArrayList<>();
        List<LinkTransport> cooling = new ArrayList<>();
        for (LinkTransport t : chain) {
            if (t == sticky || !t.isReady()) {
                continue;
            }
            if (allowed(t)) {
                ready.add(t);
            } else {
                cooling.add(t);
            }
        }
        if (ready.isEmpty()) {
            ready.addAll(cooling);
        }

        for (LinkTransport t : ready) {
            try {
                String out = t.request(method, path, body);
                active = t;
                retryAfter = 0;
                lastError = "";
                markGood(t);
                return out;
            } catch (LinkTransport.Refused e) {
                // It answered, so it works. Remember it and let the refusal through.
                active = t;
                retryAfter = 0;
                lastError = "";
                markGood(t);
                throw e;
            } catch (IOException e) {
                Log.w(TAG, t.label() + " failed: " + e);
                t.onFailure();
                markBad(t);
                if (failure == null) {
                    failure = e;
                }
            }
        }

        lastError = failure == null
                ? "No way to reach the Pi: " + firstUnavailableReason()
                : failure.getMessage();

        // The tether's error is always the one reported, because the tether is first in
        // the chain and its exception is therefore the first failure recorded. On a phone
        // that is simply not tethered, that message says "failed to connect to
        // 192.168.42.100 after 1500ms" and buries the fact that Bluetooth has no paired Pi
        // to fall back on, which is the one thing the user could act on.
        String btWhy = bluetoothUnavailableReason();
        if (!btWhy.isEmpty()) {
            lastError = lastError + " | Bluetooth: " + btWhy;
        }

        Log.w(TAG, "no transport reached the Pi; last error: " + lastError);

        // Escalate. Consecutive total failures mean the Pi is genuinely away, and retrying
        // it every couple of seconds is what makes the Bluetooth stack stop accepting
        // connections.
        int streak = ++failStreak;
        long backoff = FAIL_BACKOFF_MIN_MS << Math.min(streak - 1, 4);
        if (backoff > FAIL_BACKOFF_MAX_MS) {
            backoff = FAIL_BACKOFF_MAX_MS;
        }
        retryAfter = System.currentTimeMillis() + backoff;
        throw failure != null ? failure : new IOException(lastError);
    }

    private String firstUnavailableReason() {
        for (LinkTransport t : chain) {
            String why = t.unavailableReason();
            if (!why.isEmpty()) {
                return why;
            }
        }
        return "nothing is configured";
    }

    /**
     * Why Bluetooth cannot help right now, or "" if it can.
     *
     * Only consulted when every transport has already failed, so it never costs anything
     * on the working path.
     */
    private String bluetoothUnavailableReason() {
        for (LinkTransport t : chain) {
            if (t instanceof HttpTransport) {
                continue;
            }
            if (!t.isReady()) {
                String why = t.unavailableReason();
                if (!why.isEmpty()) {
                    return why;
                }
            }
        }
        return "";
    }
}
