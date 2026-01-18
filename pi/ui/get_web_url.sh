#!/bin/bash
# Get Web Remote URL - Quick script to find the web remote access URL

echo "========================================="
echo "MX5 Web Remote Control"
echo "========================================="
echo ""

# Get all network interfaces and IPs
echo "Available on these addresses:"
hostname -I | tr ' ' '\n' | while read ip; do
    if [ ! -z "$ip" ]; then
        echo "  http://$ip:5000"
    fi
done

echo ""
echo "Save this URL to your phone's home screen!"
echo ""
echo "Common addresses:"
echo "  - http://192.168.1.28:5000  (if Pi has static IP)"
echo "  - http://raspberrypi.local:5000  (mDNS - may work)"
echo ""
echo "Current hostname: $(hostname)"
echo "========================================="
