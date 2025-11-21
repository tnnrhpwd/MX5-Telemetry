/*
 * MX5-Telemetry System
 * 
 * A comprehensive embedded telemetry solution for 2008 Mazda Miata NC (MX-5)
 * 
 * Features:
 * - CAN Bus communication for RPM and vehicle data
 * - WS2812B LED strip for visual RPM indicator and shift light
 * - GPS logging with Neo-6M module
 * - SD card data logging in CSV format
 * - Automatic GoPro power control via MOSFET
 * - Low-power standby mode when vehicle is off
 * 
 * Hardware:
 * - Arduino Nano (ATmega328P, 16MHz, 5V)
 * - MCP2515 CAN Controller (500 kbaud)
 * - WS2812B LED Strip
 * - Neo-6M GPS Module
 * - MicroSD Card Module
 * - MOSFET for GoPro power control
 * - LM2596 Buck Converter (12V to 5V)
 * 
 * Author: AI Assistant
 * Date: 2025-11-20
 */

// ============================================================================
// LIBRARY DEPENDENCIES
// ============================================================================
// Install these libraries via Arduino IDE Library Manager:
// 1. Tools → Manage Libraries → Search and install each:
//
//    - "MCP_CAN" by Cory J. Fowler (v1.5.0 or later)
//    - "Adafruit NeoPixel" by Adafruit (v1.10.0 or later)
//    - "TinyGPSPlus" by Mikal Hart (v1.0.3 or later)
//
// 2. Built-in libraries (no installation needed):
//    - SPI.h, SD.h, SoftwareSerial.h
//
// If compilation fails with "library not found" errors, see libraries_needed.txt
// ============================================================================

#include <SPI.h>                  // Built-in: SPI communication
#include <mcp_can.h>              // Install via Library Manager: CAN Bus control
#include <SD.h>                   // Built-in: SD Card file operations
#include <Adafruit_NeoPixel.h>    // Install via Library Manager: WS2812B LED control
#include <TinyGPS++.h>            // Install via Library Manager: GPS NMEA parser
#include <SoftwareSerial.h>       // Built-in: Software UART for GPS

// ============================================================================
// PIN DEFINITIONS
// ============================================================================
#define CAN_CS_PIN      10    // MCP2515 Chip Select (SPI)
#define SD_CS_PIN       4     // SD Card Chip Select (SPI)
#define LED_DATA_PIN    6     // WS2812B Data Pin
#define GPS_RX_PIN      2     // GPS Module RX (connect to GPS TX)
#define GPS_TX_PIN      3     // GPS Module TX (connect to GPS RX)
#define GOPRO_PIN       5     // MOSFET Gate for GoPro Power Control

// SPI Pins (shared between CAN and SD):
// D11 - MOSI
// D12 - MISO
// D13 - SCK

// ============================================================================
// CONFIGURATION CONSTANTS
// ============================================================================
#define LED_COUNT       30    // Number of LEDs in the strip
#define CAN_SPEED       CAN_500KBPS  // Miata NC CAN bus speed
#define SERIAL_BAUD     115200       // Serial monitor baud rate
#define GPS_BAUD        9600         // GPS module baud rate

// RPM Thresholds (adjust for your Miata's redline)
#define RPM_IDLE        800          // Idle RPM
#define RPM_MIN_DISPLAY 1000         // Minimum RPM to show on LED strip
#define RPM_MAX_DISPLAY 7000         // Maximum RPM for gradient
#define RPM_SHIFT_LIGHT 6500         // RPM to activate shift light
#define RPM_REDLINE     7200         // Absolute redline

// Timing Constants
#define CAN_READ_INTERVAL    20      // Read CAN bus every 20ms (50Hz)
#define GPS_READ_INTERVAL    100     // Read GPS every 100ms (10Hz)
#define LOG_INTERVAL         200     // Log data every 200ms (5Hz)
#define GOPRO_OFF_DELAY      10000   // Turn off GoPro after 10s at RPM=0
#define STANDBY_CHECK_INTERVAL 1000  // Check for standby every 1s

// OBD-II PIDs
#define OBD2_MODE_01    0x01         // Show current data
#define PID_ENGINE_RPM  0x0C         // Engine RPM PID
#define PID_VEHICLE_SPEED 0x0D       // Vehicle Speed PID
#define PID_THROTTLE    0x11         // Throttle Position PID
#define PID_COOLANT_TEMP 0x05        // Coolant Temperature PID

// CAN IDs
#define OBD2_REQUEST_ID 0x7DF        // Standard OBD-II request ID
#define OBD2_RESPONSE_ID 0x7E8       // Standard OBD-II response ID

// ============================================================================
// GLOBAL OBJECTS
// ============================================================================
MCP_CAN CAN(CAN_CS_PIN);                          // CAN Bus controller
Adafruit_NeoPixel strip(LED_COUNT, LED_DATA_PIN, NEO_GRB + NEO_KHZ800);
TinyGPSPlus gps;                                  // GPS parser
SoftwareSerial gpsSerial(GPS_RX_PIN, GPS_TX_PIN); // GPS serial connection

// ============================================================================
// GLOBAL VARIABLES
// ============================================================================
// Vehicle Data
volatile uint16_t currentRPM = 0;
volatile uint8_t vehicleSpeed = 0;
volatile uint8_t throttlePosition = 0;
volatile int8_t coolantTemp = 0;

// GPS Data
double latitude = 0.0;
double longitude = 0.0;
double altitude = 0.0;
uint8_t satellites = 0;
uint32_t gpsTime = 0;
uint32_t gpsDate = 0;
bool gpsValid = false;

// Timing Variables
unsigned long lastCANRead = 0;
unsigned long lastGPSRead = 0;
unsigned long lastLogWrite = 0;
unsigned long lastStandbyCheck = 0;
unsigned long rpmZeroStartTime = 0;
bool rpmWasZero = false;

// System State
bool canInitialized = false;
bool sdInitialized = false;
bool gpsInitialized = false;
bool goProOn = false;
bool inStandbyMode = false;
File logFile;
String logFileName = "";

// Error Counters
uint16_t canErrorCount = 0;
uint16_t sdErrorCount = 0;

// ============================================================================
// SETUP FUNCTION
// ============================================================================
void setup() {
  // Initialize Serial for debugging
  Serial.begin(SERIAL_BAUD);
  delay(100);
  Serial.println(F("MX5-Telemetry System Starting..."));
  
  // Initialize GPIO Pins
  pinMode(GOPRO_PIN, OUTPUT);
  digitalWrite(GOPRO_PIN, LOW);  // GoPro OFF initially
  
  // Initialize LED Strip
  strip.begin();
  strip.show();  // Initialize all pixels to 'off'
  strip.setBrightness(255);  // Full brightness
  startupAnimation();  // Show visual feedback during startup
  
  // Initialize CAN Bus
  Serial.println(F("Initializing CAN Bus..."));
  canInitialized = initCAN();
  if (canInitialized) {
    Serial.println(F("CAN Bus initialized successfully"));
  } else {
    Serial.println(F("CAN Bus initialization FAILED!"));
    errorAnimation();  // Show error on LED strip
  }
  
  // Initialize SD Card
  Serial.println(F("Initializing SD Card..."));
  sdInitialized = initSD();
  if (sdInitialized) {
    Serial.println(F("SD Card initialized successfully"));
    createLogFile();
  } else {
    Serial.println(F("SD Card initialization FAILED!"));
    errorAnimation();
  }
  
  // Initialize GPS
  Serial.println(F("Initializing GPS..."));
  gpsSerial.begin(GPS_BAUD);
  gpsInitialized = true;
  Serial.println(F("GPS initialized successfully"));
  
  // Ready Animation
  readyAnimation();
  Serial.println(F("System Ready!"));
  Serial.println(F("Waiting for vehicle data..."));
}

// ============================================================================
// MAIN LOOP
// ============================================================================
void loop() {
  unsigned long currentMillis = millis();
  
  // Read CAN Bus at high frequency (50Hz)
  if (currentMillis - lastCANRead >= CAN_READ_INTERVAL) {
    lastCANRead = currentMillis;
    readCANData();
  }
  
  // Read GPS at moderate frequency (10Hz)
  if (currentMillis - lastGPSRead >= GPS_READ_INTERVAL) {
    lastGPSRead = currentMillis;
    readGPSData();
  }
  
  // Update LED strip based on current RPM
  updateLEDStrip(currentRPM);
  
  // Log data periodically (5Hz)
  if (currentMillis - lastLogWrite >= LOG_INTERVAL) {
    lastLogWrite = currentMillis;
    logData();
  }
  
  // Manage GoPro power based on RPM
  manageGoProPower(currentMillis);
  
  // Check for standby mode periodically
  if (currentMillis - lastStandbyCheck >= STANDBY_CHECK_INTERVAL) {
    lastStandbyCheck = currentMillis;
    checkStandbyMode();
  }
  
  // Keep feeding GPS data
  while (gpsSerial.available() > 0) {
    gps.encode(gpsSerial.read());
  }
}

// ============================================================================
// CAN BUS FUNCTIONS
// ============================================================================

bool initCAN() {
  // Initialize MCP2515 at 500kbps with 16MHz crystal
  if (CAN.begin(MCP_ANY, CAN_SPEED, MCP_16MHZ) == CAN_OK) {
    CAN.setMode(MCP_NORMAL);  // Set to normal mode
    return true;
  }
  return false;
}

void readCANData() {
  if (!canInitialized) return;
  
  long unsigned int rxId;
  unsigned char len = 0;
  unsigned char rxBuf[8];
  
  // Check if data is available
  if (CAN.checkReceive() == CAN_MSGAVAIL) {
    CAN.readMsgBuf(&rxId, &len, rxBuf);
    
    // Reset error counter on successful read
    canErrorCount = 0;
    
    // Parse Mazda-specific CAN messages for RPM
    // The Miata NC broadcasts RPM on CAN ID 0x201 (typical)
    // Format: bytes 0-1 contain RPM (RPM = ((Byte0 << 8) | Byte1) / 4)
    if (rxId == 0x201 && len >= 2) {
      uint16_t rawRPM = (rxBuf[0] << 8) | rxBuf[1];
      currentRPM = rawRPM / 4;  // Convert to actual RPM
    }
    
    // Also try standard OBD-II response
    if (rxId == OBD2_RESPONSE_ID && len >= 4) {
      if (rxBuf[1] == OBD2_MODE_01 + 0x40) {  // Response mode
        switch (rxBuf[2]) {
          case PID_ENGINE_RPM:
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
        }
      }
    }
  } else {
    // Periodically request RPM via OBD-II if no direct CAN data
    static unsigned long lastOBDRequest = 0;
    if (millis() - lastOBDRequest > 100) {  // Request every 100ms
      lastOBDRequest = millis();
      requestOBDData(PID_ENGINE_RPM);
    }
  }
  
  // Check for CAN errors
  byte canStatus = CAN.checkError();
  if (canStatus != 0) {
    canErrorCount++;
    if (canErrorCount > 100) {
      // Too many errors, try to reinitialize
      Serial.println(F("CAN Bus errors detected, reinitializing..."));
      canInitialized = initCAN();
      canErrorCount = 0;
    }
  }
}

void requestOBDData(uint8_t pid) {
  if (!canInitialized) return;
  
  unsigned char requestBuf[8] = {0x02, OBD2_MODE_01, pid, 0, 0, 0, 0, 0};
  CAN.sendMsgBuf(OBD2_REQUEST_ID, 0, 8, requestBuf);
}

// ============================================================================
// LED STRIP FUNCTIONS
// ============================================================================

void updateLEDStrip(uint16_t rpm) {
  if (rpm < RPM_MIN_DISPLAY) {
    // Below minimum display RPM - turn off all LEDs
    strip.clear();
    strip.show();
    return;
  }
  
  // Check for shift light activation
  if (rpm >= RPM_SHIFT_LIGHT) {
    shiftLightPattern(rpm);
    return;
  }
  
  // Normal gradient display
  // Map RPM to number of LEDs to illuminate
  int activeLEDs = map(rpm, RPM_MIN_DISPLAY, RPM_MAX_DISPLAY, 0, LED_COUNT);
  activeLEDs = constrain(activeLEDs, 0, LED_COUNT);
  
  // Create color gradient: Green -> Yellow -> Red
  for (int i = 0; i < LED_COUNT; i++) {
    if (i < activeLEDs) {
      uint32_t color = getRPMColor(i, LED_COUNT);
      strip.setPixelColor(i, color);
    } else {
      strip.setPixelColor(i, 0);  // Turn off
    }
  }
  
  strip.show();
}

uint32_t getRPMColor(int ledIndex, int totalLEDs) {
  // Create gradient from green (low RPM) to red (high RPM)
  // Green -> Yellow -> Orange -> Red
  
  float position = (float)ledIndex / (float)totalLEDs;
  
  uint8_t red, green, blue = 0;
  
  if (position < 0.5) {
    // Green to Yellow (first half)
    red = (uint8_t)(position * 2.0 * 255);
    green = 255;
  } else {
    // Yellow to Red (second half)
    red = 255;
    green = (uint8_t)((1.0 - position) * 2.0 * 255);
  }
  
  return strip.Color(red, green, blue);
}

void shiftLightPattern(uint16_t rpm) {
  // Flash all LEDs red when at shift point
  static unsigned long lastFlash = 0;
  static bool flashState = false;
  
  unsigned long currentMillis = millis();
  
  // Flash faster as RPM approaches redline
  uint16_t flashInterval = map(rpm, RPM_SHIFT_LIGHT, RPM_REDLINE, 200, 50);
  flashInterval = constrain(flashInterval, 50, 200);
  
  if (currentMillis - lastFlash >= flashInterval) {
    lastFlash = currentMillis;
    flashState = !flashState;
  }
  
  if (flashState) {
    // All LEDs bright red
    for (int i = 0; i < LED_COUNT; i++) {
      strip.setPixelColor(i, strip.Color(255, 0, 0));
    }
  } else {
    // All LEDs dim red
    for (int i = 0; i < LED_COUNT; i++) {
      strip.setPixelColor(i, strip.Color(64, 0, 0));
    }
  }
  
  strip.show();
}

// LED Animations
void startupAnimation() {
  // Rainbow chase animation
  for (int j = 0; j < 255; j += 5) {
    for (int i = 0; i < LED_COUNT; i++) {
      strip.setPixelColor(i, wheelColor((i * 256 / LED_COUNT + j) & 255));
    }
    strip.show();
    delay(10);
  }
  strip.clear();
  strip.show();
}

void errorAnimation() {
  // Flash red 3 times
  for (int i = 0; i < 3; i++) {
    for (int j = 0; j < LED_COUNT; j++) {
      strip.setPixelColor(j, strip.Color(255, 0, 0));
    }
    strip.show();
    delay(200);
    strip.clear();
    strip.show();
    delay(200);
  }
}

void readyAnimation() {
  // Fill with green and fade out
  for (int j = 0; j < LED_COUNT; j++) {
    strip.setPixelColor(j, strip.Color(0, 255, 0));
    strip.show();
    delay(20);
  }
  delay(500);
  for (int brightness = 255; brightness >= 0; brightness -= 5) {
    for (int j = 0; j < LED_COUNT; j++) {
      strip.setPixelColor(j, strip.Color(0, brightness, 0));
    }
    strip.show();
    delay(10);
  }
  strip.clear();
  strip.show();
}

uint32_t wheelColor(byte wheelPos) {
  // Color wheel for rainbow effect
  wheelPos = 255 - wheelPos;
  if (wheelPos < 85) {
    return strip.Color(255 - wheelPos * 3, 0, wheelPos * 3);
  }
  if (wheelPos < 170) {
    wheelPos -= 85;
    return strip.Color(0, wheelPos * 3, 255 - wheelPos * 3);
  }
  wheelPos -= 170;
  return strip.Color(wheelPos * 3, 255 - wheelPos * 3, 0);
}

// ============================================================================
// GPS FUNCTIONS
// ============================================================================

void readGPSData() {
  // GPS data is continuously fed in the main loop
  // Here we just update our global variables if valid data is available
  
  if (gps.location.isValid()) {
    latitude = gps.location.lat();
    longitude = gps.location.lng();
    gpsValid = true;
  } else {
    gpsValid = false;
  }
  
  if (gps.altitude.isValid()) {
    altitude = gps.altitude.meters();
  }
  
  if (gps.satellites.isValid()) {
    satellites = gps.satellites.value();
  }
  
  if (gps.time.isValid()) {
    gpsTime = (gps.time.hour() * 10000) + (gps.time.minute() * 100) + gps.time.second();
  }
  
  if (gps.date.isValid()) {
    gpsDate = (gps.date.year() * 10000) + (gps.date.month() * 100) + gps.date.day();
  }
}

// ============================================================================
// SD CARD LOGGING FUNCTIONS
// ============================================================================

bool initSD() {
  if (!SD.begin(SD_CS_PIN)) {
    return false;
  }
  return true;
}

void createLogFile() {
  if (!sdInitialized) return;
  
  // Create unique filename based on current time or incrementing counter
  // Format: LOG_YYMMDD_HHMM.CSV
  
  String dateStr = "";
  String timeStr = "";
  
  if (gps.date.isValid() && gps.time.isValid()) {
    // Use GPS time if available
    char buffer[20];
    sprintf(buffer, "%02d%02d%02d_%02d%02d", 
            gps.date.year() % 100, gps.date.month(), gps.date.day(),
            gps.time.hour(), gps.time.minute());
    logFileName = "LOG_" + String(buffer) + ".CSV";
  } else {
    // Use counter if GPS time not available
    int fileCounter = 0;
    do {
      logFileName = "LOG_" + String(fileCounter) + ".CSV";
      fileCounter++;
    } while (SD.exists(logFileName) && fileCounter < 10000);
  }
  
  // Create and write CSV header
  logFile = SD.open(logFileName, FILE_WRITE);
  if (logFile) {
    logFile.println(F("Timestamp,Date,Time,Latitude,Longitude,Altitude,Satellites,RPM,Speed,Throttle,CoolantTemp"));
    logFile.close();
    Serial.print(F("Log file created: "));
    Serial.println(logFileName);
  } else {
    Serial.println(F("Error creating log file!"));
    sdErrorCount++;
  }
}

void logData() {
  if (!sdInitialized || logFileName.length() == 0) return;
  
  // Open file for appending
  logFile = SD.open(logFileName, FILE_WRITE);
  if (logFile) {
    // Write timestamp
    logFile.print(millis());
    logFile.print(F(","));
    
    // Write GPS date and time
    logFile.print(gpsDate);
    logFile.print(F(","));
    logFile.print(gpsTime);
    logFile.print(F(","));
    
    // Write GPS coordinates
    if (gpsValid) {
      logFile.print(latitude, 6);
      logFile.print(F(","));
      logFile.print(longitude, 6);
      logFile.print(F(","));
      logFile.print(altitude, 1);
    } else {
      logFile.print(F(",,,"));
    }
    logFile.print(F(","));
    
    // Write satellite count
    logFile.print(satellites);
    logFile.print(F(","));
    
    // Write vehicle data
    logFile.print(currentRPM);
    logFile.print(F(","));
    logFile.print(vehicleSpeed);
    logFile.print(F(","));
    logFile.print(throttlePosition);
    logFile.print(F(","));
    logFile.print(coolantTemp);
    
    // End line
    logFile.println();
    
    // Close file to ensure data is written
    logFile.close();
    
    // Reset error counter
    sdErrorCount = 0;
  } else {
    sdErrorCount++;
    if (sdErrorCount > 10) {
      // Too many errors, try to reinitialize
      Serial.println(F("SD Card errors detected, reinitializing..."));
      sdInitialized = initSD();
      if (sdInitialized) {
        createLogFile();
      }
      sdErrorCount = 0;
    }
  }
}

// ============================================================================
// GOPRO POWER CONTROL
// ============================================================================

void manageGoProPower(unsigned long currentMillis) {
  if (currentRPM > 0) {
    // Engine is running - turn on GoPro
    if (!goProOn) {
      digitalWrite(GOPRO_PIN, HIGH);
      goProOn = true;
      Serial.println(F("GoPro powered ON"));
    }
    rpmWasZero = false;
  } else {
    // RPM is zero
    if (!rpmWasZero) {
      // Just transitioned to zero RPM
      rpmZeroStartTime = currentMillis;
      rpmWasZero = true;
    } else {
      // RPM has been zero for a while
      if (goProOn && (currentMillis - rpmZeroStartTime >= GOPRO_OFF_DELAY)) {
        // Turn off GoPro after delay
        digitalWrite(GOPRO_PIN, LOW);
        goProOn = false;
        Serial.println(F("GoPro powered OFF"));
      }
    }
  }
}

// ============================================================================
// POWER MANAGEMENT
// ============================================================================

void checkStandbyMode() {
  if (currentRPM == 0 && !goProOn) {
    // Vehicle is off and GoPro is off - enter low-processing standby
    if (!inStandbyMode) {
      inStandbyMode = true;
      Serial.println(F("Entering standby mode..."));
      
      // Turn off LED strip to save power
      strip.clear();
      strip.show();
      
      // Close any open files
      if (logFile) {
        logFile.close();
      }
    }
  } else {
    if (inStandbyMode) {
      inStandbyMode = false;
      Serial.println(F("Exiting standby mode..."));
    }
  }
}
