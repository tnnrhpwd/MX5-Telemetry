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
        // Clear GPS data to prevent logging stale/garbage values
        gpsValid = false;
        gpsDate = 0;
        gpsTime = 0;
        latitude = 0.0;
        longitude = 0.0;
        satellites = 0;
        fixType = 0;
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
    
    // Update global variables ONLY if we have satellites (prevents garbage data)
    if (gps.satellites.isValid() && gps.satellites.value() > 0) {
        satellites = gps.satellites.value();
        
        // Only update position if location is valid
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
        
        if (gps.time.isValid()) {
            gpsTime = (gps.time.hour() * 10000) + (gps.time.minute() * 100) + gps.time.second();
        }
        
        if (gps.date.isValid()) {
            gpsDate = (gps.date.year() * 10000) + (gps.date.month() * 100) + gps.date.day();
        }
    } else {
        // No satellites = no valid data
        gpsValid = false;
        fixType = 0;
        satellites = 0;
    }
    
    // Update fix quality information - require valid location AND satellites
    if (gps.location.isValid() && gps.location.age() < 2000 && gps.satellites.isValid() && gps.satellites.value() > 0) {
        fixType = 1;  // Basic GPS fix (TinyGPS++ doesn't differentiate DGPS)
    } else {
        fixType = 0;  // No fix
    }
    
    // Update HDOP (Horizontal Dilution of Precision) - only when satellites available
    if (gps.satellites.isValid() && gps.satellites.value() > 0 && gps.hdop.isValid()) {
        hdop = gps.hdop.value();  // Already stored as hdop * 100
    } else {
        hdop = 9999;  // Invalid/unknown HDOP
    }
    
    // Update course/heading
    if (gps.course.isValid()) {
        course = gps.course.deg();
    }
}
