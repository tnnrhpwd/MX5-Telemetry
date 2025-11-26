# 📊 Data Analysis Guide

How to analyze and visualize your MX5 telemetry data.

## 📥 Exporting Data from SD Card

1. **Power off the vehicle** completely
2. **Remove the MicroSD card** from the module
3. **Insert into computer** (use USB card reader if needed)
4. **Copy CSV files** to your computer
   - Files are named: `LOG_YYMMDD_HHMM.CSV`
5. **Safely eject** the card and reinsert into module

## 📋 CSV Data Structure

Your log files contain these columns:

```
Timestamp, Date, Time, Latitude, Longitude, Altitude, Satellites, RPM, Speed, Throttle, CoolantTemp
```

### Column Descriptions

| Column | Type | Unit | Example | Description |
|--------|------|------|---------|-------------|
| Timestamp | Integer | milliseconds | 125430 | Time since system startup |
| Date | Integer | YYYYMMDD | 20251120 | GPS date |
| Time | Integer | HHMMSS | 143052 | GPS time (UTC) |
| Latitude | Float | degrees | 34.052235 | GPS latitude (WGS84) |
| Longitude | Float | degrees | -118.243683 | GPS longitude (WGS84) |
| Altitude | Float | meters | 125.4 | GPS altitude above sea level |
| Satellites | Integer | count | 8 | Number of GPS satellites |
| RPM | Integer | rev/min | 3450 | Engine RPM |
| Speed | Integer | km/h | 65 | Vehicle speed |
| Throttle | Integer | percent | 45 | Throttle position (0-100%) |
| CoolantTemp | Integer | °C | 88 | Engine coolant temperature |

## 🖥️ Opening in Spreadsheet Software

### Microsoft Excel

1. Open Excel
2. **File** → **Open**
3. Select your CSV file
4. Data should auto-import with correct columns
5. If not formatted:
   - **Data** → **Text to Columns**
   - Choose "Delimited" → "Comma"

### Google Sheets

1. Open Google Sheets
2. **File** → **Import**
3. **Upload** tab → Select CSV file
4. Import location: **Create new spreadsheet**
5. Separator type: **Comma**
6. Click **Import data**

### LibreOffice Calc

1. Open LibreOffice Calc
2. **File** → **Open**
3. Select CSV file
4. Text Import dialog:
   - Separated by: **Comma**
   - String delimiter: **"**
5. Click **OK**

## 📈 Basic Analysis Tasks

### 1. Max RPM per Session

**Excel Formula**:
```excel
=MAX(H2:H10000)
```
(Assuming RPM is in column H)

**Result**: Shows highest RPM reached during the drive

---

### 2. Average Speed

**Excel Formula**:
```excel
=AVERAGE(I2:I10000)
```
(Assuming Speed is in column I)

**Filter for moving only** (Speed > 5 km/h):
```excel
=AVERAGEIF(I2:I10000,">5")
```

---

### 3. Time in RPM Ranges

Create a helper column to categorize RPM:

**Excel Formula** (in new column L):
```excel
=IF(H2<2000,"Idle",IF(H2<4000,"Cruising",IF(H2<6000,"Sport","Redline")))
```

Then use **PivotTable**:
- Rows: RPM Category
- Values: Count of entries

---

### 4. GPS Track Distance

Calculate distance between consecutive GPS points using Haversine formula.

**Excel** (add helper column for distance):
```excel
=ACOS(COS(RADIANS(90-D2))*COS(RADIANS(90-D3))+SIN(RADIANS(90-D2))*SIN(RADIANS(90-D3))*COS(RADIANS(E2-E3)))*6371
```
(Where D=Latitude, E=Longitude)

Sum all distances for total track length.

---

### 5. Shift Point Analysis

Find average RPM at gear changes (look for sudden RPM drops):

1. Create helper column: `RPM Change = H3 - H2`
2. Filter for large negative changes (< -1000 RPM)
3. Average the "before shift" RPM values

## 📊 Visualization Examples

### 1. RPM vs Time Graph

**Excel**:
1. Select **Timestamp** (column A) and **RPM** (column H)
2. **Insert** → **Line Chart**
3. Format:
   - X-axis: Timestamp (convert to minutes: `=A2/60000`)
   - Y-axis: RPM
   - Title: "Engine RPM Over Time"

**Result**: See RPM behavior throughout your drive

---

### 2. Speed vs RPM Scatter Plot

**Excel**:
1. Select **RPM** (column H) and **Speed** (column I)
2. **Insert** → **Scatter Plot**
3. Add trendline to see gear ratios

**Analysis**: Different clusters represent different gears

---

### 3. GPS Track Map

**Google Maps**:
1. Create KML file (see script below)
2. Upload to **My Maps** (https://www.google.com/mymaps)
3. Visualize your driving route

**Google Earth**:
1. Export to KML format
2. **File** → **Open** in Google Earth

---

### 4. Throttle Position Heatmap

**Excel**:
1. Select **Timestamp** and **Throttle** columns
2. **Insert** → **Line Chart** with color gradient
3. Format data series with color scale:
   - 0% = Green
   - 50% = Yellow
   - 100% = Red

---

### 5. Coolant Temperature Trend

**Excel**:
1. Select **Timestamp** and **CoolantTemp** columns
2. **Insert** → **Line Chart**
3. Add horizontal reference line at 90°C (normal operating temp)

## 🐍 Python Analysis Scripts

### Installation

```bash
pip install pandas matplotlib numpy gpxpy
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

If you drive the same circuit multiple times:

```python
import pandas as pd
from scipy.signal import find_peaks

df = pd.read_csv('track_session.CSV')

# Detect laps by finding when you cross start/finish line
# Example: find when latitude crosses a specific value
start_line_lat = 34.052235  # Your start/finish latitude

crossings = []
for i in range(1, len(df)):
    if (df.loc[i-1, 'Latitude'] < start_line_lat and 
        df.loc[i, 'Latitude'] >= start_line_lat):
        crossings.append(df.loc[i, 'Timestamp'])

# Calculate lap times
lap_times = []
for i in range(1, len(crossings)):
    lap_time = (crossings[i] - crossings[i-1]) / 1000  # seconds
    lap_times.append(lap_time)
    print(f"Lap {i}: {lap_time:.2f} seconds ({lap_time/60:.2f} min)")

print(f"\nBest lap: {min(lap_times):.2f} seconds")
print(f"Average lap: {sum(lap_times)/len(lap_times):.2f} seconds")
```

### Cornering Analysis

Find maximum lateral G-forces (requires calculating speed changes):

```python
import pandas as pd
import numpy as np

df = pd.read_csv('track_session.CSV')

# Calculate speed change rate (approximation of acceleration)
df['Speed_change'] = df['Speed'].diff() / (df['Timestamp'].diff() / 1000)

# Find aggressive cornering (negative acceleration while speed > 50)
cornering = df[(df['Speed'] > 50) & (df['Speed_change'] < -5)]

print(f"Aggressive corners detected: {len(cornering)}")
print(f"Max deceleration: {cornering['Speed_change'].min():.1f} km/h/s")
```

## 🔗 Advanced Tools

### RaceRender (Video Overlay)

Create professional race videos with telemetry overlay:

1. **Export to RaceRender format**:
   - CSV with GPS, Speed, RPM columns
   - Sync with GoPro video using timestamp
   
2. **Import to RaceRender**:
   - Download: https://racerender.com
   - Import CSV and video
   - Add gauges, track map, graphs

### Race Technology Analysis

Use professional racing software:

1. **Circuit Tools** - Free track analysis software
   - Website: http://www.circuittools.com
   
2. **AiM Race Studio** - Professional data analysis
   - Website: https://www.aim-sportline.com

### Motorsport Data Analysis

For serious track day analysis:

- **MoTeC i2** - Industry standard (expensive)
- **Race Studio 3** - AiM's analysis software
- **PI Toolbox** - Professional analysis platform

## 📱 Mobile Apps

### Track Addict (iOS/Android)

- Import GPX files from your telemetry
- Overlay on track maps
- Compare multiple sessions

### Harry's Lap Timer (iOS)

- Import CSV data
- Analyze lap times
- Video overlay support

### RaceChrono (iOS/Android)

- Professional lap timing
- Import telemetry data
- Video synchronization

## 💡 Pro Tips

### 1. Data Quality Checks

Before analyzing, verify:
- GPS satellite count > 6 for accurate positioning
- No large gaps in data (SD card write errors)
- RPM values are reasonable (0-7500 for Miata)
- Timestamps are monotonically increasing

### 2. Filtering Noise

GPS data can be noisy. Apply smoothing:

```python
df['Speed_smooth'] = df['Speed'].rolling(window=5).mean()
df['RPM_smooth'] = df['RPM'].rolling(window=3).mean()
```

### 3. Synchronizing with Video

1. Note exact time when you start recording (both systems)
2. Use a visual/audio cue (e.g., honk horn)
3. Find that moment in both video and CSV data
4. Align timestamps

### 4. Backup Your Data

- Copy CSV files immediately after each session
- Name files descriptively: `track_name_YYMMDD.CSV`
- Keep raw data + processed analysis separately

### 5. Track-Specific Analysis

Create a template spreadsheet for your favorite track:
- Known lap time records
- Sector timing gates (GPS coordinates)
- Best speed for each corner
- Optimal shift points

## 📚 Learning Resources

### Books

- "Speed Secrets" by Ross Bentley
- "Going Faster!" by Carl Lopez
- "Data Acquisition in Motorsports" by Jorge Segers

### Websites

- **MotorsportReg.com** - Track day events
- **Gridlife.com** - Time attack series
- **NASA Racing** - Club racing organization

### YouTube Channels

- "Engineering Explained" - Technical automotive content
- "Driver61" - Driving technique and data analysis
- "Speed Academy" - Track day content

---

**Ready to analyze your data?** Start with basic spreadsheet analysis, then move to Python for advanced visualizations!

**Questions or cool analysis techniques?** Share them in the GitHub issues!
