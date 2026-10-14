package com.mx5.remote;

import java.io.BufferedReader;
import java.io.IOException;
import java.io.InputStream;
import java.io.InputStreamReader;
import java.io.OutputStream;
import java.net.HttpURLConnection;
import java.net.URL;
import java.nio.charset.StandardCharsets;

/**
 * The Pi's Flask server over the USB tether.
 *
 * Only HttpURLConnection and org.json, both platform classes, so the app still resolves no
 * third party dependencies at all. Timeouts are deliberately short: the Pi is a few
 * microseconds away on a tether, so anything slower is a fault and the UI is better off
 * showing "offline" quickly than hanging. That matters more now than it did, because a
 * slow tether timeout is time the fallback to Bluetooth has to wait.
 */
final class HttpTransport implements LinkTransport {

    private static final int CONNECT_TIMEOUT_MS = 1500;
    private static final int READ_TIMEOUT_MS = 1500;

    private String baseUrl = "";
    private String token = "";

    void configure(String baseUrl, String token) {
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

    String baseUrl() {
        return baseUrl;
    }

    @Override
    public String label() {
        return "USB tether";
    }

    @Override
    public boolean isReady() {
        return !baseUrl.isEmpty();
    }

    @Override
    public String unavailableReason() {
        return baseUrl.isEmpty() ? "No Pi address set" : "";
    }

    @Override
    public void onFailure() {
        // Stateless: every request opens its own connection, so there is nothing to drop.
    }

    @Override
    public void close() {
        // Nothing held open.
    }

    @Override
    public String request(String method, String path, String body) throws IOException {
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
                // We got an answer, so the transport worked and the server said no. Thrown
                // as Refused so this never counts as a reason to fall back to Bluetooth.
                throw new LinkTransport.Refused(
                        "HTTP " + code + (text.isEmpty() ? "" : ": " + text));
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
