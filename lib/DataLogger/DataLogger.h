#ifndef DATA_LOGGER_H
#define DATA_LOGGER_H

#include <Arduino.h>
#include <SdFat.h>
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
    void finishLogging();  // Flush buffer and close log (call on STOP command)
    
    // Status
    bool isInitialized() const { return initialized; }
    uint16_t getErrorCount() const { return errorCount; }
    const char* getLogFileName() const { return logFileName; }
    void getSDCardInfo(uint32_t& totalKB, uint32_t& usedKB, uint8_t& fileCount);
    
    // Data Retrieval (Serial Dump)
    void listFiles();
    void dumpFile(const char* filename);
    void dumpCurrentLog();
    
    // Live Data Streaming
    void streamData(uint32_t timestamp, const GPSHandler& gps, const class CANHandler& can,
                    bool logStatus, uint16_t canErrorCount);
    
private:
    uint8_t csPin;
    bool initialized;
    bool isLogging;
    uint16_t errorCount;
    char logFileName[13];  // "LOG_XXXX.CSV" + null terminator
    SdFat sd;
    FatFile logFile;
    

};

#endif // DATA_LOGGER_H
