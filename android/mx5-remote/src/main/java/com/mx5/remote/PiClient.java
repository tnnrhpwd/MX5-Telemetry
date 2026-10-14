package com.mx5.remote;

import org.json.JSONException;
import org.json.JSONObject;

import java.io.BufferedReader;
import java.io.IOException;
import java.io.InputStream;
import java.io.InputStreamReader;
import java.io.OutputStream;
import java.net.HttpURLConnection;
import java.net.URL;
import java.nio.charset.StandardCharsets;

/**
 * Talks to the Pi's Flask server over the USB tether.
 *
 * Only HttpURLConnection and org.json, both platform classes, so the app resolves
 * no third party dependencies at all. Timeouts are deliberately short: the Pi is a
 * few microseconds away on a tether, so anything slower is a fault and the UI is
 * better off showing "offline" quickly than hanging.
 */
public final class PiClient {

    private static final int CONNECT_TIMEOUT_MS = 1500;
    private static final int READ_TIMEOUT_MS = 1500;

    private String baseUrl = "";

    public void configure(String baseUrl, String token) {
        String b = baseUrl == null ? "" : baseUrl.trim();
        if (b.endsWith("/")) {
            b = b.substring(0, b.length() - 1);
        }
        if (!b.isEmpty() && !b.startsWith("http://") && !b.startsWith("https://")) {
            b = "http://" + b;
        }
        this.baseUrl = b;
        this.token = token == null ? "" : token.trim();
    }

    private String token = "";

    public String baseUrl() {
        return baseUrl;
    }

    public boolean isConfigured() {
        return !baseUrl.isEmpty();
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

    private String request(String method, String path, String body) throws IOException {
        if (baseUrl.isEmpty()) {
            throw new IOException("No Pi address configured");
        }
        HttpURLConnection conn = null;
        try {
            conn = (HttpURLConnection) new URL(baseUrl + path).openConnection();
            conn.setRequestMethod(method);
            conn.setConnectTimeout(CONNECT_TIMEOUT_MS);
            conn.setReadTimeout(READ_TIMEOUT_MS);
            conn.setRequestProperty("Accept", "application/json");
            if (!token.isEmpty()) {
                conn.setRequestProperty("Authorization", "Bearer " + token);
            }
            if (body != null) {
                conn.setDoOutput(true);
                conn.setRequestProperty("Content-Type", "application/json");
                byte[] payload = body.getBytes(StandardCharsets.UTF_8);
                conn.setFixedLengthStreamingMode(payload.length);
                try (OutputStream out = conn.getOutputStream()) {
                    out.write(payload);
                }
            }
            int code = conn.getResponseCode();
            InputStream stream = code >= 400 ? conn.getErrorStream() : conn.getInputStream();
            String text = read(stream);
            if (code >= 400) {
                throw new IOException("HTTP " + code + (text.isEmpty() ? "" : ": " + text));
            }
            return text.isEmpty() ? "{}" : text;
        } finally {
            if (conn != null) {
                conn.disconnect();
            }
        }
    }

    private static String read(InputStream in) throws IOException {
        if (in == null) {
            return "";
        }
        StringBuilder sb = new StringBuilder();
        try (BufferedReader r = new BufferedReader(new InputStreamReader(in, StandardCharsets.UTF_8))) {
            String line;
            while ((line = r.readLine()) != null) {
                sb.append(line);
            }
        }
        return sb.toString();
    }
}
