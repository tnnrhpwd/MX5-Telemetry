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
        if (Serial) Serial.println(F("DEBUG: SD not initialized, retrying..."));
        if (sd.begin(csPin, SD_SCK_MHZ(4))) {
            initialized = true;
            if (Serial) Serial.println(F("DEBUG: SD reinitialized OK"));
        } else {
            if (Serial) Serial.println(F("DEBUG: SD reinit failed"));
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
            // Format: MMDD_HHMM.CSV (e.g., 1125_1530.CSV for Nov 25, 3:30pm)
            sprintf(logFileName, "%04lu_%04lu.CSV", gpsDate % 10000, (gpsTime / 10000) % 10000);
            isLogging = true;
            
            if (Serial) {
                Serial.print(F("DEBUG: Creating GPS file: "));
                Serial.println(logFileName);
            }
            
            if (logFile.open(&sd, logFileName, O_CREAT | O_WRITE | O_TRUNC)) {
                if (Serial) Serial.println(F("DEBUG: File opened"));
                
                // Write header first (simpler, more reliable)
                if (!logFile.write("SysTime_ms,Date,GPSTime,GPS_Fix,Lat,Lon,Speed_GPS,Alt,Sat,HDOP,Heading,RPM,Speed_CAN,Throttle,Load,Coolant,Timing,CAN_Status\n")) {
                    if (Serial) Serial.println(F("DEBUG: Header write FAILED"));
                } else {
                    if (Serial) Serial.println(F("DEBUG: Header written"));
                }
                
                logFile.close();
                if (Serial) Serial.println(F("DEBUG: File created OK"));
                delay(50);  // Delay after SD operations
                return;
            } else {
                if (Serial) Serial.println(F("DEBUG: File open FAILED"));
                logFileName[0] = '\0';
                isLogging = false;
                errorCount++;
                delay(50);  // Delay after SD operations
                return;
            }
        }
    #endif
    
    // Fallback: counter-based filename
    fileCounter = (millis() / 1000 + fileCounter) % 10000;
    sprintf(logFileName, "LOG_%04u.CSV", fileCounter);
    fileCounter++;
    
    isLogging = true;
    
    if (Serial) {
        Serial.print(F("DEBUG: Creating counter file: "));
        Serial.println(logFileName);
    }
    
    if (logFile.open(&sd, logFileName, O_CREAT | O_WRITE | O_TRUNC)) {
        if (Serial) Serial.println(F("DEBUG: File opened"));
        
        // Write header first (simpler, more reliable)
        if (!logFile.write("SysTime_ms,Date,GPSTime,GPS_Fix,Lat,Lon,Speed_GPS,Alt,Sat,HDOP,Heading,RPM,Speed_CAN,Throttle,Load,Coolant,Timing,CAN_Status\n")) {
            if (Serial) Serial.println(F("DEBUG: Header write FAILED"));
        } else {
            if (Serial) Serial.println(F("DEBUG: Header written"));
        }
        
        logFile.close();
        if (Serial) Serial.println(F("DEBUG: File created OK"));
    } else {
        if (Serial) Serial.println(F("DEBUG: File open FAILED"));
        logFileName[0] = '\0';
        isLogging = false;
        errorCount++;
    }
    
    delay(50);  // Delay after SD operations
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
    char buf[120];
    char lat[12], lon[12], spdGPS[8], alt[8], heading[8];
    
    // Convert floats to strings - only use GPS data if we have a valid fix
    if (gps.getFixType() > 0) {
        dtostrf(gps.getLatitude(), 1, 6, lat);
        dtostrf(gps.getLongitude(), 1, 6, lon);
        sprintf(spdGPS, "%.1f", gps.getSpeed());
        sprintf(alt, "%.1f", gps.getAltitude());
        sprintf(heading, "%.1f", gps.getCourse());
    } else {
        strcpy(lat, "0");
        strcpy(lon, "0");
        strcpy(spdGPS, "0");
        strcpy(alt, "0");
        strcpy(heading, "0");
    }
    
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
    char rpmStr[8], speedStr[8], throttleStr[8], loadStr[8], coolantStr[8], timingStr[8], hdopStr[8], satStr[8], fixStr[8];
    
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
    
    // GPS data strings
    uint16_t hdop = gps.getHDOP();
    if (hdop == 9999) {
        strcpy(hdopStr, "-");
    } else {
        sprintf(hdopStr, "%d", hdop);
    }
    
    if (gps.getFixType() > 0) {
        sprintf(satStr, "%u", gps.getSatellites());
        sprintf(fixStr, "%u", gps.getFixType());
    } else {
        strcpy(satStr, "-");
        strcpy(fixStr, "-");
    }
    
    // Write line (split into multiple writes to avoid buffer overflow)
    // Part 1: System time, date, GPS time, fix, position
    // Use 0 for Date/Time when GPS has no fix (prevents garbage values)
    uint32_t safeDate = (gps.getFixType() > 0) ? gps.getDate() : 0;
    uint32_t safeTime = (gps.getFixType() > 0) ? gps.getTime() : 0;
    sprintf(buf, "%lu,%lu,%lu,%s,%s,%s,", 
            timestamp, safeDate, safeTime, fixStr, lat, lon);
    logFile.write(buf);
    
    // Part 2: GPS speed, altitude, satellites, HDOP, heading
    sprintf(buf, "%s,%s,%s,%s,%s,", 
            spdGPS, alt, satStr, hdopStr, heading);
    logFile.write(buf);
    
    // Part 3: CAN data (RPM, speed, throttle, load, coolant, timing) and status
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
                Serial.println(name);
                Serial.flush();
                delay(10);  // Small delay between file listings
                count++;
            }
        }
        entry.close();
        if (count >= 50) break;
    }
    
    if (count == 0) {
        Serial.println(F("Files:0"));
        Serial.flush();
    }
    
    root.close();
    delay(50);  // Delay after SD operations
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
    
    // Read and print file contents
    char buffer[64];
    int bytesRead;
    int chunkCount = 0;
    bool aborted = false;
    
    while ((bytesRead = file.read(buffer, sizeof(buffer) - 1)) > 0) {
        buffer[bytesRead] = '\0';
        Serial.print(buffer);
        delayMicroseconds(500);  // Brief delay to prevent TX buffer overflow without blocking
        
        // Every 10 chunks (~640 bytes), check for abort command
        if (++chunkCount % 10 == 0 && Serial.available() > 0) {
            char cmd = Serial.read();
            if (cmd == 'X' || cmd == 'x') {
                aborted = true;
                break;
            }
        }
    }
    
    file.close();
    
    if (aborted) {
        Serial.println(F("ABORTED"));
    } else {
        Serial.println(F("OK"));
    }
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
    Serial.write(',');
    Serial.print(logStatus ? 1 : 0);
    Serial.write(',');
    Serial.print(canErrorCount);
    Serial.println();
}
