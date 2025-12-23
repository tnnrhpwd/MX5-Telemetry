#!/bin/bash
# MX5 Telemetry Display - Manual Start Script
# Run this script to start the telemetry display
# Usage: ./start_display.sh [--windowed]

cd ~/MX5-Telemetry/pi/ui/src
export DISPLAY=:0

if [ "$1" == "--windowed" ] || [ "$1" == "-w" ]; then
    echo "Starting MX5 Telemetry Display (Windowed)..."
    python3 main.py
else
    echo "Starting MX5 Telemetry Display (Fullscreen)..."
    python3 main.py --fullscreen
fi
