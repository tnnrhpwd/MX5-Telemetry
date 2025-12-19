# 📊 Data Analysis Guide

How to analyze and visualize your MX5 telemetry data.

## 🏎️ Current Architecture

Data logging is handled by the **Raspberry Pi 4B**, which:
- Reads HS-CAN (RPM, speed, throttle, temps) and MS-CAN (steering wheel buttons)
- Receives TPMS and G-force data from ESP32-S3
- Logs to local storage or streams to external services

> **Note**: The legacy Arduino-based SD card logging (GPS, CSV files) has been archived.  
> See `archive/dual-arduino/docs/` for historical CSV format documentation.

---

## 📋 Data Sources

### CAN Bus Data (Pi reads directly)

| Data | CAN ID | Source |
|------|--------|--------|
| Engine RPM | 0x201 | HS-CAN (500 kbaud) |
| Vehicle Speed | 0x420 | HS-CAN |
| Throttle Position | 0x201 | HS-CAN |
| Coolant Temperature | OBD-II PID | HS-CAN |
| Steering Wheel Buttons | MS-CAN IDs | MS-CAN (125 kbaud) |

### Sensor Data (ESP32-S3 → Pi via serial)

| Data | Source | Update Rate |
|------|--------|-------------|
| TPMS (4 tires) | BLE sensors | ~1 Hz |
| G-Force (lateral/longitudinal) | QMI8658 IMU | ~50 Hz |

---

## 📈 Basic Analysis Tasks

### 1. Max RPM per Session

If your logging system outputs CSV:
```python
import pandas as pd
df = pd.read_csv('telemetry_log.csv')
max_rpm = df['RPM'].max()
print(f"Max RPM: {max_rpm}")
```

---

### 2. Average Speed

```python
avg_speed = df[df['Speed'] > 5]['Speed'].mean()  # Exclude idle
print(f"Average moving speed: {avg_speed:.1f} km/h")
```

---

### 3. Time in RPM Ranges

```python
def rpm_category(rpm):
    if rpm < 2000: return 'Idle'
    elif rpm < 4000: return 'Cruising'
    elif rpm < 6000: return 'Sport'
    else: return 'Redline'

df['RPM_Category'] = df['RPM'].apply(rpm_category)
print(df['RPM_Category'].value_counts())
```

---

### 4. Shift Point Analysis

Find average RPM at gear changes (look for sudden RPM drops):

```python
df['RPM_Change'] = df['RPM'].diff()
shifts = df[df['RPM_Change'] < -1000]
avg_shift_rpm = df.loc[shifts.index - 1, 'RPM'].mean()
print(f"Average shift point: {avg_shift_rpm:.0f} RPM")
```

---

## 📊 Visualization Examples

### 1. RPM vs Time Graph

```python
import matplotlib.pyplot as plt

plt.figure(figsize=(12, 4))
plt.plot(df['Timestamp'] / 60000, df['RPM'], linewidth=0.5)
plt.xlabel('Time (minutes)')
plt.ylabel('RPM')
plt.title('Engine RPM Over Time')
plt.grid(True, alpha=0.3)
plt.show()
```

---

### 2. Speed vs RPM Scatter (Gear Detection)

```python
plt.figure(figsize=(8, 6))
plt.scatter(df['RPM'], df['Speed'], alpha=0.1, s=1)
plt.xlabel('RPM')
plt.ylabel('Speed (km/h)')
plt.title('Speed vs RPM - Gear Clusters')
plt.grid(True, alpha=0.3)
plt.show()
```

Different clusters in this plot represent different gears.

---

### 3. G-Force Plot (from ESP32 IMU)

```python
plt.figure(figsize=(8, 8))
plt.scatter(df['G_Lateral'], df['G_Longitudinal'], alpha=0.3, s=1)
plt.xlabel('Lateral G (Left/Right)')
plt.ylabel('Longitudinal G (Accel/Brake)')
plt.title('G-Force Circle')
plt.axhline(y=0, color='k', linewidth=0.5)
plt.axvline(x=0, color='k', linewidth=0.5)
circle = plt.Circle((0, 0), 1.0, fill=False, color='r', linestyle='--')
plt.gca().add_patch(circle)
plt.axis('equal')
plt.show()
```

---

### 4. TPMS Pressure Over Time

```python
fig, axes = plt.subplots(2, 2, figsize=(12, 8))
positions = ['FL', 'FR', 'RL', 'RR']

for ax, pos in zip(axes.flat, positions):
    ax.plot(df['Timestamp'] / 60000, df[f'TPMS_{pos}'])
    ax.set_title(f'{pos} Tire Pressure')
    ax.set_xlabel('Time (min)')
    ax.set_ylabel('PSI')
    ax.grid(True, alpha=0.3)

plt.tight_layout()
plt.show()
```

---

### 5. Coolant Temperature Trend

```python
plt.figure(figsize=(12, 4))
plt.plot(df['Timestamp'] / 60000, df['CoolantTemp'])
plt.axhline(y=90, color='r', linestyle='--', label='Normal Temp')
plt.xlabel('Time (minutes)')
plt.ylabel('Coolant Temp (°C)')
plt.title('Engine Coolant Temperature')
plt.legend()
plt.grid(True, alpha=0.3)
plt.show()
```

### Script 1: Basic Statistics

```python
import pandas as pd
import numpy as np

# Load CSV file
df = pd.read_csv('LOG_251120_1430.CSV')

# Basic statistics
print("=== Telemetry Statistics ===")
print(f"Duration: {df['Timestamp'].max()/1000/60:.1f} minutes")
print(f"Max RPM: {df['RPM'].max()} rev/min")
print(f"Max Speed: {df['Speed'].max()} km/h")
print(f"Avg Speed (moving): {df[df['Speed']>5]['Speed'].mean():.1f} km/h")
print(f"Max Throttle: {df['Throttle'].max()}%")
print(f"Avg Coolant Temp: {df['CoolantTemp'].mean():.1f}°C")

# Time in RPM ranges
rpm_ranges = pd.cut(df['RPM'], bins=[0, 2000, 4000, 6000, 8000], 
                    labels=['Idle', 'Cruising', 'Sport', 'Redline'])
print("\n=== Time in RPM Ranges ===")
print(rpm_ranges.value_counts() / len(df) * 100)
```

---

### Script 2: RPM Visualization

```python
import pandas as pd
import matplotlib.pyplot as plt

# Load data
df = pd.read_csv('LOG_251120_1430.CSV')
df['TimeMin'] = df['Timestamp'] / 60000  # Convert to minutes

# Create plot
plt.figure(figsize=(12, 6))
plt.plot(df['TimeMin'], df['RPM'], linewidth=0.5, color='blue')
plt.axhline(y=6500, color='r', linestyle='--', label='Shift Point')
plt.axhline(y=7200, color='darkred', linestyle='--', label='Redline')
plt.xlabel('Time (minutes)')
plt.ylabel('RPM')
plt.title('Engine RPM Over Time')
plt.legend()
plt.grid(True, alpha=0.3)
plt.tight_layout()
plt.savefig('rpm_plot.png', dpi=300)
plt.show()
```

---

### Script 3: GPS Track Map

```python
import pandas as pd
import matplotlib.pyplot as plt

# Load data
df = pd.read_csv('LOG_251120_1430.CSV')

# Filter valid GPS points
gps_data = df[(df['Latitude'] != 0) & (df['Longitude'] != 0)]

# Create map plot
plt.figure(figsize=(10, 10))
plt.scatter(gps_data['Longitude'], gps_data['Latitude'], 
           c=gps_data['Speed'], cmap='viridis', s=1, alpha=0.6)
plt.colorbar(label='Speed (km/h)')
plt.xlabel('Longitude')
plt.ylabel('Latitude')
plt.title('GPS Track (colored by speed)')
plt.axis('equal')
plt.grid(True, alpha=0.3)
plt.tight_layout()
plt.savefig('gps_track.png', dpi=300)
plt.show()
```

---

### Script 4: Export to GPX

```python
import pandas as pd
import gpxpy
import gpxpy.gpx
from datetime import datetime, timedelta

# Load data
df = pd.read_csv('LOG_251120_1430.CSV')

# Filter valid GPS points
gps_data = df[(df['Latitude'] != 0) & (df['Longitude'] != 0)]

# Create GPX object
gpx = gpxpy.gpx.GPX()
gpx_track = gpxpy.gpx.GPXTrack()
gpx.tracks.append(gpx_track)
gpx_segment = gpxpy.gpx.GPXTrackSegment()
gpx_track.segments.append(gpx_segment)

# Add points
for _, row in gps_data.iterrows():
    point = gpxpy.gpx.GPXTrackPoint(
        latitude=row['Latitude'],
        longitude=row['Longitude'],
        elevation=row['Altitude'],
        time=datetime.utcfromtimestamp(row['Timestamp']/1000)
    )
    gpx_segment.points.append(point)

# Save GPX file
with open('track.gpx', 'w') as f:
    f.write(gpx.to_xml())

print(f"GPX file created: track.gpx ({len(gps_data)} points)")
```

---

### Script 5: Comprehensive Analysis Dashboard

```python
import pandas as pd
import matplotlib.pyplot as plt
import numpy as np

# Load data
df = pd.read_csv('LOG_251120_1430.CSV')
df['TimeMin'] = df['Timestamp'] / 60000

# Create dashboard with multiple subplots
fig, axes = plt.subplots(3, 2, figsize=(15, 12))
fig.suptitle('MX5 Telemetry Dashboard', fontsize=16)

# 1. RPM vs Time
axes[0, 0].plot(df['TimeMin'], df['RPM'], linewidth=0.5)
axes[0, 0].axhline(y=6500, color='r', linestyle='--', alpha=0.5)
axes[0, 0].set_xlabel('Time (min)')
axes[0, 0].set_ylabel('RPM')
axes[0, 0].set_title('Engine RPM')
axes[0, 0].grid(True, alpha=0.3)

# 2. Speed vs Time
axes[0, 1].plot(df['TimeMin'], df['Speed'], linewidth=0.5, color='green')
axes[0, 1].set_xlabel('Time (min)')
axes[0, 1].set_ylabel('Speed (km/h)')
axes[0, 1].set_title('Vehicle Speed')
axes[0, 1].grid(True, alpha=0.3)

# 3. RPM Histogram
axes[1, 0].hist(df['RPM'], bins=50, color='blue', alpha=0.7)
axes[1, 0].set_xlabel('RPM')
axes[1, 0].set_ylabel('Frequency')
axes[1, 0].set_title('RPM Distribution')
axes[1, 0].grid(True, alpha=0.3)

# 4. Speed vs RPM (Gear Analysis)
axes[1, 1].scatter(df['RPM'], df['Speed'], s=1, alpha=0.3)
axes[1, 1].set_xlabel('RPM')
axes[1, 1].set_ylabel('Speed (km/h)')
axes[1, 1].set_title('Speed vs RPM (Gear Ratios)')
axes[1, 1].grid(True, alpha=0.3)

# 5. Throttle Position
axes[2, 0].plot(df['TimeMin'], df['Throttle'], linewidth=0.5, color='orange')
axes[2, 0].set_xlabel('Time (min)')
axes[2, 0].set_ylabel('Throttle (%)')
axes[2, 0].set_title('Throttle Position')
axes[2, 0].grid(True, alpha=0.3)

# 6. GPS Track
gps_valid = df[(df['Latitude'] != 0) & (df['Longitude'] != 0)]
axes[2, 1].scatter(gps_valid['Longitude'], gps_valid['Latitude'], 
                   c=gps_valid['Speed'], cmap='viridis', s=1)
axes[2, 1].set_xlabel('Longitude')
axes[2, 1].set_ylabel('Latitude')
axes[2, 1].set_title('GPS Track')
axes[2, 1].axis('equal')

plt.tight_layout()
plt.savefig('dashboard.png', dpi=300)
plt.show()
```

## 🏁 Racing / Track Day Analysis

### Lap Time Calculation

With the current Pi-based architecture, you can implement lap timing by detecting when you cross a virtual start/finish line:

```python
import pandas as pd

df = pd.read_csv('telemetry_log.csv')

# Option 1: Use speed pattern (crossing pit lane)
# Option 2: Use a GPS dongle connected to Pi if installed

# Example: detect lap completion by RPM pattern (WOT at start/finish)
# Find sequences where throttle goes from high to low to high
high_throttle = df['Throttle'] > 90
lap_markers = []
# ... implement your detection logic based on track characteristics
```

### G-Force Analysis (from ESP32 IMU)

The ESP32-S3's QMI8658 IMU provides accurate G-force data:

```python
import pandas as pd
import numpy as np

df = pd.read_csv('telemetry_log.csv')

# Find peak G-forces
max_lateral = df['G_Lateral'].abs().max()
max_braking = df[df['G_Longitudinal'] < 0]['G_Longitudinal'].min()
max_accel = df[df['G_Longitudinal'] > 0]['G_Longitudinal'].max()

print(f"Max lateral G: {max_lateral:.2f} G")
print(f"Max braking G: {abs(max_braking):.2f} G")
print(f"Max acceleration G: {max_accel:.2f} G")

# G-force friction circle
total_g = np.sqrt(df['G_Lateral']**2 + df['G_Longitudinal']**2)
print(f"Max combined G: {total_g.max():.2f} G")
```

---

## 🔗 Integration Options

### Video Overlay Tools

For track day videos with telemetry overlay:
- **RaceRender** - https://racerender.com (import CSV + video)
- **Race Chrono** - Mobile app with video sync
- **Harry's Lap Timer** - iOS app with import support

---

## 💡 Pro Tips

### 1. Data Quality Checks

Before analyzing:
- Verify RPM values are reasonable (0-7500 for Miata)
- Check TPMS values for outliers (sensor disconnects)
- Ensure G-force readings are calibrated (zero at rest)

### 2. Filtering Noise

Apply smoothing for cleaner visualizations:

```python
df['Speed_smooth'] = df['Speed'].rolling(window=5).mean()
df['RPM_smooth'] = df['RPM'].rolling(window=3).mean()
df['G_Lat_smooth'] = df['G_Lateral'].rolling(window=10).mean()
```

### 3. Backup Your Data

- Export logs from Pi regularly
- Name files descriptively: `track_name_YYMMDD.csv`
- Keep raw data + processed analysis separately

---

## 🔗 Related Documentation

- [PI Display Integration](../PI_DISPLAY_INTEGRATION.md) - Architecture overview
- [TPMS Bluetooth](../hardware/TPMS_BLUETOOTH.md) - BLE sensor decoding
- [LED State System](../features/LED_STATE_SYSTEM.md) - Visual feedback states

---

**Questions or cool analysis techniques?** Share them in the GitHub issues!
