#include "DataLogger.h"
#include "CANHandler.h"

// ============================================================================
// Data Logger Implementation
// ============================================================================

DataLogger::DataLogger(uint8_t cs)
    : csPin(cs), initialized(false), errorCount(0), logFileName("") {
}

bool DataLogger::begin() {
    if (!SD.begin(csPin)) {
        return false;
    }
    initialized = true;
    return true;
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
        logFile.print(F("Timestamp,Date,Time,Lat,Lon,Alt,GPS_Spd,Sats,"));
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
        // Timestamp, date, time
        logFile.print(timestamp);
        logFile.write(',');
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
    if (!initialized) return;
    
    File root = SD.open("/");
    if (!root) return;
    
    int fileCount = 0;
    while (true) {
        File entry = root.openNextFile();
        if (!entry) break;
        
        if (!entry.isDirectory()) {
            fileCount++;
            Serial.print(entry.name());
            Serial.print(' ');
            Serial.println(entry.size());
        }
        entry.close();
    }
    root.close();
    Serial.print(F("Files:"));
    Serial.println(fileCount);
}

void DataLogger::dumpFile(const String& filename) {
    if (!initialized) return;
    
    File file = SD.open(filename, FILE_READ);
    if (!file) return;
    
    Serial.println(F("---BEGIN---"));
    
    while (file.available()) {
        String line = file.readStringUntil('\n');
        Serial.println(line);
    }
    
    file.close();
    Serial.println(F("---END---"));
}

void DataLogger::dumpCurrentLog() {
    if (logFileName.length() > 0) {
        dumpFile(logFileName);
    }
}

// ============================================================================
// Live Data Streaming (Real-time output without SD logging)
// ============================================================================

void DataLogger::streamData(uint32_t timestamp, const GPSHandler& gps, const CANHandler& can,
                            bool logStatus, uint16_t canErrorCount) {
    // Stream in CSV format - optimized for memory
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
