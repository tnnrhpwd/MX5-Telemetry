package com.mx5.remote;

import android.bluetooth.BluetoothDevice;
import android.bluetooth.BluetoothGatt;
import android.bluetooth.BluetoothGattCallback;
import android.bluetooth.BluetoothGattCharacteristic;
import android.bluetooth.BluetoothGattDescriptor;
import android.bluetooth.BluetoothProfile;
import android.content.Context;
import android.os.Build;
import android.util.Log;

import java.io.IOException;
import java.util.UUID;
import java.util.concurrent.CountDownLatch;
import java.util.concurrent.TimeUnit;

/**
 * Bluetooth LE (GATT) as the fallback of the fallback.
 *
 * It exists because SPP's weak point is the SDP service record, which BlueZ has been
 * moving out of `sdptool`, and GATT has no SDP to lose. The cost is that a reply has to be
 * chunked to the negotiated MTU: a telemetry snapshot is roughly a kilobyte, so one poll
 * becomes several notifications. That is why SPP is tried first.
 *
 * Incoming notifications are fed straight into the shared line queue, so a reply split
 * across several of them reassembles without this class knowing or caring.
 */
final class BleTransport extends BtTransport {

    // Must match pi/ui/src/bt_ble_server.py.
    static final UUID SERVICE_UUID = UUID.fromString("6d783500-0001-4d58-3535-4d583554454c");
    static final UUID RX_UUID = UUID.fromString("6d783500-0002-4d58-3535-4d583554454c");
    static final UUID TX_UUID = UUID.fromString("6d783500-0003-4d58-3535-4d583554454c");

    /** The standard Client Characteristic Configuration descriptor, for enabling notify. */
    private static final UUID CCCD = UUID.fromString("00002902-0000-1000-8000-00805f9b34fb");

    /** Diagnostics. This transport had no logging at all, so a refused write said nothing. */
    private static final String TAG = "MX5Ble";

    private static final long OPEN_TIMEOUT_MS = 8000;
    private static final long WRITE_TIMEOUT_MS = 2000;

    /** BluetoothStatusCodes.ERROR_GATT_WRITE_REQUEST_BUSY: another write is outstanding. */
    private static final int GATT_WRITE_REQUEST_BUSY = 201;

    /**
     * Write commands, not write requests.
     *
     * A write *request* holds the connection's single GATT operation slot until its own
     * onCharacteristicWrite arrives, and on this phone that callback never arrives at all:
     * an HCI capture shows the write completing on the air and the Pi answering it, while
     * the app is never told. The connection therefore stayed busy for ever after the first
     * chunk, and every later chunk was refused with 201 no matter how long it retried.
     *
     * A write *command* needs no acknowledgement, so nothing is left outstanding and the
     * next chunk can follow. The Pi's reply to the request is what confirms the bytes
     * arrived, and request() already waits for exactly that. The Pi's RX characteristic
     * accepts both write types so a client that prefers requests still works.
     */
    private static final int WRITE_TYPE = BluetoothGattCharacteristic.WRITE_TYPE_NO_RESPONSE;

    /** Pause between chunks while the stack releases the previous write. */
    private static final long WRITE_PACING_MS = 20;

    /** Ask for a large MTU so telemetry needs fewer round trips. */
    private static final int WANTED_MTU = 517;

    private final Context context;
    private final DeviceSource devices;

    private BluetoothGatt gatt;
    private BluetoothGattCharacteristic rx;
    private BluetoothGattCharacteristic tx;
    private int mtu = 23;
    private volatile boolean connected;

    // Assigned by the connecting thread and read by the GATT callbacks on a binder thread,
    // so these have to be volatile: without it a callback can look at a latch before it is
    // assigned, do nothing, and leave the waiter to time out on an operation that in fact
    // completed.
    private volatile CountDownLatch connectLatch;
    private volatile CountDownLatch servicesLatch;
    private volatile CountDownLatch descriptorLatch;
    private volatile CountDownLatch mtuLatch;
    private volatile CountDownLatch writeLatch;

    // Statuses from the callbacks. Android runs one operation per connection at a time, so
    // one slot each is enough, but the status has to be kept: a discovery or a descriptor
    // write that fails still fires its callback, and treating that as success is how a
    // dead link gets reported as a working one.
    private volatile int servicesStatus = BluetoothGatt.GATT_FAILURE;
    private volatile int descriptorStatus = BluetoothGatt.GATT_FAILURE;
    private volatile int writeStatus = BluetoothGatt.GATT_FAILURE;

    BleTransport(Context context, String token, DeviceSource devices) {
        super(token);
        this.context = context.getApplicationContext();
        this.devices = devices;
    }

    @Override
    public String label() {
        return "Bluetooth LE";
    }

    @Override
    public boolean isReady() {
        return devices.device() != null;
    }

    @Override
    public String unavailableReason() {
        return devices.reason();
    }

    @Override
    protected boolean isOpen() {
        return connected && gatt != null;
    }

    // -- connect ------------------------------------------------------------

    @Override
    protected void open() throws IOException {
        BluetoothDevice device = devices.device();
        if (device == null) {
            throw new IOException(devices.reason());
        }

        clearReceived();
        mtu = 23;
        connectLatch = new CountDownLatch(1);
        servicesLatch = new CountDownLatch(1);
        servicesStatus = BluetoothGatt.GATT_FAILURE;
        descriptorStatus = BluetoothGatt.GATT_FAILURE;
        connected = false;

        // Drop any previous connection before opening another. Leaving one behind leaves a
        // second GATT client on the same peripheral, which Android answers by refusing the
        // next write with status 201 and by delivering the old client's callbacks here.
        closeGatt();

        try {
            // autoConnect=false: a direct connection to an already-bonded device, which
            // also means no scanning and therefore no scan permission.
            gatt = device.connectGatt(context, false, callback);
        } catch (SecurityException e) {
            throw new IOException("Bluetooth permission denied", e);
        }
        if (gatt == null) {
            throw new IOException("Could not open a GATT connection");
        }

        if (!await(connectLatch, OPEN_TIMEOUT_MS)) {
            closePipe();
            throw new IOException("BLE connect timed out");
        }
        if (!connected) {
            closePipe();
            throw new IOException("BLE connection was refused");
        }

        if (!gatt.discoverServices() || !await(servicesLatch, OPEN_TIMEOUT_MS)) {
            closePipe();
            throw new IOException("BLE service discovery failed");
        }
        if (servicesStatus != BluetoothGatt.GATT_SUCCESS) {
            int status = servicesStatus;
            closePipe();
            throw new IOException("BLE service discovery failed (status " + status + ")");
        }

        rx = findCharacteristic(SERVICE_UUID, RX_UUID);
        tx = findCharacteristic(SERVICE_UUID, TX_UUID);
        Log.d(TAG, "discovered: rx=" + (rx != null) + " tx=" + (tx != null));
        if (rx == null || tx == null) {
            closePipe();
            throw new IOException("The Pi's BLE service was not found: is the Bluetooth "
                    + "link running on the Pi?");
        }

        enableNotifications(tx);

        // Deliberately no requestMtu() here.
        //
        // The Pi asks for a large MTU itself the moment a central connects, and Android
        // reports the result through onMtuChanged, so asking cost nothing and bought
        // nothing: an HCI capture showed zero MTU requests from this side on every
        // connection while the link still ended up at 517. What it did do was sit between
        // the subscribe and the first write, and the write that followed it never reported
        // completion. A smaller MTU only costs more notifications, and the line protocol
        // already tolerates a reply split across several of them.
    }

    private BluetoothGattCharacteristic findCharacteristic(UUID service, UUID characteristic) {
        if (gatt.getService(service) == null) {
            return null;
        }
        return gatt.getService(service).getCharacteristic(characteristic);
    }

    /**
     * Wait on a callback latch, turning an interrupt into an IOException.
     *
     * The GATT callback arrives on a binder thread, so the only way to write this as a
     * straight line of code is to wait on a latch, and CountDownLatch.await is one of the
     * few things here that throws a checked exception.
     */
    private static boolean await(CountDownLatch latch, long timeoutMs) throws IOException {
        try {
            return latch.await(timeoutMs, TimeUnit.MILLISECONDS);
        } catch (InterruptedException e) {
            Thread.currentThread().interrupt();
            throw new IOException("Interrupted while connecting over BLE", e);
        }
    }

    @SuppressWarnings("deprecation")
    private void enableNotifications(BluetoothGattCharacteristic c) throws IOException {
        if (!gatt.setCharacteristicNotification(c, true)) {
            throw new IOException("Could not subscribe to the Pi's replies");
        }
        BluetoothGattDescriptor cccd = c.getDescriptor(CCCD);
        if (cccd == null) {
            throw new IOException("The Pi's reply characteristic has no CCCD descriptor");
        }

        descriptorLatch = new CountDownLatch(1);
        descriptorStatus = BluetoothGatt.GATT_FAILURE;
        byte[] enable = BluetoothGattDescriptor.ENABLE_NOTIFICATION_VALUE;
        boolean accepted;
        if (Build.VERSION.SDK_INT >= Build.VERSION_CODES.TIRAMISU) {
            accepted = gatt.writeDescriptor(cccd, enable) == BluetoothGatt.GATT_SUCCESS;
        } else {
            cccd.setValue(enable);
            accepted = gatt.writeDescriptor(cccd);
        }
        if (!accepted) {
            throw new IOException("Could not enable reply notifications");
        }

        // Wait for the descriptor write. Until its callback arrives the connection stays
        // busy, so the next operation, which is the first request, would be dropped.
        if (!await(descriptorLatch, WRITE_TIMEOUT_MS)) {
            throw new IOException("Timed out enabling reply notifications");
        }
        int status = descriptorStatus;
        if (status != BluetoothGatt.GATT_SUCCESS) {
            throw new IOException(
                    "Could not enable reply notifications (status " + status + ")");
        }
    }

    // -- io -----------------------------------------------------------------

    @SuppressWarnings("deprecation")
    @Override
    protected void send(byte[] data) throws IOException {
        BluetoothGatt g = gatt;
        BluetoothGattCharacteristic c = rx;
        if (g == null || c == null) {
            throw new IOException("BLE link is not open");
        }

        // Three bytes go to the ATT header, so anything larger is rejected.
        int chunk = Math.max(20, mtu - 3);
        Log.d(TAG, "send " + data.length + " bytes, mtu=" + mtu + ", chunk=" + chunk);
        for (int off = 0; off < data.length; off += chunk) {
            int len = Math.min(chunk, data.length - off);
            byte[] part = new byte[len];
            System.arraycopy(data, off, part, 0, len);
            writeChunk(g, c, part, off);
        }
    }

    /**
     * Write one chunk, retrying while Android reports the connection busy.
     *
     * Deliberately does not wait for onCharacteristicWrite. An HCI capture showed the write
     * completes on the air: the Pi answers it with an ATT Write Response and with the reply
     * to the request, and onCharacteristicChanged delivers that reply. That one callback
     * just never arrives, while onDescriptorWrite, onServicesDiscovered and
     * onConnectionStateChange all do, so waiting on it turned a working write into
     * "BLE write timed out" and then into a reconnect. The reply is the real proof a request
     * landed, and request() already waits for it.
     *
     * Pacing is still needed, because the stack can still be releasing the previous bytes.
     * Retrying on ERROR_GATT_WRITE_REQUEST_BUSY covers that without needing a callback.
     */
    private void writeChunk(BluetoothGatt g, BluetoothGattCharacteristic c, byte[] part,
                            int off) throws IOException {
        long deadline = System.currentTimeMillis() + WRITE_TIMEOUT_MS;
        while (true) {
            int code;
            if (Build.VERSION.SDK_INT >= Build.VERSION_CODES.TIRAMISU) {
                code = g.writeCharacteristic(c, part, WRITE_TYPE);
            } else {
                c.setWriteType(WRITE_TYPE);
                c.setValue(part);
                code = g.writeCharacteristic(c) ? BluetoothGatt.GATT_SUCCESS : -1;
            }
            if (code == BluetoothGatt.GATT_SUCCESS) {
                return;
            }
            if (code != GATT_WRITE_REQUEST_BUSY) {
                // The code matters: Android refuses a GATT write with a status that says why,
                // and a generic message threw that away.
                Log.w(TAG, "writeCharacteristic refused: code=" + code + " partLen="
                        + part.length + " off=" + off);
                throw new IOException("The Pi would not accept a BLE write (code " + code + ")");
            }
            if (System.currentTimeMillis() > deadline) {
                Log.w(TAG, "write stayed busy for " + WRITE_TIMEOUT_MS + "ms, off=" + off);
                throw new IOException("The Pi would not accept a BLE write (stayed busy)");
            }
            try {
                Thread.sleep(WRITE_PACING_MS);
            } catch (InterruptedException e) {
                Thread.currentThread().interrupt();
                throw new IOException("Interrupted during a BLE write", e);
            }
        }
    }

    /** Close the current GATT client, if there is one, without touching the latches. */
    private void closeGatt() {
        BluetoothGatt g = gatt;
        gatt = null;
        rx = null;
        tx = null;
        if (g != null) {
            try {
                g.disconnect();
            } catch (Exception ignored) {
                // already gone
            }
            try {
                g.close();
            } catch (Exception ignored) {
                // already gone
            }
        }
    }

    @Override
    protected void closePipe() {
        Log.d(TAG, "closePipe, connected was " + connected);
        connected = false;
        // Release anything waiting inside open(). A connection that has ended must unblock
        // those waits rather than leave them to time out, and the statuses are cleared so
        // that whatever is waiting reports a failure rather than a stale success.
        writeStatus = BluetoothGatt.GATT_FAILURE;
        descriptorStatus = BluetoothGatt.GATT_FAILURE;
        servicesStatus = BluetoothGatt.GATT_FAILURE;
        signal(connectLatch);
        signal(servicesLatch);
        signal(descriptorLatch);
        signal(mtuLatch);
        signal(writeLatch);
        closeGatt();
        clearReceived();
    }

    // -- callbacks ----------------------------------------------------------

    private final BluetoothGattCallback callback = new BluetoothGattCallback() {

        /**
         * True when this callback belongs to the connection currently in use.
         *
         * The operation latches are per-attempt, so a callback from a connection that has
         * already been replaced would satisfy the *new* attempt's latch and let it continue
         * on an operation that never happened. That is visible in the trace as "discovered"
         * one millisecond after connecting.
         */
        private boolean isCurrent(BluetoothGatt g) {
            if (g != gatt) {
                Log.d(TAG, "ignoring a callback from a superseded connection");
                return false;
            }
            return true;
        }

        @Override
        public void onConnectionStateChange(BluetoothGatt g, int status, int newState) {
            Log.d(TAG, "onConnectionStateChange status=" + status + " newState=" + newState);
            if (!isCurrent(g)) {
                return;
            }
            connected = newState == BluetoothProfile.STATE_CONNECTED;
            if (!connected) {
                // Unblocks a pending receiveLine rather than leaving it to time out.
                clearReceived();
            }
            signal(connectLatch);
        }

        @Override
        public void onServicesDiscovered(BluetoothGatt g, int status) {
            if (!isCurrent(g)) {
                return;
            }
            servicesStatus = status;
            signal(servicesLatch);
        }

        @Override
        public void onDescriptorWrite(BluetoothGatt g, BluetoothGattDescriptor d, int status) {
            Log.d(TAG, "onDescriptorWrite status=" + status);
            if (!isCurrent(g)) {
                return;
            }
            descriptorStatus = status;
            signal(descriptorLatch);
        }

        @Override
        public void onMtuChanged(BluetoothGatt g, int newMtu, int status) {
            Log.d(TAG, "onMtuChanged newMtu=" + newMtu + " status=" + status);
            if (!isCurrent(g)) {
                return;
            }
            if (status == BluetoothGatt.GATT_SUCCESS && newMtu > 23) {
                mtu = newMtu;
            }
            signal(mtuLatch);
        }

        @Override
        public void onCharacteristicChanged(BluetoothGatt g, BluetoothGattCharacteristic c) {
            Log.d(TAG, "notify (legacy overload) len=" + (c.getValue() == null ? 0 : c.getValue().length));
            if (!isCurrent(g)) {
                return;
            }
            feed(c.getValue());
        }

        @Override
        public void onCharacteristicChanged(BluetoothGatt g, BluetoothGattCharacteristic c,
                                            byte[] value) {
            // Android 13 added this overload; overriding both covers every version.
            Log.d(TAG, "notify len=" + (value == null ? 0 : value.length));
            if (!isCurrent(g)) {
                return;
            }
            feed(value);
        }

        @Override
        public void onCharacteristicWrite(BluetoothGatt g, BluetoothGattCharacteristic c,
                                          int status) {
            Log.d(TAG, "onCharacteristicWrite status=" + status);
            if (!isCurrent(g)) {
                return;
            }
            writeStatus = status;
            signal(writeLatch);
        }
    };

    private static void signal(CountDownLatch latch) {
        if (latch != null) {
            latch.countDown();
        }
    }
}
