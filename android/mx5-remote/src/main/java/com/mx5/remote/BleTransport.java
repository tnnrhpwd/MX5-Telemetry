package com.mx5.remote;

import android.bluetooth.BluetoothDevice;
import android.bluetooth.BluetoothGatt;
import android.bluetooth.BluetoothGattCallback;
import android.bluetooth.BluetoothGattCharacteristic;
import android.bluetooth.BluetoothGattDescriptor;
import android.bluetooth.BluetoothProfile;
import android.content.Context;
import android.os.Build;

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

    private static final long OPEN_TIMEOUT_MS = 8000;
    private static final long WRITE_TIMEOUT_MS = 2000;

    /** Ask for a large MTU so telemetry needs fewer round trips. */
    private static final int WANTED_MTU = 517;

    private final Context context;
    private final DeviceSource devices;

    private BluetoothGatt gatt;
    private BluetoothGattCharacteristic rx;
    private BluetoothGattCharacteristic tx;
    private int mtu = 23;
    private volatile boolean connected;

    private CountDownLatch connectLatch;
    private CountDownLatch servicesLatch;
    private volatile CountDownLatch writeLatch;

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
        connected = false;

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

        rx = findCharacteristic(SERVICE_UUID, RX_UUID);
        tx = findCharacteristic(SERVICE_UUID, TX_UUID);
        if (rx == null || tx == null) {
            closePipe();
            throw new IOException("The Pi's BLE service was not found: is the Bluetooth "
                    + "link running on the Pi?");
        }

        // Best effort: a small MTU still works, it just costs more notifications.
        try {
            gatt.requestMtu(WANTED_MTU);
        } catch (SecurityException e) {
            // ignore, keep the default
        }

        enableNotifications(tx);
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
        byte[] enable = BluetoothGattDescriptor.ENABLE_NOTIFICATION_VALUE;
        boolean ok;
        if (Build.VERSION.SDK_INT >= Build.VERSION_CODES.TIRAMISU) {
            ok = gatt.writeDescriptor(cccd, enable) == BluetoothGatt.GATT_SUCCESS;
        } else {
            cccd.setValue(enable);
            ok = gatt.writeDescriptor(cccd);
        }
        if (!ok) {
            throw new IOException("Could not enable reply notifications");
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
        for (int off = 0; off < data.length; off += chunk) {
            int len = Math.min(chunk, data.length - off);
            byte[] part = new byte[len];
            System.arraycopy(data, off, part, 0, len);

            writeLatch = new CountDownLatch(1);
            boolean accepted;
            if (Build.VERSION.SDK_INT >= Build.VERSION_CODES.TIRAMISU) {
                accepted = g.writeCharacteristic(
                        c, part, BluetoothGattCharacteristic.WRITE_TYPE_DEFAULT)
                        == BluetoothGatt.GATT_SUCCESS;
            } else {
                c.setWriteType(BluetoothGattCharacteristic.WRITE_TYPE_DEFAULT);
                c.setValue(part);
                accepted = g.writeCharacteristic(c);
            }
            if (!accepted) {
                throw new IOException("The Pi would not accept a BLE write");
            }

            try {
                if (!writeLatch.await(WRITE_TIMEOUT_MS, TimeUnit.MILLISECONDS)) {
                    throw new IOException("BLE write timed out");
                }
            } catch (InterruptedException e) {
                Thread.currentThread().interrupt();
                throw new IOException("Interrupted during a BLE write", e);
            }
        }
    }

    @Override
    protected void closePipe() {
        connected = false;
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
        clearReceived();
    }

    // -- callbacks ----------------------------------------------------------

    private final BluetoothGattCallback callback = new BluetoothGattCallback() {

        @Override
        public void onConnectionStateChange(BluetoothGatt g, int status, int newState) {
            connected = newState == BluetoothProfile.STATE_CONNECTED;
            if (!connected) {
                // Unblocks a pending receiveLine rather than leaving it to time out.
                clearReceived();
            }
            signal(connectLatch);
        }

        @Override
        public void onServicesDiscovered(BluetoothGatt g, int status) {
            signal(servicesLatch);
        }

        @Override
        public void onMtuChanged(BluetoothGatt g, int newMtu, int status) {
            if (status == BluetoothGatt.GATT_SUCCESS && newMtu > 23) {
                mtu = newMtu;
            }
        }

        @Override
        public void onCharacteristicChanged(BluetoothGatt g, BluetoothGattCharacteristic c) {
            feed(c.getValue());
        }

        @Override
        public void onCharacteristicChanged(BluetoothGatt g, BluetoothGattCharacteristic c,
                                            byte[] value) {
            // Android 13 added this overload; overriding both covers every version.
            feed(value);
        }

        @Override
        public void onCharacteristicWrite(BluetoothGatt g, BluetoothGattCharacteristic c,
                                          int status) {
            signal(writeLatch);
        }
    };

    private static void signal(CountDownLatch latch) {
        if (latch != null) {
            latch.countDown();
        }
    }
}
