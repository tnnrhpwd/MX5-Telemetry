#include "GPSHandler.h"

// ============================================================================
// GPS Handler Implementation
// ============================================================================

GPSHandler::GPSHandler(uint8_t rxPin, uint8_t txPin)
    : gpsSerial(rxPin, txPin),
      enabled(false),
      latitude(0.0),
      longitude(0.0),
      altitude(0.0),
      speed(0.0),
      satellites(0),
      gpsTime(0),
      gpsDate(0),
      gpsValid(false) {
}

void GPSHandler::begin() {
    gpsSerial.begin(GPS_BAUD);
    enabled = false;  // Start disabled, will be enabled on START command
}

void GPSHandler::enable() {
    if (!enabled) {
        enabled = true;
        // Clear any stale data in serial buffer
        while (gpsSerial.available() > 0) {
            gpsSerial.read();
        }
    }
}

void GPSHandler::disable() {
    if (enabled) {
        enabled = false;
        // Clear serial buffer to prevent interference with USB Serial
        while (gpsSerial.available() > 0) {
            gpsSerial.read();
        }
        // Optionally invalidate GPS data
        gpsValid = false;
    }
}

void GPSHandler::update() {
    // Only process GPS data if enabled
    if (!enabled) {
        return;
    }
    
    // Feed GPS data into parser
    while (gpsSerial.available() > 0) {
        gps.encode(gpsSerial.read());
    }
    
    // Update global variables if valid data is available
    if (gps.location.isValid()) {
        latitude = gps.location.lat();
        longitude = gps.location.lng();
        gpsValid = true;
    } else {
        gpsValid = false;
    }
    
    if (gps.altitude.isValid()) {
        altitude = gps.altitude.meters();
    }
    
    if (gps.speed.isValid()) {
        speed = gps.speed.kmph();  // GPS speed in km/h
    }
    
    if (gps.satellites.isValid()) {
        satellites = gps.satellites.value();
    }
    
    if (gps.time.isValid()) {
        gpsTime = (gps.time.hour() * 10000) + (gps.time.minute() * 100) + gps.time.second();
    }
    
    if (gps.date.isValid()) {
        gpsDate = (gps.date.year() * 10000) + (gps.date.month() * 100) + gps.date.day();
    }
}
