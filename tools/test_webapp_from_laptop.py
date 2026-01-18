#!/usr/bin/env python3
"""Test webapp from laptop"""
import requests

try:
    r = requests.get('http://192.168.1.23:5000', timeout=5)
    print(f"Status Code: {r.status_code}")
    
    if r.status_code == 200:
        print("\n✓✓✓ WEBAPP IS WORKING! ✓✓✓")
        
        # Extract title
        start = r.text.find("<title>") + 7
        end = r.text.find("</title>")
        title = r.text[start:end]
        print(f"\nPage Title: {title}")
        print(f"\nYou can access it from any device on WiFi at:")
        print(f"  http://192.168.1.23:5000")
        print(f"\nOr when Pi is in hotspot mode:")
        print(f"  http://192.168.4.1:5000")
    else:
        print(f"\n✗ Error: HTTP {r.status_code}")
        
except Exception as e:
    print(f"✗ Connection failed: {e}")
