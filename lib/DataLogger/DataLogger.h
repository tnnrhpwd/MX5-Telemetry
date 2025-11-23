#ifndef DATA_LOGGER_H
#define DATA_LOGGER_H

#include <Arduino.h>
#include <SD.h>
#include <SPI.h>
#include <config.h>
#include "GPSHandler.h"

// ============================================================================
// SD Card Data Logger
// ============================================================================
// Manages CSV data logging to MicroSD card with unique timestamped filenames
// ============================================================================

class DataLogger {
public:
    DataLogger(uint8_t csPin);
    
    // Initialization
    bool begin();
    void createLogFile(uint32_t gpsDate, uint32_t gpsTime);
    
    // Logging
    void logData(uint32_t timestamp, const GPSHandler& gps, const class CANHandler& can,
                 bool logStatus, uint16_t canErrorCount);
    
    // Status
    bool isInitialized() const { return initialized; }
    uint16_t getErrorCount() const { return errorCount; }
    String getLogFileName() const { return logFileName; }
    void getSDCardInfo(uint32_t& totalKB, uint32_t& usedKB, uint8_t& fileCount);
    
    // Data Retrieval (Serial Dump)
    void listFiles();
    void dumpFile(const String& filename);
    void dumpCurrentLog();
    
    // Live Data Streaming
    void streamData(uint32_t timestamp, const GPSHandler& gps, const class CANHandler& can,
                    bool logStatus, uint16_t canErrorCount);
    
private:
    uint8_t csPin;
    bool initialized;
    uint16_t errorCount;
    String logFileName;
    File logFile;
};

#endif // DATA_LOGGER_H
