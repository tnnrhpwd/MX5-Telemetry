#ifndef GPS_HANDLER_H
#define GPS_HANDLER_H

#include <Arduino.h>
#include <TinyGPS++.h>
#include <SoftwareSerial.h>
#include <config.h>

// ============================================================================
// GPS Data Handler
// ============================================================================
// Manages Neo-6M GPS module for position, altitude, and time data
// ============================================================================

class GPSHandler {
public:
    GPSHandler(uint8_t rxPin, uint8_t txPin);
    
    // Initialization
    void begin();
    
    // Dynamic enable/disable
    void enable();   // Start GPS serial communication
    void disable();  // Stop GPS serial communication and clear buffers
    bool isEnabled() const { return enabled; }
    
    // Update (call frequently to feed GPS data)
    void update();
    
    // Data accessors
    double getLatitude() const { return latitude; }
    double getLongitude() const { return longitude; }
    double getAltitude() const { return altitude; }
    double getSpeed() const { return speed; }  // GPS speed in km/h
    uint8_t getSatellites() const { return satellites; }
    uint32_t getTime() const { return gpsTime; }
    uint32_t getDate() const { return gpsDate; }
    bool isValid() const { return gpsValid; }
    uint8_t getFixType() const { return fixType; }  // 0=no fix, 1=GPS fix, 2=DGPS fix
    uint16_t getHDOP() const { return hdop; }  // Horizontal Dilution of Precision (*100)
    double getCourse() const { return course; }  // Heading in degrees
    
private:
    TinyGPSPlus gps;
    SoftwareSerial gpsSerial;
    bool enabled;
    
    // GPS data
    double latitude;
    double longitude;
    double altitude;
    double speed;  // GPS speed in km/h
    uint8_t satellites;
    uint32_t gpsTime;
    uint32_t gpsDate;
    bool gpsValid;
    uint8_t fixType;  // GPS fix quality
    uint16_t hdop;    // Horizontal Dilution of Precision (*100)
    double course;    // Course heading in degrees
};

#endif // GPS_HANDLER_H
