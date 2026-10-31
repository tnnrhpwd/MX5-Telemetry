#!/bin/bash
# MX5 Telemetry - Bring up CAN interfaces
# Called by systemd service on boot

# Wait for interfaces to be ready
sleep 2

# Bring up HS-CAN (500kbps) - Engine data, RPM, Speed
#
# NOT listen-only. The ECU broadcasts everything this app uses passively, but the two
# OBD-II Mode 01 PIDs (MAF 0x10 and intake air 0x0F) are *request/response*: the Pi has
# to transmit 0x7DF to get an answer. With `listen-only on` the kernel drops the TX
# silently, so no reply ever comes, `telemetry.maf` stays 0 and instant MPG can never be
# computed. Requests are one 8-byte frame 4x/second, which is nothing on a 500 kbps bus.
# restart-ms 100: Auto-recover from bus-off errors
# ACTUAL WIRING: HS-CAN is on can1 (spi0.0, CE0)
if ip link show can1 > /dev/null 2>&1; then
    # `type can` parameters can only be applied while the device is down. On an interface
    # that is already running the kernel answers "Device or resource busy" and keeps the
    # old flags - so re-running this on a live system silently left listen-only on, printed
    # the success line below anyway, and the Pi could not transmit an OBD request until the
    # next reboot.
    ip link set can1 down 2>/dev/null || true
    ip link set can1 type can bitrate 500000 restart-ms 100 listen-only off
    ip link set can1 up
    echo "can1 (HS-CAN) up at 500kbps (transmit enabled for OBD-II, auto-restart)"
else
    echo "can1 not found - check MCP2515 wiring"
fi

# Bring up MS-CAN (125kbps) - Steering wheel buttons, body data
# LISTEN-ONLY mode for production (no transmission to car CAN bus)
# restart-ms 100: Auto-recover from bus-off errors
# ACTUAL WIRING: MS-CAN is on can0 (spi0.1, CE1)
if ip link show can0 > /dev/null 2>&1; then
    ip link set can0 down 2>/dev/null || true
    ip link set can0 type can bitrate 125000 restart-ms 100 listen-only on
    ip link set can0 up
    echo "can0 (MS-CAN) up at 125kbps (listen-only, auto-restart)"
else
    echo "can0 not found - check MCP2515 wiring"
fi
