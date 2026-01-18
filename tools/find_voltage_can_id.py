#!/usr/bin/env python3
"""
Find the CAN ID that broadcasts battery voltage on MX5 NC.

Run this with engine OFF and note your multimeter reading.
The script will look for CAN messages with values matching your voltage.

Usage:
    python find_voltage_can_id.py [measured_voltage]
    
Example:
    python find_voltage_can_id.py 12.2
"""

import can
import sys
import time
from collections import defaultdict

# Expected voltage from multimeter (default 12.2V)
MEASURED_VOLTAGE = float(sys.argv[1]) if len(sys.argv) > 1 else 12.2

# Common voltage encoding schemes to check
def decode_voltage_schemes(data):
    """Try various voltage encoding schemes, return list of (scheme_name, voltage)"""
    results = []
    
    if len(data) >= 1:
        # Single byte schemes
        results.append(("byte0 / 10", data[0] / 10.0))
        results.append(("byte0 / 8", data[0] / 8.0))
        results.append(("byte0 * 0.1", data[0] * 0.1))
        
    if len(data) >= 2:
        # Two byte big-endian schemes
        raw_be = (data[0] << 8) | data[1]
        results.append(("bytes0-1 BE / 100", raw_be / 100.0))
        results.append(("bytes0-1 BE / 1000", raw_be / 1000.0))
        results.append(("bytes0-1 BE / 50", raw_be / 50.0))
        results.append(("bytes0-1 BE * 0.001", raw_be * 0.001))
        
        # Two byte little-endian schemes
        raw_le = (data[1] << 8) | data[0]
        results.append(("bytes0-1 LE / 100", raw_le / 100.0))
        results.append(("bytes0-1 LE / 1000", raw_le / 1000.0))
        
    if len(data) >= 3:
        # Check bytes 1-2
        raw_be = (data[1] << 8) | data[2]
        results.append(("bytes1-2 BE / 100", raw_be / 100.0))
        raw_le = (data[2] << 8) | data[1]
        results.append(("bytes1-2 LE / 100", raw_le / 100.0))
        
    if len(data) >= 4:
        # Check bytes 2-3
        raw_be = (data[2] << 8) | data[3]
        results.append(("bytes2-3 BE / 100", raw_be / 100.0))
        
    if len(data) >= 5:
        # Check bytes 3-4
        raw_be = (data[3] << 8) | data[4]
        results.append(("bytes3-4 BE / 100", raw_be / 100.0))
        
    if len(data) >= 6:
        # Check bytes 4-5
        raw_be = (data[4] << 8) | data[5]
        results.append(("bytes4-5 BE / 100", raw_be / 100.0))
    
    return results

def main():
    print("=" * 60)
    print("MX5 NC Voltage CAN ID Finder")
    print("=" * 60)
    print(f"Looking for voltage around: {MEASURED_VOLTAGE}V")
    print(f"Acceptable range: {MEASURED_VOLTAGE - 0.5}V to {MEASURED_VOLTAGE + 0.5}V")
    print()
    print("Turn ignition to ACC or ON (do NOT start engine)")
    print("Scanning BOTH CAN buses for 10 seconds each...")
    print()
    
    buses_to_scan = []
    for channel in ['can0', 'can1']:
        try:
            bus = can.interface.Bus(channel=channel, bustype='socketcan')
            buses_to_scan.append((channel, bus))
            print(f"  ✓ {channel} opened")
        except Exception as e:
            print(f"  ✗ {channel} failed: {e}")
    
    if not buses_to_scan:
        print("No CAN buses available!")
        return
    
    # Collect samples for each CAN ID
    can_data = defaultdict(list)
    voltage_matches = []
    
    for channel, bus in buses_to_scan:
        print(f"\nScanning {channel} for 10 seconds...")
        start_time = time.time()
        scan_duration = 10  # seconds
        
        while time.time() - start_time < scan_duration:
            msg = bus.recv(timeout=0.1)
            if msg:
                can_id = msg.arbitration_id
                data = bytes(msg.data)
                
                # Store unique data patterns per CAN ID
                if data not in can_data[(channel, can_id)]:
                    can_data[(channel, can_id)].append(data)
                    
                    # Check for voltage matches
                    for scheme_name, voltage in decode_voltage_schemes(data):
                        if MEASURED_VOLTAGE - 0.5 <= voltage <= MEASURED_VOLTAGE + 0.5:
                            voltage_matches.append({
                                'channel': channel,
                                'can_id': can_id,
                                'data': data,
                                'scheme': scheme_name,
                                'voltage': voltage,
                                'diff': abs(voltage - MEASURED_VOLTAGE)
                            })
        
        bus.shutdown()
        print(f"  {channel} done")
    
    print(f"\nScanned {len(can_data)} unique CAN IDs")
    print()
    
    if voltage_matches:
        # Sort by closest match
        voltage_matches.sort(key=lambda x: x['diff'])
        
        print("=" * 60)
        print("POTENTIAL VOLTAGE CAN IDs FOUND!")
        print("=" * 60)
        print()
        
        seen = set()
        for match in voltage_matches[:15]:  # Top 15 matches
            key = (match['channel'], match['can_id'], match['scheme'])
            if key in seen:
                continue
            seen.add(key)
            
            data_hex = ' '.join(f'{b:02X}' for b in match['data'])
            print(f"CAN ID: 0x{match['can_id']:03X} on {match['channel']}")
            print(f"  Data: {data_hex}")
            print(f"  Decode: {match['scheme']} = {match['voltage']:.2f}V")
            print(f"  Diff from measured: {match['diff']:.2f}V")
            print()
        
        # Best match
        best = voltage_matches[0]
        print("=" * 60)
        print("BEST MATCH:")
        print(f"  CAN bus: {best['channel']}")
        print(f"  CAN ID: 0x{best['can_id']:03X}")
        print(f"  Decoding: {best['scheme']}")
        print(f"  Voltage: {best['voltage']:.2f}V (measured: {MEASURED_VOLTAGE}V)")
        print("=" * 60)
        
    else:
        print("No voltage matches found in the expected range.")
        print()
        print("Possible reasons:")
        print("1. Voltage might not be broadcast with ignition on ACC")
        print("2. Different encoding scheme not tested")
        print("3. Your MX5 might not broadcast voltage at all")
    
    # Also dump all CAN IDs seen for reference
    print()
    print("=" * 60)
    print("ALL CAN IDs SEEN:")
    print("=" * 60)
    for (channel, can_id) in sorted(can_data.keys()):
        samples = can_data[(channel, can_id)]
        print(f"{channel} 0x{can_id:03X}: {len(samples)} unique patterns")
        for data in samples[:2]:  # Show first 2 patterns
            data_hex = ' '.join(f'{b:02X}' for b in data)
            print(f"       {data_hex}")

if __name__ == "__main__":
    main()
