#include "DataLogger.h"
#include "CANHandler.h"

// ============================================================================
// Data Logger Implementation
// ============================================================================

DataLogger::DataLogger(uint8_t cs)
    : csPin(cs), initialized(false), isLogging(false), errorCount(0) {
    logFileName[0] = '\0';
}

bool DataLogger::begin() {
    // Try to initialize SD card with retries (quick attempts to minimize boot delay)
    for (int attempt = 0; attempt < 3; attempt++) {
        if (sd.begin(csPin, SD_SCK_MHZ(4))) {
            initialized = true;
            return true;
        }
        delay(50);  // Short delay before retry
    }
    // Failed after retries
    initialized = false;
    return false;
}

void DataLogger::createLogFile(uint32_t gpsDate, uint32_t gpsTime) {
    if (!initialized) return;
    
    static uint16_t fileCounter = 0;
    
    #if GPS_FILENAMES_ENABLED
        // Use GPS-based filename if valid date
        if (gpsDate > 20000000 && gpsDate < 21000000) {
            // Format: MMDD_HHMM.CSV (e.g., 1125_1530.CSV for Nov 25, 3:30pm)
            sprintf(logFileName, "%04lu_%04lu.CSV", gpsDate % 10000, (gpsTime / 10000) % 10000);
            isLogging = true;
            
            if (logFile.open(&sd, logFileName, O_CREAT | O_WRITE | O_TRUNC)) {
                logFile.write("Time,Date,GPSTime,Lat,Lon,Speed,Alt,Sat,RPM\n");
                logFile.close();
                return;
            } else {
                logFileName[0] = '\0';
                isLogging = false;
                errorCount++;
                return;
            }
        }
    #endif
    
    // Fallback: counter-based filename
    fileCounter = (millis() / 1000 + fileCounter) % 10000;
    sprintf(logFileName, "LOG_%04u.CSV", fileCounter);
    fileCounter++;
    
    isLogging = true;
    
    if (logFile.open(&sd, logFileName, O_CREAT | O_WRITE | O_TRUNC)) {
        logFile.write("Time,Date,GPSTime,Lat,Lon,Speed,Alt,Sat,RPM\n");
        logFile.close();
    } else {
        logFileName[0] = '\0';
        isLogging = false;
        errorCount++;
    }
}

void DataLogger::logData(uint32_t timestamp, const GPSHandler& gps, const CANHandler& can,
                         bool /*logStatus*/, uint16_t /*canErrorCount*/) {
    if (!initialized || !isLogging || logFileName[0] == '\0') return;
    
    // Open file for append
    if (!logFile.open(&sd, logFileName, O_WRITE | O_APPEND)) {
        errorCount++;
        if (errorCount > 10) {
            logFileName[0] = '\0';
            isLogging = false;
        }
        return;
    }
    
    // Build entire line in buffer before writing (more reliable)
    char buf[80];
    char lat[12], lon[12], spd[8], alt[8];
    
    // Convert floats to strings
    dtostrf(gps.getLatitude(), 1, 6, lat);
    dtostrf(gps.getLongitude(), 1, 6, lon);
    dtostrf(gps.getSpeed(), 1, 2, spd);
    dtostrf(gps.getAltitude(), 1, 1, alt);
    
    // Write line (split into two writes to avoid buffer overflow)
    sprintf(buf, "%lu,%lu,%lu,%s,%s,", timestamp, gps.getDate(), gps.getTime(), lat, lon);
    logFile.write(buf);
    
    sprintf(buf, "%s,%s,%u,%u\n", spd, alt, gps.getSatellites(), can.getRPM());
    logFile.write(buf);
    
    // Close file
    logFile.close();
    errorCount = 0;
}

void DataLogger::finishLogging() {
    // Just clear the flag - don't touch String to avoid heap issues
    isLogging = false;
    errorCount = 0;
}

// ============================================================================
// Data Retrieval Methods (Serial Dump)
// ============================================================================

void DataLogger::listFiles() {
    if (!initialized) {
        Serial.println(F("Files:0"));
        return;
    }
    
    FatFile root;
    if (!root.open(&sd, "/", O_RDONLY)) {
        Serial.println(F("Files:0"));
        return;
    }
    
    uint8_t count = 0;
    FatFile entry;
    char name[13];
    
    // Limit iterations to prevent infinite loops
    root.rewind();
    while (entry.openNext(&root, O_RDONLY)) {
        if (!entry.isDir()) {
            if (count == 0) Serial.print(F("Files:"));
            entry.getName(name, sizeof(name));
            Serial.println(name);
            count++;
        }
        entry.close();
        if (count >= 50) break;
    }
    
    if (count == 0) {
        Serial.println(F("Files:0"));
    }
    
    root.close();
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
        Serial.println(F("ERR:SD_NOT_INIT"));
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
    
    // Check if file is empty
    if (file.fileSize() == 0) {
        file.close();
        Serial.println(F("ERR:EMPTY"));
        return;
    }
    
    // Read and print file contents
    char buffer[64];
    int bytesRead;
    while ((bytesRead = file.read(buffer, sizeof(buffer) - 1)) > 0) {
        buffer[bytesRead] = '\0';
        Serial.print(buffer);
    }
    
    file.close();
    Serial.println(F("OK"));
}

void DataLogger::dumpCurrentLog() {
    if (logFileName[0] != '\0') {
        dumpFile(logFileName);
    } else {
        Serial.println(F("ERR:NOLOG"));
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
