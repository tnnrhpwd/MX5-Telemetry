#include "DataLogger.h"
#include "CANHandler.h"

// ============================================================================
// Data Logger Implementation
// ============================================================================

DataLogger::DataLogger(uint8_t cs)
    : csPin(cs), initialized(false), isLogging(false), errorCount(0),
      writeErrorCount(0), recordsWritten(0), logStartTime(0) {
    logFileName[0] = '\0';
}

bool DataLogger::begin() {
    // Wait for SD card to stabilize after power-on (critical for reliable detection)
    delay(200);
    
    // Try to initialize SD card with retries
    for (int attempt = 0; attempt < 3; attempt++) {
        if (sd.begin(csPin, SD_SCK_MHZ(4))) {
            initialized = true;
            return true;
        }
        delay(100);  // Delay before retry (increased from 50ms)
    }
    // Failed after retries
    initialized = false;
    return false;
}

void DataLogger::writeMetadataHeader(uint32_t gpsDate, uint32_t gpsTime) {
    if (!logFile.isOpen()) return;
    
    // Simplified metadata header to minimize memory usage and SD writes
    char buf[64];
    
    // Just write firmware version and start time
    sprintf(buf, "# MX5 v%s", FIRMWARE_VERSION);
    logFile.write(buf);
    
    if (gpsDate > 20000000 && gpsDate < 21000000) {
        sprintf(buf, " - %lu/%lu", gpsDate, gpsTime);
        logFile.write(buf);
    }
    
    logFile.write("\n");
}

void DataLogger::createLogFile(uint32_t gpsDate, uint32_t gpsTime) {
    // Try to reinitialize if SD card wasn't ready at boot
    if (!initialized) {
        if (sd.begin(csPin, SD_SCK_MHZ(4))) {
            initialized = true;
        } else {
            return;
        }
    }
    
    delay(50);  // Delay before SD operations
    
    static uint16_t fileCounter = 0;
    recordsWritten = 0;
    writeErrorCount = 0;
    logStartTime = millis();
    
    #if GPS_FILENAMES_ENABLED
        // Use GPS-based filename if valid date
        if (gpsDate > 20000000 && gpsDate < 21000000) {
            sprintf(logFileName, "%04lu_%04lu.CSV", gpsDate % 10000, (gpsTime / 10000) % 10000);
            isLogging = true;
            
            if (logFile.open(&sd, logFileName, O_CREAT | O_WRITE | O_TRUNC)) {
                logFile.write("SysTime_ms,Date,GPSTime,GPS_Fix,Lat,Lon,Speed_GPS,Alt,Sat,HDOP,Heading,RPM,Speed_CAN,Throttle,Load,Coolant,Timing,CAN_Status\n");
                logFile.close();
                delay(50);
                return;
            } else {
                logFileName[0] = '\0';
                isLogging = false;
                errorCount++;
                delay(50);
                return;
            }
        }
    #endif
    
    // Sequential filename: Find highest existing LOG_XXXX.CSV and use next number
    uint16_t highestNum = 0;
    FatFile root;
    FatFile entry;
    char name[13];
    
    if (root.open(&sd, "/", O_RDONLY)) {
        while (entry.openNext(&root, O_RDONLY)) {
            if (!entry.isDir() && entry.getName(name, sizeof(name))) {
                if (strncmp(name, "LOG_", 4) == 0 && strstr(name, ".CSV")) {
                    uint16_t num = atoi(name + 4);
                    if (num > highestNum) {
                        highestNum = num;
                    }
                }
            }
            entry.close();
        }
        root.close();
    }
    
    fileCounter = highestNum + 1;
    sprintf(logFileName, "LOG_%04u.CSV", fileCounter);
    isLogging = true;
    
    if (logFile.open(&sd, logFileName, O_CREAT | O_WRITE | O_TRUNC)) {
        logFile.write("SysTime_ms,Date,GPSTime,GPS_Fix,Lat,Lon,Speed_GPS,Alt,Sat,HDOP,Heading,RPM,Speed_CAN,Throttle,Load,Coolant,Timing,CAN_Status\n");
        logFile.close();
    } else {
        logFileName[0] = '\0';
        isLogging = false;
        errorCount++;
    }
    
    delay(50);
}

void DataLogger::logData(uint32_t timestamp, const GPSHandler& gps, const CANHandler& can,
                         bool /*logStatus*/, uint16_t canErrorCount) {
    if (!initialized || !isLogging || logFileName[0] == '\0') return;
    
    // Open file for append
    if (!logFile.open(&sd, logFileName, O_WRITE | O_APPEND)) {
        errorCount++;
        writeErrorCount++;
        if (errorCount > 10) {
            logFileName[0] = '\0';
            isLogging = false;
        }
        return;
    }
    
    // Build entire line in buffer before writing (more reliable)
    // Format: SysTime_ms,Date,GPSTime,GPS_Fix,Lat,Lon,Speed_GPS,Alt,Sat,HDOP,Heading,RPM,Speed_CAN,Throttle,Load,Coolant,Timing,CAN_Status
    char buf[80];
    
    // GPS data tracking - separate from position validity
    uint8_t sats = gps.getSatellites();
    uint8_t fixType = gps.getFixType();
    uint32_t gpsDate = gps.getDate();
    uint32_t gpsTime = gps.getTime();
    
    // Sanitize satellite count - reject garbage values
    if (sats > 50) sats = 0;
    
    // Check if we have valid position data
    bool hasValidLocation = gps.isValid() && sats > 0 && fixType > 0 && fixType < 10;
    
    // Check if we have valid time/date (even without position fix)
    bool hasValidTime = (gpsDate >= 20200101 && gpsDate <= 21001231) && gpsTime > 0;
    
    // Determine CAN status: 1=OK, E=Errors, X=No Init, -=Not connected
    char canStatus;
    if (!can.isInitialized()) {
        canStatus = 'X';  // CAN chip failed to initialize
    } else if (!can.hasRecentData()) {
        canStatus = '-';  // Initialized but no recent data (not connected to vehicle)
    } else if (canErrorCount > 0) {
        canStatus = 'E';  // Receiving data but with errors
    } else {
        canStatus = '1';  // OK - receiving clean data from vehicle
    }
    
    // CAN data: prepare strings with dash for unavailable/stale data
    bool canDataValid = can.isInitialized() && can.hasRecentData();
    char rpmStr[8], speedStr[8], throttleStr[8], loadStr[8], coolantStr[8], timingStr[8];
    
    // CAN data strings
    if (canDataValid) {
        sprintf(rpmStr, "%d", can.getRPM());
        sprintf(speedStr, "%d", can.getSpeed());
        sprintf(throttleStr, "%d", can.getThrottle());
        sprintf(loadStr, "%d", can.getCalculatedLoad());
        sprintf(coolantStr, "%d", can.getCoolantTemp());
        sprintf(timingStr, "%d", can.getTimingAdvance());
    } else {
        strcpy(rpmStr, "-");
        strcpy(speedStr, "-");
        strcpy(throttleStr, "-");
        strcpy(loadStr, "-");
        strcpy(coolantStr, "-");
        strcpy(timingStr, "-");
    }
    
    // Part 1: System time, date, GPS time, fix type
    // Log GPS date/time even without full position fix (aids debugging)
    if (hasValidLocation) {
        sprintf(buf, "%lu,%lu,%lu,%u,", timestamp, gpsDate, gpsTime, fixType);
    } else if (hasValidTime) {
        // We have time but no position - still log date/time for debugging
        sprintf(buf, "%lu,%lu,%lu,0,", timestamp, gpsDate, gpsTime);
    } else {
        sprintf(buf, "%lu,-,-,0,", timestamp);
    }
    logFile.write(buf);
    
    // Part 2: Position (lat, lon) - use dtostrf for reliable float formatting
    if (hasValidLocation) {
        char lat[12], lon[12];
        dtostrf(gps.getLatitude(), 1, 6, lat);
        dtostrf(gps.getLongitude(), 1, 6, lon);
        sprintf(buf, "%s,%s,", lat, lon);
    } else {
        strcpy(buf, "-,-,");
    }
    logFile.write(buf);
    
    // Part 3: Speed, Alt, Sat, HDOP, Heading - use dtostrf for floats
    if (hasValidLocation) {
        char spd[8], alt[10], hdg[8];
        dtostrf(gps.getSpeed(), 1, 1, spd);
        dtostrf(gps.getAltitude(), 1, 1, alt);
        dtostrf(gps.getCourse(), 1, 1, hdg);
        uint16_t hdop = gps.getHDOP();
        if (hdop == 9999 || hdop > 5000) {
            sprintf(buf, "%s,%s,%u,-,%s,", spd, alt, sats, hdg);
        } else {
            sprintf(buf, "%s,%s,%u,%u,%s,", spd, alt, sats, hdop, hdg);
        }
    } else {
        sprintf(buf, "-,-,%u,-,-,", sats);
    }
    logFile.write(buf);
    
    // Part 4: CAN data (RPM, speed, throttle, load, coolant, timing) and status
    sprintf(buf, "%s,%s,%s,%s,%s,%s,%c\n", 
            rpmStr, speedStr, throttleStr, loadStr, coolantStr, timingStr, canStatus);
    logFile.write(buf);
    
    // Close file and update counters
    logFile.close();
    errorCount = 0;
    recordsWritten++;
}

void DataLogger::finishLogging() {
    // Write session summary at end of log (simplified)
    if (initialized && logFileName[0] != '\0') {
        delay(50);
        if (logFile.open(&sd, logFileName, O_WRITE | O_APPEND)) {
            char buf[48];
            sprintf(buf, "# End: %lu rec, %u err, %lu sec\n", 
                    recordsWritten, writeErrorCount, (millis() - logStartTime) / 1000);
            logFile.write(buf);
            logFile.close();
        }
        delay(50);
    }
    
    // Clear the flag - don't touch String to avoid heap issues
    isLogging = false;
    errorCount = 0;
}

// ============================================================================
// Data Retrieval Methods (Serial Dump)
// ============================================================================

void DataLogger::listFiles() {
    if (!initialized) {
        Serial.println(F("Files:0"));
        Serial.flush();
        return;
    }
    
    delay(50);  // Delay before SD operations
    
    FatFile root;
    if (!root.open(&sd, "/", O_RDONLY)) {
        Serial.println(F("Files:0"));
        Serial.flush();
        return;
    }
    
    uint8_t count = 0;
    FatFile entry;
    char name[13];
    
    root.rewind();
    while (entry.openNext(&root, O_RDONLY)) {
        if (!entry.isDir()) {
            if (entry.getName(name, sizeof(name))) {
                if (count == 0) Serial.print(F("Files:"));
                Serial.print(name);
                Serial.print('|');
                Serial.println(entry.fileSize());
                Serial.flush();
                delay(25);  // Increased delay to prevent serial corruption
                count++;
            }
        }
        entry.close();
        if (count >= 100) break;
    }
    
    if (count == 0) {
        Serial.println(F("Files:0"));
    }
    
    root.close();
    delay(50);
    Serial.println(F("OK"));
    Serial.flush();
}

void DataLogger::getSDCardInfo(uint32_t& totalKB, uint32_t& usedKB, uint8_t& fileCount) {
    totalKB = 0;
    usedKB = 0;
    fileCount = 0;
    
    if (!initialized) return;
    
    FatFile root;
    if (!root.open(&sd, "/", O_RDONLY)) return;
    
    unsigned long totalBytes = 0;
    FatFile entry;
    
    // Limit to prevent hangs
    root.rewind();
    while (entry.openNext(&root, O_RDONLY)) {
        if (!entry.isDir()) {
            fileCount++;
            totalBytes += entry.fileSize();
        }
        entry.close();
        if (fileCount >= 50) break;
    }
    
    root.close();
    usedKB = totalBytes / 1024;
}

void DataLogger::dumpFile(const char* filename) {
    if (!initialized) {
        Serial.println(F("E:SD"));
        return;
    }
    
    if (!filename || *filename == '\0') {
        Serial.println(F("ERR:NO_FILENAME"));
        return;
    }
    
    // Open file from SD card volume
    FatFile file;
    if (!file.open(&sd, filename, O_RDONLY)) {
        Serial.print(F("ERR:OPEN_"));
        Serial.println(filename);
        return;
    }
    
    // Get file size for progress tracking
    uint32_t fileSize = file.fileSize();
    uint32_t bytesWritten = 0;
    
    // Send file size header so receiver knows what to expect
    Serial.print(F("SIZE:"));
    Serial.println(fileSize);
    Serial.flush();
    delay(10);
    
    // Use smaller buffer and proper flow control to prevent TX overflow
    // At 115200 baud, 1 byte = ~87us, so 32 bytes = ~2.8ms
    // Serial TX buffer is 64 bytes, so we need to wait for it to drain
    char buffer[32];
    int bytesRead;
    int chunkCount = 0;
    bool aborted = false;
    unsigned long lastProgressTime = millis();
    
    while ((bytesRead = file.read(buffer, sizeof(buffer) - 1)) > 0) {
        buffer[bytesRead] = '\0';
        
        // Wait for TX buffer to have space (critical for large files)
        Serial.flush();  // Block until TX buffer is empty
        Serial.print(buffer);
        bytesWritten += bytesRead;
        
        // Small delay between chunks to allow receiver to process
        delay(2);  // 2ms delay gives receiver time to process
        
        // Every 32 chunks (~1KB), do housekeeping
        if (++chunkCount % 32 == 0) {
            // Check for abort command
            if (Serial.available() > 0) {
                char cmd = Serial.read();
                if (cmd == 'X' || cmd == 'x') {
                    aborted = true;
                    break;
                }
            }
            
            // Send progress every 2 seconds for large files
            if (millis() - lastProgressTime > 2000) {
                // Don't send progress mid-file to avoid corrupting data
                // Just update internal tracking
                lastProgressTime = millis();
            }
            
            // Yield to prevent watchdog timeout on very large files
            delay(1);
        }
    }
    
    file.close();
    
    // Ensure all data is sent before OK
    Serial.flush();
    delay(10);
    
    if (aborted) {
        Serial.println(F("ABORTED"));
    } else {
        Serial.println(F("OK"));
    }
    Serial.flush();
}

void DataLogger::dumpCurrentLog() {
    if (logFileName[0] != '\0') {
        dumpFile(logFileName);
    } else {
        Serial.println(F("E:NL"));
    }
}

// ============================================================================
// Live Data Streaming (Real-time output without SD logging)
// ============================================================================

void DataLogger::streamData(uint32_t timestamp, const GPSHandler& gps, const CANHandler& can,
                            bool logStatus, uint16_t canErrorCount) {
    // Stream in simplified CSV format (saves flash memory)
    Serial.print(timestamp);
    Serial.write(',');
    Serial.print(gps.getDate());
    Serial.write(',');
    Serial.print(gps.getTime());
    Serial.write(',');
    
    if (gps.isValid()) {
        Serial.print(gps.getLatitude(), 6);
        Serial.write(',');
        Serial.print(gps.getLongitude(), 6);
        Serial.write(',');
        Serial.print(gps.getAltitude(), 1);
        Serial.write(',');
        Serial.print(gps.getSpeed(), 2);
    } else {
        Serial.print(F(",,,,"));
    }
    Serial.write(',');
    
    Serial.print(gps.getSatellites());
    Serial.write(',');
    
    // Only output CAN data if connected and receiving data (consistent with logData behavior)
    bool canDataValid = can.isInitialized() && can.hasRecentData();
    if (canDataValid) {
        Serial.print(can.getRPM());
        Serial.write(',');
        Serial.print(can.getSpeed());
        Serial.write(',');
        Serial.print(can.getThrottle());
        Serial.write(',');
        Serial.print(can.getCalculatedLoad());
        Serial.write(',');
        Serial.print(can.getCoolantTemp());
        Serial.write(',');
        Serial.print(can.getIntakeTemp());
        Serial.write(',');
        Serial.print(can.getBarometric());
        Serial.write(',');
        Serial.print(can.getTimingAdvance());
        Serial.write(',');
        Serial.print(can.getMAFRate());
        Serial.write(',');
        Serial.print(can.getShortFuelTrim());
        Serial.write(',');
        Serial.print(can.getLongFuelTrim());
        Serial.write(',');
        Serial.print(can.getO2Voltage(), 3);
    } else {
        // Output dashes for all CAN fields when not connected
        Serial.print(F("-,-,-,-,-,-,-,-,-,-,-,-"));
    }
    Serial.write(',');
    Serial.print(logStatus ? 1 : 0);
    Serial.write(',');
    Serial.print(canErrorCount);
    Serial.println();
}
