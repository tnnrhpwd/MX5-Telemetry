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
        if (SD.begin(csPin)) {
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
    
    // Generate unique filename based on GPS date/time
    // Format: LOG_YYMMDD_HHMM.CSV
    if (gpsDate > 0 && gpsTime > 0) {
        char filename[24];
        uint16_t year = gpsDate / 10000;
        uint8_t month = (gpsDate / 100) % 100;
        uint8_t day = gpsDate % 100;
        uint8_t hour = gpsTime / 10000;
        uint8_t minute = (gpsTime / 100) % 100;
        
        sprintf(filename, "LOG_%02d%02d%02d_%02d%02d.CSV", 
                year % 100, month, day, hour, minute);
        logFileName = String(filename);
    } else {
        // Fallback: use counter if no GPS fix
        int fileCounter = 0;
        do {
            char filename[16];
            sprintf(filename, "LOG_%d.CSV", fileCounter++);
            logFileName = String(filename);
        } while (SD.exists(logFileName));
    }
    
    // Create file with CSV header
    logFile = SD.open(logFileName, FILE_WRITE);
    if (logFile) {
        // Write CSV header - using single F() for memory efficiency
        logFile.print(F("Elapsed_Time,Date,Time,Lat,Lon,Alt,GPS_Spd,Sats,"));
        logFile.print(F("RPM,ECU_Spd,Thr,Load,"));
        logFile.print(F("Coolant,Intake,Baro,"));
        logFile.print(F("Timing,MAF,STFT,LTFT,"));
        logFile.println(F("O2,LogStat,CANErr"));
        logFile.close();
        Serial.println(logFileName);
    } else {
        errorCount++;
    }
}

void DataLogger::logData(uint32_t timestamp, const GPSHandler& gps, const CANHandler& can,
                         bool logStatus, uint16_t canErrorCount) {
    if (!initialized || logFileName.length() == 0) return;
    
    // Open file for appending (FILE_WRITE mode)
    logFile = SD.open(logFileName, FILE_WRITE);
    if (logFile) {
        // Elapsed time in HH:MM:SS.mmm format
        char timeBuffer[16];
        formatElapsedTime(timestamp, timeBuffer);
        logFile.print(timeBuffer);
        logFile.write(',');
        
        // GPS date and time
        logFile.print(gps.getDate());
        logFile.write(',');
        logFile.print(gps.getTime());
        logFile.write(',');
        
        // GPS coordinates and speed
        if (gps.isValid()) {
            logFile.print(gps.getLatitude(), 6);
            logFile.write(',');
            logFile.print(gps.getLongitude(), 6);
            logFile.write(',');
            logFile.print(gps.getAltitude(), 1);
            logFile.write(',');
            logFile.print(gps.getSpeed(), 2);
        } else {
            logFile.print(F(",,,,"));
        }
        logFile.write(',');
        
        // Satellites
        logFile.print(gps.getSatellites());
        logFile.write(',');
        
        // Core Performance
        logFile.print(can.getRPM());
        logFile.write(',');
        logFile.print(can.getSpeed());
        logFile.write(',');
        logFile.print(can.getThrottle());
        logFile.write(',');
        logFile.print(can.getCalculatedLoad());
        logFile.write(',');
        
        // Engine Health
        logFile.print(can.getCoolantTemp());
        logFile.write(',');
        logFile.print(can.getIntakeTemp());
        logFile.write(',');
        logFile.print(can.getBarometric());
        logFile.write(',');
        
        // Tuning Data
        logFile.print(can.getTimingAdvance());
        logFile.write(',');
        logFile.print(can.getMAFRate());
        logFile.write(',');
        logFile.print(can.getShortFuelTrim());
        logFile.write(',');
        logFile.print(can.getLongFuelTrim());
        logFile.write(',');
        logFile.print(can.getO2Voltage(), 3);
        logFile.write(',');
        
        // System Status
        logFile.print(logStatus ? 1 : 0);
        logFile.write(',');
        logFile.print(canErrorCount);
        logFile.println();
        
        // Close file to ensure data is written
        logFile.close();
        
        // Reset error counter
        errorCount = 0;
    } else {
        errorCount++;
        if (errorCount > SD_ERROR_THRESHOLD) {
            initialized = begin();
            if (initialized) {
                createLogFile(gps.getDate(), gps.getTime());
            }
            errorCount = 0;
        }
    }
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
    
    // Open root directory
    File root = SD.open("/");
    if (!root) {
        // Try re-initializing the SD card
        initialized = begin();
        if (initialized) {
            root = SD.open("/");
        }
        
        if (!root) {
            Serial.println(F("Files:0"));
            Serial.flush();
            return;
        }
    }
    
    // Count files (with timeout protection)
    uint8_t fileCount = 0;
    unsigned long startTime = millis();
    const unsigned long SCAN_TIMEOUT = 1000; // 1 second timeout
    
    int maxFiles = 50;
    for (int i = 0; i < maxFiles; i++) {
        if (millis() - startTime > SCAN_TIMEOUT) break;
        
        File entry = root.openNextFile();
        if (!entry) break; // No more files
        
        if (!entry.isDirectory()) {
            fileCount++;
        }
        entry.close();
    }
    
    // Report count
    Serial.print(F("Files:"));
    Serial.println(fileCount);
    Serial.flush();
    
    // Rewind and list filenames
    root.rewindDirectory();
    startTime = millis();
    
    for (int i = 0; i < maxFiles; i++) {
        if (millis() - startTime > SCAN_TIMEOUT) break;
        
        File entry = root.openNextFile();
        if (!entry) break;
        
        if (!entry.isDirectory()) {
            Serial.println(entry.name());
            Serial.flush();
        }
        entry.close();
    }
    
    root.close();
}

void DataLogger::getSDCardInfo(uint32_t& totalKB, uint32_t& usedKB, uint8_t& fileCount) {
    totalKB = 0;
    usedKB = 0;
    fileCount = 0;
    
    if (!initialized) return;
    
    // Get volume information
    // Note: SD library doesn't provide direct size access on Arduino
    // We'll count files and estimate usage
    
    File root = SD.open("/");
    if (!root) {
        // Try to reinit if root won't open
        initialized = begin();
        if (initialized) {
            root = SD.open("/");
        }
        if (!root) return;
    }
    
    unsigned long totalBytes = 0;
    unsigned long startTime = millis();
    const unsigned long SCAN_TIMEOUT = 1000; // 1 second timeout
    
    int maxFiles = 50;
    for (int i = 0; i < maxFiles; i++) {
        if (millis() - startTime > SCAN_TIMEOUT) break;
        
        File entry = root.openNextFile();
        if (!entry) break;
        
        if (!entry.isDirectory()) {
            fileCount++;
            totalBytes += entry.size();
        }
        entry.close();
        
        // Early exit if found files
        if (fileCount > 0 && (millis() - startTime > 500)) break;
    }
    
    root.close();
    
    usedKB = totalBytes / 1024;
    // Assume SD card capacity based on typical sizes (estimate)
    // Most SD cards are at least 1GB, but we can't directly query this
    totalKB = 0; // Set to 0 to indicate "unknown" - will display as "??"
}

void DataLogger::dumpFile(const String& filename) {
    if (!initialized) {
        Serial.println(F("ERR:NO_SD"));
        Serial.flush();
        return;
    }
    
    File file = SD.open(filename, FILE_READ);
    if (!file) {
        Serial.println(F("ERR:FILE_NOT_FOUND"));
        Serial.flush();
        return;
    }
    
    Serial.println(F("BEGIN_DUMP"));
    Serial.flush();
    
    // Stream file with timeout protection
    unsigned long startTime = millis();
    const unsigned long DUMP_TIMEOUT = 30000; // 30 second timeout
    
    while (file.available()) {
        // Prevent infinite loop
        if (millis() - startTime > DUMP_TIMEOUT) {
            Serial.println(F("ERR:TIMEOUT"));
            Serial.flush();
            break;
        }
        
        String line = file.readStringUntil('\n');
        Serial.println(line);
        
        // Small delay to prevent serial buffer overflow
        delay(5);
    }
    
    file.close();
    Serial.println(F("END_DUMP"));
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
