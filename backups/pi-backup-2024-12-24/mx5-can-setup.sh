#!/bin/bash
sleep 2
ip link set can0 down 2>/dev/null
ip link set can0 up type can bitrate 500000 listen-only on
ip link set can1 down 2>/dev/null
ip link set can1 up type can bitrate 125000 listen-only on
