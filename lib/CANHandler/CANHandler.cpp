#include "CANHandler.h"

// ============================================================================
// CAN Handler Implementation
// ============================================================================

CANHandler::CANHandler(uint8_t csPin) 
    : can(csPin), 
      initialized(false), 
      errorCount(0),
      currentRPM(0),
      vehicleSpeed(0),
      throttlePosition(0),
      calculatedLoad(0),
      coolantTemp(0),
      intakeTemp(0),
      barometric(101),  // Default 101 kPa (sea level)
      timingAdvance(0),
      mafRate(0),
      shortFuelTrim(0),
      longFuelTrim(0),
      o2Voltage(0.0),
      lastOBDRequest(0),
      currentPidIndex(0) {
}

bool CANHandler::begin() {
    // Initialize MCP2515 at 500kbps with 16MHz crystal
    if (can.begin(MCP_ANY, CAN_SPEED, MCP_16MHZ) == CAN_OK) {
        can.setMode(MCP_NORMAL);  // Set to normal mode
        initialized = true;
        errorCount = 0;
        return true;
    }
    return false;
}

void CANHandler::update() {
    if (!initialized) return;
    
    long unsigned int rxId;
    unsigned char len = 0;
    unsigned char rxBuf[8];
    
    // ============================================================================
    // DUAL-MODE CAN READING STRATEGY (as specified in requirements)
    // ============================================================================
    // Mode 1: Direct CAN monitoring (preferred) - fastest response
    //         Listens for Mazda-specific CAN ID 0x201 containing raw RPM data
    //         This provides the highest polling rate for accurate visual feedback
    //
    // Mode 2: OBD-II PID requests (fallback) - standard protocol
    //         Requests PID 0x0C (Engine RPM) via standard OBD-II protocol
    //         Used if direct CAN monitoring doesn't capture RPM data
    // ============================================================================
    
    // Check if data is available
    if (can.checkReceive() == CAN_MSGAVAIL) {
        can.readMsgBuf(&rxId, &len, rxBuf);
        
        // Reset error counter on successful read (robust error handling)
        errorCount = 0;
        
        // Parse based on message type
        parseMazdaCANFrame(rxId, len, rxBuf);
        parseOBDResponse(rxId, len, rxBuf);
        
    } else {
        // MODE 2 FALLBACK: Cycle through all OBD-II PIDs for comprehensive data collection
        if (millis() - lastOBDRequest > 100) {  // Request every 100ms
            lastOBDRequest = millis();
            cycleOBDRequests();
        }
    }
    
    // ============================================================================
    // ROBUST ERROR HANDLING (as specified in requirements)
    // ============================================================================
    // Gracefully handle CAN Bus errors without crashing the system
    // Auto-reinitialize after threshold of errors to recover communication
    // ============================================================================
    byte canStatus = can.checkError();
    if (canStatus != 0) {
        errorCount++;
        if (errorCount > CAN_ERROR_THRESHOLD) {
            initialized = begin();
            errorCount = 0;
        }
    }
}

void CANHandler::parseMazdaCANFrame(unsigned long rxId, unsigned char len, unsigned char* rxBuf) {
    // MODE 1: Parse Mazda-specific CAN messages for RPM (fastest method)
    // The Miata NC broadcasts RPM on CAN ID 0x201 (typical Mazda protocol)
    // Format: bytes 0-1 contain RPM (RPM = ((Byte0 << 8) | Byte1) / 4)
    if (rxId == MAZDA_RPM_CAN_ID && len >= 2) {
        uint16_t rawRPM = (rxBuf[0] << 8) | rxBuf[1];
        currentRPM = rawRPM / 4;  // Convert to actual RPM
    }
}

void CANHandler::parseOBDResponse(unsigned long rxId, unsigned char len, unsigned char* rxBuf) {
    // MODE 2: Standard OBD-II PID responses (fallback for compatibility)
    if (rxId == OBD2_RESPONSE_ID && len >= 4) {
        if (rxBuf[1] == OBD2_MODE_01 + 0x40) {  // Response mode (0x41)
            switch (rxBuf[2]) {
                case PID_ENGINE_RPM:  // PID 0x0C: Engine RPM
                    if (len >= 5) {
                        currentRPM = ((rxBuf[3] << 8) | rxBuf[4]) / 4;
                    }
                    break;
                case PID_VEHICLE_SPEED:
                    if (len >= 4) {
                        vehicleSpeed = rxBuf[3];
                    }
                    break;
                case PID_THROTTLE:
                    if (len >= 4) {
                        throttlePosition = (rxBuf[3] * 100) / 255;
                    }
                    break;
                case PID_COOLANT_TEMP:
                    if (len >= 4) {
                        coolantTemp = rxBuf[3] - 40;  // Offset by -40°C
                    }
                    break;
                case PID_CALCULATED_LOAD:
                    if (len >= 4) {
                        calculatedLoad = (rxBuf[3] * 100) / 255;  // Percentage
                    }
                    break;
                case PID_INTAKE_TEMP:
                    if (len >= 4) {
                        intakeTemp = rxBuf[3] - 40;  // Offset by -40°C
                    }
                    break;
                case PID_BAROMETRIC:
                    if (len >= 4) {
                        barometric = rxBuf[3];  // kPa
                    }
                    break;
                case PID_TIMING_ADVANCE:
                    if (len >= 4) {
                        timingAdvance = (rxBuf[3] / 2) - 64;  // Degrees before TDC
                    }
                    break;
                case PID_MAF_RATE:
                    if (len >= 5) {
                        mafRate = ((rxBuf[3] << 8) | rxBuf[4]) / 100;  // g/s
                    }
                    break;
                case PID_SHORT_FUEL_TRIM:
                    if (len >= 4) {
                        shortFuelTrim = (rxBuf[3] - 128) * 100 / 128;  // Percentage
                    }
                    break;
                case PID_LONG_FUEL_TRIM:
                    if (len >= 4) {
                        longFuelTrim = (rxBuf[3] - 128) * 100 / 128;  // Percentage
                    }
                    break;
                case 0x14:  // O2 Sensor Bank 1 Sensor 1
                    if (len >= 4) {
                        o2Voltage = rxBuf[3] * 0.005;  // Volts (resolution 0.005V)
                    }
                    break;
            }
        }
    }
}

void CANHandler::requestOBDData(uint8_t pid) {
    if (!initialized) return;
    
    unsigned char requestBuf[8] = {0x02, OBD2_MODE_01, pid, 0, 0, 0, 0, 0};
    can.sendMsgBuf(OBD2_REQUEST_ID, 0, 8, requestBuf);
}

void CANHandler::cycleOBDRequests() {
    // Cycle through all required PIDs for comprehensive data logging
    static const uint8_t pids[] = {
        PID_ENGINE_RPM,
        PID_VEHICLE_SPEED,
        PID_THROTTLE,
        PID_CALCULATED_LOAD,
        PID_COOLANT_TEMP,
        PID_INTAKE_TEMP,
        PID_BAROMETRIC,
        PID_TIMING_ADVANCE,
        PID_MAF_RATE,
        PID_SHORT_FUEL_TRIM,
        PID_LONG_FUEL_TRIM,
        0x14  // O2 Sensor Bank 1 Sensor 1
    };
    
    requestOBDData(pids[currentPidIndex]);
    currentPidIndex = (currentPidIndex + 1) % (sizeof(pids) / sizeof(pids[0]));
}
