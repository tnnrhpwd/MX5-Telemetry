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
      gpsValid(false),
      fixType(0),
      hdop(9999),
      course(0.0) {
}

void GPSHandler::begin() {
    gpsSerial.begin(GPS_BAUD);
    enabled = false;  // Start disabled, will be enabled on START command
    
    // Clear GPS data to start clean (prevent logging uninitialized values)
    gpsValid = false;
    gpsDate = 0;
    gpsTime = 0;
    latitude = 0.0;
    longitude = 0.0;
    altitude = 0.0;
    speed = 0.0;
    satellites = 0;
    fixType = 0;
    hdop = 9999;
    course = 0.0;
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
        // Clear ALL GPS data to prevent logging stale/garbage values
        gpsValid = false;
        gpsDate = 0;
        gpsTime = 0;
        latitude = 0.0;
        longitude = 0.0;
        altitude = 0.0;
        speed = 0.0;
        satellites = 0;
        fixType = 0;
        hdop = 9999;
        course = 0.0;
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
    
    // Always update satellite count if available (even before fix)
    // This helps debug GPS acquisition
    if (gps.satellites.isValid()) {
        uint8_t sats = gps.satellites.value();
        // Sanity check - reject garbage values
        if (sats <= 50) {
            satellites = sats;
        }
    }
    
    // Time and date are often available before full position fix
    // Update them independently to aid debugging and logging
    if (gps.time.isValid() && gps.time.age() < 2000) {
        gpsTime = (gps.time.hour() * 10000) + (gps.time.minute() * 100) + gps.time.second();
    }
    
    if (gps.date.isValid() && gps.date.age() < 5000) {
        uint32_t newDate = (gps.date.year() * 10000) + (gps.date.month() * 100) + gps.date.day();
        // Sanity check date range (year 2020-2100)
        if (newDate >= 20200101 && newDate <= 21001231) {
            gpsDate = newDate;
        }
    }
    
    // Update position data ONLY with valid satellites and location
    if (satellites > 0 && gps.location.isValid() && gps.location.age() < 2000) {
        latitude = gps.location.lat();
        longitude = gps.location.lng();
        gpsValid = true;
        fixType = 1;  // GPS fix acquired
        
        // Update additional data when we have a fix
        if (gps.altitude.isValid()) {
            altitude = gps.altitude.meters();
        }
        
        if (gps.speed.isValid()) {
            speed = gps.speed.kmph();  // GPS speed in km/h
        }
        
        if (gps.course.isValid()) {
            course = gps.course.deg();
        }
        
        // Update HDOP when available
        if (gps.hdop.isValid()) {
            hdop = gps.hdop.value();  // Already stored as hdop * 100
        }
    } else {
        // No valid fix
        gpsValid = false;
        fixType = 0;
        // Keep satellite count for diagnostic purposes - don't reset to 0
    }
}
