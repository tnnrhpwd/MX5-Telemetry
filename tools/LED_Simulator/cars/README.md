# Car Configuration Files

This directory contains JSON configuration files for different vehicles to use with the LED Simulator.

## File Format

Each car configuration file is a JSON file with the following structure:

```json
{
  "name": "Car Display Name",
  "year": 2008,
  "make": "Manufacturer",
  "model": "Model Name",
  "engine": {
    "displacement": 2.0,
    "cylinders": 4,
    "aspiration": "naturally_aspirated",
    "redline_rpm": 7200,
    "idle_rpm": 800,
    "shift_light_rpm": 6500,
    "min_display_rpm": 1000,
    "max_display_rpm": 7000
  },
  "transmission": {
    "type": "manual",
    "gears": 6,
    "gear_ratios": {
      "1": 3.760,
      "2": 2.269,
      "3": 1.645,
      "4": 1.187,
      "5": 1.000,
      "6": 0.843
    },
    "final_drive": 4.100,
    "clutch_engagement_rpm": 1200
  },
  "tires": {
    "size": "205/45R17",
    "circumference_meters": 1.937
  },
  "performance": {
    "top_speed_kmh": 215,
    "top_speed_mph": 134,
    "zero_to_100_kmh": 8.1,
    "power_hp": 170,
    "power_kw": 127,
    "torque_nm": 188,
    "weight_kg": 1138
  },
  "physics": {
    "rpm_accel_rate": 50,
    "rpm_decel_rate": 30,
    "rpm_idle_return_rate": 20,
    "speed_accel_rate": 0.5,
    "speed_decel_rate": 1.0
  }
}
```

## Field Descriptions

### Engine Section
- **redline_rpm**: Maximum safe engine RPM
- **idle_rpm**: RPM when engine is idling
- **shift_light_rpm**: RPM when shift light activates
- **min_display_rpm**: Minimum RPM to start showing on LED strip
- **max_display_rpm**: Maximum RPM for LED gradient display

### Transmission Section
- **type**: Transmission type (manual/automatic)
- **gears**: Number of forward gears
- **gear_ratios**: Ratio for each gear (higher = more torque, lower speed)
- **final_drive**: Final drive ratio
- **clutch_engagement_rpm**: Minimum RPM for clutch to engage

### Tires Section
- **size**: Tire size designation
- **circumference_meters**: Rolling circumference of tire in meters

### Performance Section
- **top_speed_kmh**: Maximum vehicle speed in km/h

### Physics Section
- **rpm_accel_rate**: RPM increase per frame when accelerating
- **rpm_decel_rate**: RPM decrease per frame when decelerating
- **rpm_idle_return_rate**: RPM return rate to idle
- **speed_accel_rate**: Speed increase per frame (km/h)
- **speed_decel_rate**: Speed decrease per frame (km/h)

## Calculating Tire Circumference

Tire circumference = π × tire diameter (in meters)

For example, 205/45R17:
- Width: 205mm
- Aspect ratio: 45% (sidewall height = 205 × 0.45 = 92.25mm)
- Rim diameter: 17 inches = 431.8mm
- Total diameter = (2 × 92.25) + 431.8 = 616.3mm = 0.6163m
- Circumference = π × 0.6163 = 1.937m

## Creating Your Own Car File

1. Copy an existing car file (e.g., `2008_miata_nc.json`)
2. Rename it to match your vehicle (e.g., `2015_mustang_gt.json`)
3. Update all the values to match your vehicle's specifications
4. Save the file in this `cars/` directory
5. Load it in the simulator using the "Load Car File" button

## Available Cars

- **2008_miata_nc.json** - 2008 Mazda MX-5 NC (default)
- **example_sports_car.json** - Generic example for reference

## Tips

- Find gear ratios in your vehicle's service manual or online databases
- Redline RPM is usually printed on the tachometer
- Top speed can be found in manufacturer specifications
- Physics rates (accel/decel) can be adjusted for desired simulator feel
- Test your configuration and adjust values until it feels realistic
