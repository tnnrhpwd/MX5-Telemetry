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
    // Initialize MCP2515 at 500kbps with 8MHz crystal (WWZMDiB module)
    Serial.print(F("CAN init: MCP_ANY, 500KBPS, 8MHz... "));
    byte result = can.begin(MCP_ANY, CAN_SPEED, MCP_8MHZ);
    if (result == CAN_OK) {
        Serial.println(F("OK"));
        
        // Set masks to 0 = accept all messages (no filtering)
        can.init_Mask(0, 0, 0x00000000);
        can.init_Mask(1, 0, 0x00000000);
        can.init_Filt(0, 0, 0x00000000);
        can.init_Filt(1, 0, 0x00000000);
        can.init_Filt(2, 0, 0x00000000);
        can.init_Filt(3, 0, 0x00000000);
        can.init_Filt(4, 0, 0x00000000);
        can.init_Filt(5, 0, 0x00000000);
        Serial.println(F("Masks/filters set to accept ALL"));
        
        // Use NORMAL mode - ACKs frames but we don't transmit
        Serial.print(F("Setting NORMAL mode... "));
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
    
    // Check INT pin state for debugging
    static uint8_t intLowCount = 0;
    if (digitalRead(CAN_INT_PIN) == LOW) {
        intLowCount++;
    }
    
    if (millis() - lastStatusCheck > 2000) {
        lastStatusCheck = millis();
        byte errFlag = can.getError();
        byte status = can.checkReceive();
        
        // Read MCP2515 error counters - TEC=Transmit, REC=Receive
        byte tec = can.errorCountTX();
        byte rec = can.errorCountRX();
        
        Serial.print(F("CAN: chk="));
        Serial.print(checkCount);
        Serial.print(F(" INT="));
        Serial.print(digitalRead(CAN_INT_PIN));
        Serial.print(F(" msg="));
        Serial.print(msgAvailCount);
        Serial.print(F(" err=0x"));
        Serial.print(errFlag, HEX);
        Serial.print(F(" TEC="));
        Serial.print(tec);
        Serial.print(F(" REC="));
        Serial.print(rec);
        Serial.print(F(" rx="));
        Serial.println(status == CAN_MSGAVAIL ? F("AVAIL") : F("none"));
        checkCount = 0;
    }
    
    long unsigned int rxId;
    unsigned char len = 0;
    unsigned char rxBuf[8];
    
    // Try reading directly - readMsgBuf returns CAN_OK if message was available
    byte readResult = can.readMsgBuf(&rxId, &len, rxBuf);
    
    if (readResult == CAN_OK && len > 0) {
        msgAvailCount++;
        
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

bool CANHandler::runLoopbackTest() {
    // ============================================================================
    // LOOPBACK SELF-TEST
    // ============================================================================
    // Puts MCP2515 in loopback mode where TX is internally connected to RX.
    // This verifies: SPI communication, MCP2515 chip, and internal logic.
    // Does NOT transmit on actual CAN bus - safe to run while connected to car.
    // ============================================================================
    
    Serial.println(F("\n=== CAN LOOPBACK TEST ==="));
    
    if (!initialized) {
        Serial.println(F("FAIL: CAN not initialized"));
        return false;
    }
    
    // Step 1: Enter loopback mode
    Serial.print(F("Setting loopback mode... "));
    can.setMode(MCP_LOOPBACK);
    delay(10);
    Serial.println(F("OK"));
    
    // Step 2: Prepare test message
    unsigned char testData[8] = {0xDE, 0xAD, 0xBE, 0xEF, 0xCA, 0xFE, 0x12, 0x34};
    unsigned long testId = 0x7FF;  // Use a safe test ID
    
    // Step 3: Send test message
    Serial.print(F("Sending test msg ID=0x7FF... "));
    byte sendResult = can.sendMsgBuf(testId, 0, 8, testData);
    if (sendResult != CAN_OK) {
        Serial.print(F("FAIL: send error="));
        Serial.println(sendResult);
        can.setMode(MCP_NORMAL);
        return false;
    }
    Serial.println(F("OK"));
    
    // Step 4: Wait for message to loop back
    Serial.print(F("Waiting for loopback... "));
    unsigned long startWait = millis();
    bool received = false;
    
    while (millis() - startWait < 100) {  // 100ms timeout
        if (can.checkReceive() == CAN_MSGAVAIL) {
            received = true;
            break;
        }
        delay(1);
    }
    
    if (!received) {
        Serial.println(F("FAIL: no response (timeout)"));
        can.setMode(MCP_NORMAL);
        return false;
    }
    Serial.println(F("OK"));
    
    // Step 5: Read and verify the message
    Serial.print(F("Verifying data... "));
    unsigned long rxId;
    unsigned char len = 0;
    unsigned char rxBuf[8];
    can.readMsgBuf(&rxId, &len, rxBuf);
    
    // Check ID
    if (rxId != testId) {
        Serial.print(F("FAIL: ID mismatch, got 0x"));
        Serial.println(rxId, HEX);
        can.setMode(MCP_NORMAL);
        return false;
    }
    
    // Check length
    if (len != 8) {
        Serial.print(F("FAIL: len mismatch, got "));
        Serial.println(len);
        can.setMode(MCP_NORMAL);
        return false;
    }
    
    // Check data
    bool dataMatch = true;
    for (uint8_t i = 0; i < 8; i++) {
        if (rxBuf[i] != testData[i]) {
            dataMatch = false;
            break;
        }
    }
    
    if (!dataMatch) {
        Serial.println(F("FAIL: data mismatch"));
        Serial.print(F("  Sent: "));
        for (uint8_t i = 0; i < 8; i++) {
            if (testData[i] < 0x10) Serial.print('0');
            Serial.print(testData[i], HEX);
            Serial.print(' ');
        }
        Serial.println();
        Serial.print(F("  Recv: "));
        for (uint8_t i = 0; i < 8; i++) {
            if (rxBuf[i] < 0x10) Serial.print('0');
            Serial.print(rxBuf[i], HEX);
            Serial.print(' ');
        }
        Serial.println();
        can.setMode(MCP_NORMAL);
        return false;
    }
    Serial.println(F("OK"));
    
    // Step 6: Return to normal mode
    Serial.print(F("Restoring normal mode... "));
    can.setMode(MCP_NORMAL);
    delay(10);
    Serial.println(F("OK"));
    
    Serial.println(F("=== LOOPBACK TEST PASSED ===\n"));
    return true;
}
