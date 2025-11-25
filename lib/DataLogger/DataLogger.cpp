#include "DataLogger.h"
#include "CANHandler.h"

// ============================================================================
// Data Logger Implementation
// ============================================================================

// Helper function to format milliseconds as HH:MM:SS.mmm
static void formatElapsedTime(uint32_t millis, char* buffer) {
    uint32_t totalSeconds = millis / 1000;
    uint16_t millisPart = millis % 1000;
    uint8_t hours = totalSeconds / 3600;
    uint8_t minutes = (totalSeconds % 3600) / 60;
    uint8_t seconds = totalSeconds % 60;
    
    sprintf(buffer, "%02u:%02u:%02u.%03u", hours, minutes, seconds, millisPart);
}

DataLogger::DataLogger(uint8_t cs)
    : csPin(cs), initialized(false), errorCount(0), logFileName("") {
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
    
    char filename[13];
    
    // Simple filename: LOG_XXXX.CSV where XXXX is seconds since boot
    uint16_t fileNum = (millis() / 1000) % 10000;
    sprintf(filename, "LOG_%04u.CSV", fileNum);
    logFileName = String(filename);
    
    // Create file with header - open/write/close immediately
    if (logFile.open(filename, O_CREAT | O_WRITE | O_TRUNC)) {
        logFile.write("Time,RPM\n");
        logFile.close();
    } else {
        logFileName = "";
        errorCount++;
    }
}

void DataLogger::logData(uint32_t timestamp, const GPSHandler& gps, const CANHandler& can,
                         bool logStatus, uint16_t canErrorCount) {
    if (!initialized || logFileName.length() == 0) return;
    
    // Simple: open file, write one line, close file
    if (logFile.open(logFileName.c_str(), O_WRITE | O_APPEND)) {
        char buffer[32];
        sprintf(buffer, "%lu,%u\n", timestamp, can.getRPM());
        logFile.write(buffer);
        logFile.close();
        errorCount = 0;
    } else {
        errorCount++;
        if (errorCount > 10) {
            logFileName = "";  // Stop trying after 10 failures
        }
    }
}

void DataLogger::finishLogging() {
    // Just clear the filename - no file is kept open
    logFileName = "";
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
    
    FatFile root;
    if (!root.open("/")) {
        Serial.println(F("Files:0"));
        Serial.flush();
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
    Serial.flush();
}

void DataLogger::getSDCardInfo(uint32_t& totalKB, uint32_t& usedKB, uint8_t& fileCount) {
    totalKB = 0;
    usedKB = 0;
    fileCount = 0;
    
    if (!initialized) return;
    
    FatFile root;
    if (!root.open("/")) return;
    
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

void DataLogger::dumpFile(const String& filename) {
    if (!initialized) {
        Serial.println(F("ERR:SD_NOT_INIT"));
        Serial.flush();
        return;
    }
    
    FatFile file;
    if (!file.open(filename.c_str(), O_RDONLY)) {
        Serial.println(F("ERR:FILE_NOT_FOUND"));
        Serial.flush();
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
    Serial.flush();
}

void DataLogger::dumpCurrentLog() {
    if (logFileName.length() > 0) {
        dumpFile(logFileName);
    } else {
        Serial.println(F("ERR:NO_ACTIVE_LOG"));
        Serial.flush();
    }
}

// ============================================================================
// Live Data Streaming (Real-time output without SD logging)
// ============================================================================

void DataLogger::streamData(uint32_t timestamp, const GPSHandler& gps, const CANHandler& can,
                            bool logStatus, uint16_t canErrorCount) {
    // Stream in CSV format - optimized for memory
    char timeBuffer[16];
    formatElapsedTime(timestamp, timeBuffer);
    Serial.print(timeBuffer);
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
