#include "CANHandler.h"

// ============================================================================
// CAN Handler Implementation
// ============================================================================

CANHandler::CANHandler(uint8_t csPin) 
    : can(csPin), 
      initialized(false), 
      errorCount(0),
      lastDataUpdate(0),
      currentRPM(0),
      vehicleSpeed(0),
      throttlePosition(0),
      calculatedLoad(0),
      coolantTemp(-40),   // Initialize to -40°C (OBD raw value 0) to indicate "no data"
      intakeTemp(-40),    // Initialize to -40°C (OBD raw value 0) to indicate "no data"
      barometric(0),      // Initialize to 0 kPa to indicate "no data" (valid range is ~70-110 kPa)
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
    Serial.print(F("CAN init: MCP_ANY, 500KBPS, 16MHz... "));
    byte result = can.begin(MCP_ANY, CAN_SPEED, MCP_16MHZ);
    if (result == CAN_OK) {
        Serial.println(F("OK"));
        Serial.print(F("Setting normal mode... "));
        can.setMode(MCP_NORMAL);
        Serial.println(F("OK"));
        initialized = true;
        errorCount = 0;
        return true;
    }
    Serial.print(F("FAILED! code="));
    Serial.println(result);
    return false;
}

void CANHandler::update() {
    if (!initialized) return;
    
    // Debug: Check MCP2515 status periodically
    static unsigned long lastStatusCheck = 0;
    static uint32_t checkCount = 0;
    static uint32_t msgAvailCount = 0;
    
    checkCount++;
    
    if (millis() - lastStatusCheck > 2000) {
        lastStatusCheck = millis();
        byte errFlag = can.getError();
        byte status = can.checkReceive();
        Serial.print(F("CAN status: checks="));
        Serial.print(checkCount);
        Serial.print(F(" msgs="));
        Serial.print(msgAvailCount);
        Serial.print(F(" err=0x"));
        Serial.print(errFlag, HEX);
        Serial.print(F(" rx="));
        Serial.println(status == CAN_MSGAVAIL ? F("AVAIL") : F("none"));
        checkCount = 0;
    }
    
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
        msgAvailCount++;
        can.readMsgBuf(&rxId, &len, rxBuf);
        
        // DEBUG: Print every CAN frame received (helps identify correct IDs)
        static unsigned long lastDebugPrint = 0;
        if (millis() - lastDebugPrint > 500) {  // Limit to 2 per second
            lastDebugPrint = millis();
            Serial.print(F("CAN RX ID=0x"));
            Serial.print(rxId, HEX);
            Serial.print(F(" len="));
            Serial.print(len);
            Serial.print(F(" data="));
            for (uint8_t i = 0; i < len && i < 8; i++) {
                if (rxBuf[i] < 0x10) Serial.print('0');
                Serial.print(rxBuf[i], HEX);
                Serial.print(' ');
            }
            Serial.println();
        }
        
        // Reset error counter on successful read (robust error handling)
        errorCount = 0;
        
        // Update timestamp for data freshness tracking
        lastDataUpdate = millis();
        
        // Parse based on message type
        parseMazdaCANFrame(rxId, len, rxBuf);
        parseOBDResponse(rxId, len, rxBuf);
        
    }
    // DISABLED: OBD-II requests can flood the bus and trigger check engine light!
    // Only use passive listening mode - do NOT transmit on CAN bus
    // else {
    //     if (millis() - lastOBDRequest > 100) {
    //         lastOBDRequest = millis();
    //         cycleOBDRequests();
    //     }
    // }
    
    // ============================================================================
    // ROBUST ERROR HANDLING (as specified in requirements)
    // ============================================================================
    // Gracefully handle CAN Bus errors without crashing the system
    // Auto-reinitialize disabled to prevent serial spam from MCP_CAN library
    // ============================================================================
    byte canStatus = can.checkError();
    if (canStatus != 0) {
        errorCount++;
        // Reinit disabled - causes debug spam from library
        // if (errorCount > CAN_ERROR_THRESHOLD) {
        //     initialized = begin();
        //     errorCount = 0;
        // }
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
    // DISABLED: Do NOT transmit on CAN bus - passive listening only!
    // Transmitting OBD-II requests can flood the bus and trigger CEL
    // if (!initialized) return;
    // unsigned char requestBuf[8] = {0x02, OBD2_MODE_01, pid, 0, 0, 0, 0, 0};
    // can.sendMsgBuf(OBD2_REQUEST_ID, 0, 8, requestBuf);
    (void)pid;  // Suppress unused parameter warning
}

void CANHandler::cycleOBDRequests() {
    // DISABLED: Do NOT transmit on CAN bus - passive listening only!
    // Transmitting OBD-II requests can flood the bus and trigger CEL
}
