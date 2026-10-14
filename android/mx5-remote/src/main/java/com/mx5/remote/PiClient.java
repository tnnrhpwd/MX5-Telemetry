package com.mx5.remote;

import android.content.Context;

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

    /** How long to stop trying after every transport has failed. */
    private static final long FAIL_BACKOFF_MS = 4000;

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
        return Collections.unmodifiableList(out);
    }

    /** Forget which transport worked, so the chain is walked from the top again. */
    public void resetTransports() {
        active = null;
        retryAfter = 0;
        lastError = "";
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
     */
    private String request(String method, String path, String body) throws IOException {
        if (System.currentTimeMillis() < retryAfter) {
            // Still backing off from a total failure; fail fast rather than re-walking the
            // whole chain on every poll.
            throw new IOException(lastError.isEmpty() ? "Waiting to retry" : lastError);
        }

        IOException failure = null;

        LinkTransport sticky = active;
        if (sticky != null && sticky.isReady()) {
            try {
                return sticky.request(method, path, body);
            } catch (LinkTransport.Refused e) {
                throw e;
            } catch (IOException e) {
                sticky.onFailure();
                active = null;
                failure = e;
            }
        }

        for (LinkTransport t : chain) {
            if (t == sticky || !t.isReady()) {
                continue;
            }
            try {
                String out = t.request(method, path, body);
                active = t;
                retryAfter = 0;
                lastError = "";
                return out;
            } catch (LinkTransport.Refused e) {
                // It answered, so it works. Remember it and let the refusal through.
                active = t;
                retryAfter = 0;
                lastError = "";
                throw e;
            } catch (IOException e) {
                t.onFailure();
                if (failure == null) {
                    failure = e;
                }
            }
        }

        lastError = failure == null
                ? "No way to reach the Pi: " + firstUnavailableReason()
                : failure.getMessage();
        retryAfter = System.currentTimeMillis() + FAIL_BACKOFF_MS;
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
}
