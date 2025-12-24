#!/bin/bash
# HDMI hotplug script - auto-detect and set resolution like Windows

export DISPLAY=:0
export XAUTHORITY=/home/pi/.Xauthority

# Wait for display to stabilize
sleep 2

# Get the preferred resolution from EDID and set it
PREFERRED=$(xrandr | grep -A1 "HDMI-1 connected" | tail -1 | awk '{print $1}')

if [ -n "$PREFERRED" ]; then
    logger "HDMI hotplug: Setting resolution to $PREFERRED"
    xrandr --output HDMI-1 --mode $PREFERRED --primary
else
    logger "HDMI hotplug: No preferred mode found, using auto"
    xrandr --output HDMI-1 --auto --primary
fi
