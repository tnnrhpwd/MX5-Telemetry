package com.mx5.remote;

import java.io.IOException;

/**
 * One way of reaching the Pi.
 *
 * Three implementations: the USB tether (HTTP), Bluetooth SPP, and Bluetooth LE. They are
 * not equivalent, so the chain is ordered: the tether is preferred because it is fast and
 * charges the phone, SPP next because a reply is a single write, BLE last because a reply
 * has to be chunked to the negotiated MTU.
 *
 * Requests are expressed the way the HTTP API expresses them, because that is what the
 * screens already speak. The Bluetooth transports translate a path into a protocol op
 * internally, so nothing above this interface had to change when Bluetooth was added.
 */
interface LinkTransport {

    /** Short label for the System screen, e.g. "USB tether". */
    String label();

    /** Whether this transport could be attempted right now. */
    boolean isReady();

    /** Why isReady() is false, for the System screen. Empty when it is ready. */
    String unavailableReason();

    /**
     * Perform one request and return the response body as JSON text.
     *
     * Throws IOException for anything that went wrong, whether that is a dead socket, a
     * refused token, or a command the Pi rejected.
     */
    String request(String method, String path, String body) throws IOException;

    /** A request just failed, so drop any connection that may now be dead. */
    void onFailure();

    /** Release resources. Safe to call more than once. */
    void close();

    /**
     * The exchange completed and the Pi refused the command.
     *
     * This must never cause a fallback to another transport. "The Pi said no" and "I could
     * not reach the Pi" are different, and treating a refusal as a transport failure would
     * silently move a working link to a slower one every time a value was out of range.
     * An HTTP status code counts as a refusal too: the server answered, so the transport
     * is fine.
     */
    class Refused extends IOException {
        public Refused(String message) {
            super(message);
        }
    }
}
