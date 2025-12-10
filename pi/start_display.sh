#!/bin/bash
# MX5 Telemetry Display - Manual Start Script
# Run this script to start the telemetry display
# Usage: ./start_display.sh [--fullscreen]

cd ~/MX5-Telemetry/pi/ui/src
export DISPLAY=:0

if [ "$1" == "--fullscreen" ] || [ "$1" == "-f" ]; then
    echo "Starting MX5 Telemetry Display (Fullscreen)..."
    python3 main.py --fullscreen --demo
else
    echo "Starting MX5 Telemetry Display (Windowed)..."
    python3 main.py --demo
fi
