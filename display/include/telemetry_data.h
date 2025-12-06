/*
 * ============================================================================
 * Telemetry Data Types
 * ============================================================================
 * Shared data structures for MX5 Telemetry Display Module
 * ============================================================================
 */

#ifndef TELEMETRY_DATA_H
#define TELEMETRY_DATA_H

#include <Arduino.h>

// ============================================================================
// Telemetry Data Structure
// ============================================================================
struct TelemetryPacket {
    // Engine Data
    uint16_t rpm;               // 0-8000
    uint8_t  throttlePosition;  // 0-100%
    int8_t   coolantTemp;       // -40 to 215°C
    int8_t   intakeTemp;        // -40 to 215°C
    uint8_t  oilPressure;       // 0-255 PSI
    int8_t   oilTemp;           // -40 to 215°C
    
    // Transmission
    uint8_t  speed;             // 0-255 km/h or mph
    int8_t   gear;              // -1=R, 0=N, 1-6
    
    // Fuel
    uint8_t  fuelLevel;         // 0-100%
    float    fuelConsumption;   // L/100km or MPG
    
    // GPS Data (when available)
    float    latitude;
    float    longitude;
    float    altitude;
    float    gpsSpeed;
    uint8_t  satellites;
    
    // Timing
    uint32_t timestamp;         // Milliseconds since start
    uint8_t  lapNumber;
    uint32_t lapTime;           // Current lap time in ms
    uint32_t bestLapTime;       // Best lap time in ms
    
    // Status flags
    union {
        uint8_t flags;
        struct {
            uint8_t engineRunning : 1;
            uint8_t checkEngine   : 1;
            uint8_t lowFuel       : 1;
            uint8_t overheating   : 1;
            uint8_t lowOilPress   : 1;
            uint8_t absActive     : 1;
            uint8_t tcsActive     : 1;
            uint8_t reserved      : 1;
        };
    } status;
};

// ============================================================================
// Display Mode Enum
// ============================================================================
enum DisplayMode {
    MODE_GAUGE,         // Main RPM gauge view
    MODE_DASHBOARD,     // Multi-gauge dashboard
    MODE_LAP_TIMER,     // Lap timing display
    MODE_DIAGNOSTICS,   // CAN data viewer
    MODE_SETTINGS,      // Configuration screen
    MODE_SLEEP          // Screen off / dimmed
};

// ============================================================================
// Connection Status
// ============================================================================
enum ConnectionStatus {
    CONN_DISCONNECTED,
    CONN_CONNECTING,
    CONN_CONNECTED,
    CONN_ERROR
};

// ============================================================================
// Gear Display Helper
// ============================================================================
inline const char* gearToString(int8_t gear) {
    switch (gear) {
        case -1: return "R";
        case 0:  return "N";
        case 1:  return "1";
        case 2:  return "2";
        case 3:  return "3";
        case 4:  return "4";
        case 5:  return "5";
        case 6:  return "6";
        default: return "-";
    }
}

// ============================================================================
// CAN Message IDs (MX5 NC specific)
// ============================================================================
namespace CANID {
    constexpr uint16_t ENGINE_RPM       = 0x201;
    constexpr uint16_t VEHICLE_SPEED    = 0x200;
    constexpr uint16_t THROTTLE_POS     = 0x240;
    constexpr uint16_t COOLANT_TEMP     = 0x420;
    constexpr uint16_t OIL_PRESSURE     = 0x421;
    constexpr uint16_t FUEL_LEVEL       = 0x430;
    constexpr uint16_t GEAR_POSITION    = 0x231;
}

// ============================================================================
// Serial Protocol (for Arduino communication)
// ============================================================================
// Simple packet format: STX | Length | Type | Data... | Checksum | ETX
namespace SerialProtocol {
    constexpr uint8_t STX = 0x02;  // Start of text
    constexpr uint8_t ETX = 0x03;  // End of text
    
    // Message types
    constexpr uint8_t MSG_TELEMETRY = 0x10;
    constexpr uint8_t MSG_STATUS    = 0x20;
    constexpr uint8_t MSG_COMMAND   = 0x30;
    constexpr uint8_t MSG_ACK       = 0x40;
}

#endif // TELEMETRY_DATA_H
