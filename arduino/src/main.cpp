/*
 * ============================================================================
 * MX5-Telemetry Single Arduino - Optimized CAN + LED Controller
 * ============================================================================
 * 
 * MAXIMUM PERFORMANCE single Arduino solution for Mazda Miata NC telemetry.
 * Combines CAN bus reading and LED strip control on a single Arduino Nano
 * for minimum latency and maximum responsiveness.
 * 
 * ADVANTAGES OVER DUAL ARDUINO:
 * âœ… Zero RPM data corruption (no serial link)
 * âœ… <1ms CAN-to-LED latency (was ~70ms with serial)
 * âœ… 100Hz LED update rate (was 10Hz)
 * âœ… Simpler wiring (no inter-Arduino connection)
 * âœ… Lower power consumption
 * 
 * OPTIMIZATIONS APPLIED:
 * 1. Hardware interrupt for CAN message reception (D2/INT0)
 * 2. Direct port manipulation for LED timing
 * 3. Inline LED update (no function call overhead)
 * 4. Minimal RAM usage with register variables
 * 5. Loop unrolling for critical paths
 * 6. Zero-copy CAN message parsing
 * 
 * LED SEQUENCES (configurable via serial):
 * 1. Center-Out (default): LEDs fill from both edges toward center
 * 2. Left-to-Right: LEDs fill from left to right (2x resolution)
 * 3. Right-to-Left: LEDs fill from right to left
 * 4. Center-In: LEDs fill from center outward to edges
 * 
 * HARDWARE:
 * - Arduino Nano V3.0 (ATmega328P, 16MHz, 5V logic)
 * - MCP2515 CAN Controller + TJA1050 (500 kbaud, 8MHz crystal)
 * - WS2812B LED Strip (20 LEDs)
 * - Optional: Brightness potentiometer on A6
 * - Optional: Haptic motor on D3
 * 
 * PINS:
 * - D2: MCP2515 INT (hardware interrupt - CRITICAL for performance)
 * - D3: Serial RX from Pi/ESP32 (SoftwareSerial for LED sequence commands)
 * - D4: Serial TX to Pi/ESP32 (SoftwareSerial - optional feedback)
 * - D5: WS2812B LED Data
 * - D10: MCP2515 CS (SPI)
 * - D11: MOSI (SPI)
 * - D12: MISO (SPI)
 * - D13: SCK (SPI)
 * - A6: Brightness potentiometer (optional)
 * 
 * VERSION: 1.1.0 - Added LED Sequence Selection with EEPROM persistence
 * DATE: December 16, 2025
 * LICENSE: MIT
 * ============================================================================
 */

#include <Arduino.h>
#include <SPI.h>
#include <mcp_can.h>
#include <Adafruit_NeoPixel.h>
#include <EEPROM.h>
#include <avr/wdt.h>

// ============================================================================
// CONFIGURATION - Tune these for your setup
// ============================================================================

// Pin definitions
#define CAN_CS_PIN          10      // MCP2515 Chip Select (SPI)
#define CAN_INT_PIN         2       // MCP2515 Interrupt (MUST be D2 for INT0)
#define LED_DATA_PIN        5       // WS2812B Data Pin
#define HAPTIC_PIN          6       // Haptic motor PWM (optional) - moved from D3
#define BRIGHTNESS_POT_PIN  A6      // Brightness potentiometer (optional)

// Serial communication pins (for LED sequence commands from Pi/ESP32)
#define SERIAL_RX_PIN       3       // Receive commands from Pi/ESP32
#define SERIAL_TX_PIN       4       // Send acknowledgements (optional)

// LED strip configuration  
#ifndef LED_COUNT
#define LED_COUNT           20      // Number of LEDs in strip
#endif

// Feature toggles - disable to save flash/RAM
#define ENABLE_HAPTIC       false   // Haptic motor feedback at redline
#define ENABLE_BRIGHTNESS   true    // Potentiometer brightness control
#define ENABLE_SERIAL_DEBUG false   // USB serial debugging (disable for production)
#define ENABLE_SERIAL_CMD   true    // Serial commands from Pi/ESP32 for LED sequence

// CAN bus configuration
#define CAN_SPEED           CAN_500KBPS  // MX-5 NC HS-CAN bus speed
#define CAN_CRYSTAL         MCP_8MHZ     // MCP2515 crystal frequency

// Mazda-specific CAN IDs (NC Miata 2006-2015)
#define MAZDA_RPM_CAN_ID    0x201   // Engine RPM broadcast ID
#define MAZDA_SPEED_CAN_ID  0x201   // Vehicle speed (same frame as RPM)

// RPM limits. The colour zones themselves are no longer compile-time constants - they
// live in `rampStops[]`, which the Pi can replace at runtime (see RUNTIME COLOUR RAMP).
// These two remain because they are limits, not preferences.
#define RPM_MAX             6800    // default rpm at which the strip is completely full
#define RPM_REDLINE         6800    // Trigger haptic pulse

// Timing configuration (microseconds for precision)
#define CAN_POLL_INTERVAL   10000   // Poll CAN every 10ms (100Hz)
#define LED_UPDATE_INTERVAL 10000   // Update LEDs every 10ms (100Hz)
#define BRIGHTNESS_INTERVAL 50000   // Read pot every 50ms (20Hz)
#define TIMEOUT_MS          3000    // Error mode if no CAN data for 3 seconds

// EEPROM addresses for persistent settings
#define EEPROM_MAGIC_ADDR   0       // Magic byte to check if EEPROM is initialized
#define EEPROM_SEQ_ADDR     1       // LED sequence setting (1 byte)
#define EEPROM_MAGIC_VALUE  0xA5    // Magic value to verify EEPROM is initialized

// ============================================================================
// LED SEQUENCE MODES
// ============================================================================
enum LEDSequence {
    SEQ_CENTER_OUT = 1,     // Default: Fill from edges toward center (mirrored)
    SEQ_LEFT_TO_RIGHT = 2,  // Fill left to right (double resolution)
    SEQ_RIGHT_TO_LEFT = 3,  // Fill right to left
    SEQ_CENTER_IN = 4,      // Fill from center outward to edges
    SEQ_COUNT = 4           // Total number of sequences
};

// ============================================================================
// GLOBAL OBJECTS & STATE
// ============================================================================

MCP_CAN canBus(CAN_CS_PIN);
Adafruit_NeoPixel strip(LED_COUNT, LED_DATA_PIN, NEO_GRB + NEO_KHZ800);

// ----------------------------------------------------------------------------
// Frame pacing
//
// strip.show() is the slow part of every update: on a 16 MHz AVR it pushes the
// whole strip out with interrupts disabled, so calling it when nothing changed
// costs latency and masks the CAN interrupt for no benefit. Every renderer writes
// into the pixel buffer and calls showIfChanged(), which compares against what was
// last transmitted and skips the transfer when the frame is identical.
// ----------------------------------------------------------------------------
static uint32_t lastShown[LED_COUNT] = {0};
static bool stripForceShow = true;   // set when brightness changes, which pixel values don't show

inline void showIfChanged() {
    bool changed = stripForceShow;
    stripForceShow = false;

    for (uint8_t i = 0; i < LED_COUNT; i++) {
        uint32_t c = strip.getPixelColor(i);
        if (c != lastShown[i]) {
            lastShown[i] = c;
            changed = true;
        }
    }

    if (changed) strip.show();
}

// Runtime colour ramp. Declared up here because the serial command handler (below)
// rewrites it - the table used to be five `#define`s, which meant reflashing to change
// a colour. The last stop doubles as the "full illumination" rpm.
struct RampStop {
    uint16_t rpm;
    uint8_t  r, g, b;
};

#define RAMP_STOP_COUNT 6

RampStop rampStops[RAMP_STOP_COUNT] = {
    {    0,   0,   0, 255 },   // idle - blue
    { 1400,   0, 220, 255 },   // pulling away - cyan
    { 2800,  50, 215, 130 },   // economical cruise - green
    { 4500, 255, 210,  60 },   // waking up - yellow
    { 5800, 255, 128,   0 },   // spirited - orange
    { 6800, 255,   0,   0 },   // redline - red
};

uint8_t  rampStopCount = RAMP_STOP_COUNT;
uint16_t rpmFull = 6800;          // rpm at which the strip is completely full
uint8_t  themeDim = 0;            // 0 = full brightness ramp, 1 = dark-mode (dimmed)

// Use USB Serial for commands from Pi
#if ENABLE_SERIAL_CMD
#define cmdSerial Serial
#endif

// State variables - volatile for interrupt safety
volatile uint16_t g_rpm = 0;
volatile uint8_t g_canDataReceived = 0;  // Flag set by interrupt

// Non-volatile state
uint16_t currentRPM = 0;
float smoothedRPM = 0.0f;  // Exponential moving average for smooth transitions
uint8_t currentBrightness = 255;
bool potEnabled = true;   // false once the app sets a brightness: the pot would fight it
bool errorMode = false;
bool canInitialized = false;

// RPM smoothing configuration - asymmetric + snap for maximum responsiveness.
// Rising revs track the engine one-to-one (no lag at the shift point); falling
// revs keep a light filter so the strip does not trail pixels when the throttle
// closes. Large deltas snap instantly.
#define RPM_SNAP_DELTA     250     // RPM jump that bypasses the filter entirely
#define RPM_ALPHA_RISING   1.00f   // Throttle-on: no filtering at all
#define RPM_ALPHA_FALLING  0.75f   // Lift-off: light settle, still quick

// LED sequence setting (persisted in EEPROM)
uint8_t ledSequence = SEQ_CENTER_OUT;  // Default: center-out (mirrored)

// Last RPM actually painted onto the strip. updateLEDs() runs after every CAN
// read, but the bar can only change when the RPM does; this lets it skip the
// per-LED maths entirely otherwise.
static uint16_t lastRenderedRPM = 0xFFFF;

// Serial command buffer
#if ENABLE_SERIAL_CMD
// 128, not 32: a full RAMP: line is six "<rpm>:<rrggbb>" pairs, which is ~76 characters,
// and the old 32-byte buffer silently truncated it. The parser then saw a partial ramp
// and accepted a two-stop table ending at 1400 rpm - which looked like a working command
// and quietly capped the strip at 1400 rpm.
char cmdBuffer[128];
uint8_t cmdIndex = 0;
#endif

// Bench override: `DEMO:<rpm>` forces the RPM the strip renders, `DEMO:OFF` clears it.
//
// This exists so the strip can be validated with the engine off. The alternative -
// transmitting a synthetic 0x201 frame - would put fake RPM and speed on the car's bus
// where the cluster, ABS and transmission controllers can read it, which is not
// something a diagnostic should ever do. The override only changes what the LED code
// draws; CAN decoding is untouched, and it clears itself after a minute so a forgotten
// command cannot leave a fake tachometer behind.
bool demoForced = false;
uint16_t demoRPM = 0;
unsigned long demoExpiresAt = 0;
#define DEMO_TIMEOUT_MS 60000UL

// CAN diagnostics reported in the STATUS line
unsigned long lastCanIdSeen = 0;
uint16_t frameCount = 0;         // wraps every ~65k frames; only the 1 Hz delta is used

// Timing
unsigned long lastCANPoll = 0;
unsigned long lastLEDUpdate = 0;
unsigned long lastBrightnessRead = 0;
unsigned long lastCANData = 0;

// Animation state for error mode
uint8_t errorScanPosition = 0;
int8_t errorScanDirection = 1;
unsigned long lastErrorAnimation = 0;

// Error display debounce - only show error after continuous timeout
bool displayErrorMode = false;  // Actually show error animation
unsigned long errorStartTime = 0;  // When error condition started
#define ERROR_DEBOUNCE_MS 3000  // 3 seconds before showing error animation

// ---------------------------------------------------------------------------
// Persistent LED configuration
//
// The ramp, brightness and dim flag used to vanish on every power cycle because only
// the fill sequence was stored. They now live in EEPROM behind a magic byte and a CRC,
// so a half-written block (brown-out while saving) is rejected and the firmware keeps
// its compiled-in defaults instead of showing garbage.
//
// EEPROM is rated ~100k writes and is only written on an explicit CFG:save, so dragging
// a brightness slider on the phone cannot wear it out.
// ---------------------------------------------------------------------------
#define EEPROM_CFG_MAGIC_ADDR   2
#define EEPROM_CFG_MAGIC_VALUE  0x5A
#define EEPROM_CFG_ADDR         3
#define EEPROM_CFG_STOP_BYTES   5                       // rpm lo, rpm hi, r, g, b
#define EEPROM_CFG_BODY_BYTES   (5 + RAMP_STOP_COUNT * EEPROM_CFG_STOP_BYTES)  // 5 header + 30
#define EEPROM_CFG_CRC_ADDR     (EEPROM_CFG_ADDR + EEPROM_CFG_BODY_BYTES)

void saveLedConfig();
bool loadLedConfig();

// ============================================================================
// FORWARD DECLARATIONS
// ============================================================================

void updateErrorAnimation();
void loadSettingsFromEEPROM();
void saveSettingsToEEPROM();
void handleSerialCommands();
void setLEDSequence(uint8_t seq);

// ============================================================================
// CAN INTERRUPT HANDLER - Triggered on MCP2515 INT pin falling edge
// ============================================================================
// This ISR is called when MCP2515 has a message ready. We just set a flag
// and read the message in the main loop to avoid SPI in interrupt context.
// ============================================================================

void canInterrupt() {
    g_canDataReceived = 1;
}

// ============================================================================
// EEPROM FUNCTIONS - Persist LED sequence setting across power cycles
// ============================================================================

void loadSettingsFromEEPROM() {
    // Check if EEPROM has been initialized
    if (EEPROM.read(EEPROM_MAGIC_ADDR) != EEPROM_MAGIC_VALUE) {
        // First boot - initialize with defaults
        EEPROM.write(EEPROM_MAGIC_ADDR, EEPROM_MAGIC_VALUE);
        EEPROM.write(EEPROM_SEQ_ADDR, SEQ_CENTER_OUT);
        ledSequence = SEQ_CENTER_OUT;
        #if ENABLE_SERIAL_DEBUG
        Serial.println(F("EEPROM init: defaults"));
        #endif
    } else {
        // Load saved sequence
        uint8_t savedSeq = EEPROM.read(EEPROM_SEQ_ADDR);
        if (savedSeq >= 1 && savedSeq <= SEQ_COUNT) {
            ledSequence = savedSeq;
        } else {
            ledSequence = SEQ_CENTER_OUT;
        }
        #if ENABLE_SERIAL_DEBUG
        Serial.print(F("EEPROM load: seq="));
        Serial.println(ledSequence);
        #endif
    }
}

void saveSettingsToEEPROM() {
    // Only write if value changed (EEPROM has limited write cycles)
    if (EEPROM.read(EEPROM_SEQ_ADDR) != ledSequence) {
        EEPROM.write(EEPROM_SEQ_ADDR, ledSequence);
        #if ENABLE_SERIAL_DEBUG
        Serial.print(F("EEPROM save: seq="));
        Serial.println(ledSequence);
        #endif
    }
}

void saveLedConfig() {
    uint8_t crc = 0;
    EEPROM.update(EEPROM_CFG_ADDR + 0, rampStopCount);   crc ^= rampStopCount;
    EEPROM.update(EEPROM_CFG_ADDR + 1, themeDim);        crc ^= themeDim;
    EEPROM.update(EEPROM_CFG_ADDR + 2, currentBrightness); crc ^= currentBrightness;
    EEPROM.update(EEPROM_CFG_ADDR + 3, lowByte(rpmFull));  crc ^= lowByte(rpmFull);
    EEPROM.update(EEPROM_CFG_ADDR + 4, highByte(rpmFull)); crc ^= highByte(rpmFull);

    for (uint8_t i = 0; i < RAMP_STOP_COUNT; i++) {
        const uint8_t base = EEPROM_CFG_ADDR + 5 + i * EEPROM_CFG_STOP_BYTES;
        const uint8_t vals[EEPROM_CFG_STOP_BYTES] = {
            lowByte(rampStops[i].rpm), highByte(rampStops[i].rpm),
            rampStops[i].r, rampStops[i].g, rampStops[i].b
        };
        for (uint8_t k = 0; k < EEPROM_CFG_STOP_BYTES; k++) {
            EEPROM.update(base + k, vals[k]);
            crc ^= vals[k];
        }
    }

    EEPROM.update(EEPROM_CFG_CRC_ADDR, crc);
    EEPROM.update(EEPROM_CFG_MAGIC_ADDR, EEPROM_CFG_MAGIC_VALUE);
}

bool loadLedConfig() {
    if (EEPROM.read(EEPROM_CFG_MAGIC_ADDR) != EEPROM_CFG_MAGIC_VALUE) {
        return false;   // never saved
    }

    uint8_t crc = 0;
    for (uint8_t a = EEPROM_CFG_ADDR; a < EEPROM_CFG_CRC_ADDR; a++) {
        crc ^= EEPROM.read(a);
    }
    if (crc != EEPROM.read(EEPROM_CFG_CRC_ADDR)) {
        return false;   // torn or corrupted write
    }

    const uint8_t count = EEPROM.read(EEPROM_CFG_ADDR + 0);
    if (count < 2 || count > RAMP_STOP_COUNT) return false;

    const uint16_t full = (uint16_t)EEPROM.read(EEPROM_CFG_ADDR + 3)
                        | ((uint16_t)EEPROM.read(EEPROM_CFG_ADDR + 4) << 8);
    if (full < 2000 || full > 8000) return false;

    // Everything checks out, so commit. Validation happens before any assignment so a
    // rejected block cannot leave the live configuration half-updated.
    rampStopCount = count;
    themeDim = EEPROM.read(EEPROM_CFG_ADDR + 1) ? 1 : 0;
    currentBrightness = EEPROM.read(EEPROM_CFG_ADDR + 2);
    rpmFull = full;
    for (uint8_t i = 0; i < RAMP_STOP_COUNT; i++) {
        const uint8_t base = EEPROM_CFG_ADDR + 5 + i * EEPROM_CFG_STOP_BYTES;
        rampStops[i].rpm = (uint16_t)EEPROM.read(base)
                         | ((uint16_t)EEPROM.read(base + 1) << 8);
        rampStops[i].r = EEPROM.read(base + 2);
        rampStops[i].g = EEPROM.read(base + 3);
        rampStops[i].b = EEPROM.read(base + 4);
    }
    return true;
}

// Print the live configuration so the Pi (or a person with a terminal) can see exactly
// what the strip is using, including whether it survived a power cycle.
inline void printHex2(uint8_t value) {
    if (value < 0x10) cmdSerial.print('0');
    cmdSerial.print(value, HEX);
}

void printLedConfig() {
    cmdSerial.print(F("CFG:seq="));
    cmdSerial.print(ledSequence);
    cmdSerial.print(F(",full="));
    cmdSerial.print(rpmFull);
    cmdSerial.print(F(",dim="));
    cmdSerial.print(themeDim);
    cmdSerial.print(F(",bright="));
    cmdSerial.print(currentBrightness);
    cmdSerial.print(F(",stops="));
    cmdSerial.print(rampStopCount);
    cmdSerial.print(F(",ramp="));
    for (uint8_t i = 0; i < rampStopCount; i++) {
        if (i) cmdSerial.print(',');
        cmdSerial.print(rampStops[i].rpm);
        cmdSerial.print(':');
        printHex2(rampStops[i].r);
        printHex2(rampStops[i].g);
        printHex2(rampStops[i].b);
    }
    cmdSerial.println();
}

void setLEDSequence(uint8_t seq) {
    if (seq >= 1 && seq <= SEQ_COUNT) {
        ledSequence = seq;
        // The whole strip is laid out differently, so repaint from scratch even if
        // the RPM has not changed.
        lastRenderedRPM = 0xFFFF;
        saveSettingsToEEPROM();
        
        #if ENABLE_SERIAL_CMD
        // Send acknowledgement
        cmdSerial.print(F("OK:SEQ:"));
        cmdSerial.println(ledSequence);
        #endif
        
        #if ENABLE_SERIAL_DEBUG
        Serial.print(F("Seq changed: "));
        Serial.println(ledSequence);
        #endif
    }
}

// ============================================================================
// SERIAL COMMAND HANDLER - Process commands from Pi/ESP32
// ============================================================================
// Protocol:
//   SEQ:1  - Set LED sequence to Center-Out (default)
//   SEQ:2  - Set LED sequence to Left-to-Right (2x resolution)
//   SEQ:3  - Set LED sequence to Right-to-Left
//   SEQ:4  - Set LED sequence to Center-In
//   SEQ?   - Query current sequence (responds with SEQ:n)
// ============================================================================

#if ENABLE_SERIAL_CMD
void handleSerialCommands() {
    while (cmdSerial.available()) {
        char c = cmdSerial.read();
        
        if (c == '\n' || c == '\r') {
            if (cmdIndex > 0) {
                cmdBuffer[cmdIndex] = '\0';
                
                // Parse command
                if (strncmp(cmdBuffer, "SEQ:", 4) == 0) {
                    // Set sequence: SEQ:1, SEQ:2, etc.
                    int seq = atoi(cmdBuffer + 4);
                    setLEDSequence(seq);
                }
                else if (strcmp(cmdBuffer, "SEQ?") == 0) {
                    // Query current sequence
                    cmdSerial.print(F("SEQ:"));
                    cmdSerial.println(ledSequence);
                }
                else if (strcmp(cmdBuffer, "PING") == 0) {
                    // Health check
                    cmdSerial.println(F("PONG"));
                }
                else if (strncmp(cmdBuffer, "RAMP:", 5) == 0) {
                    // RAMP:<rpm>:<rrggbb>,<rpm>:<rrggbb>,...  (the last stop is "full")
                    uint8_t count = 0;
                    char* p = cmdBuffer + 5;
                    while (*p && count < RAMP_STOP_COUNT) {
                        uint16_t rpm = 0;
                        while (*p >= '0' && *p <= '9') { rpm = (uint16_t)(rpm * 10 + (*p - '0')); p++; }
                        if (*p != ':') break;
                        p++;
                        uint32_t rgb = 0;
                        uint8_t digits = 0;
                        while (digits < 6 && *p) {
                            char c = *p;
                            uint8_t v;
                            if (c >= '0' && c <= '9')      v = (uint8_t)(c - '0');
                            else if (c >= 'A' && c <= 'F') v = (uint8_t)(c - 'A' + 10);
                            else if (c >= 'a' && c <= 'f') v = (uint8_t)(c - 'a' + 10);
                            else break;
                            rgb = (rgb << 4) | v;
                            p++;
                            digits++;
                        }
                        if (digits != 6) break;
                        rampStops[count].rpm = rpm;
                        rampStops[count].r = (uint8_t)(rgb >> 16);
                        rampStops[count].g = (uint8_t)(rgb >> 8);
                        rampStops[count].b = (uint8_t)rgb;
                        count++;
                        if (*p == ',') { p++; } else { break; }
                    }
                    if (count >= 2) {
                        rampStopCount = count;
                        rpmFull = rampStops[count - 1].rpm;
                        lastRenderedRPM = 0xFFFF;   // force a repaint
                        cmdSerial.println(F("OK:RAMP"));
                    } else {
                        cmdSerial.println(F("ERR:RAMP"));
                    }
                }
                else if (strncmp(cmdBuffer, "CFG:", 4) == 0) {
                    // CFG:bright=<0-255>,theme=<0|1>,full=<rpm>
                    char* p = cmdBuffer + 4;
                    while (*p) {
                        if (strncmp(p, "bright=", 7) == 0) {
                            int v = atoi(p + 7);
                            if (v < 0) v = 0;
                            if (v > 255) v = 255;
                            currentBrightness = (uint8_t)v;
                            strip.setBrightness(currentBrightness);
                            potEnabled = false;      // app owns brightness now
                            stripForceShow = true;
                        } else if (strncmp(p, "theme=", 6) == 0) {
                            themeDim = (atoi(p + 6) != 0) ? 1 : 0;
                            lastRenderedRPM = 0xFFFF;
                        } else if (strncmp(p, "full=", 5) == 0) {
                            int v = atoi(p + 5);
                            if (v < 2000) v = 2000;
                            if (v > 8000) v = 8000;
                            rpmFull = (uint16_t)v;
                            lastRenderedRPM = 0xFFFF;
                        } else if (strncmp(p, "pot=", 4) == 0) {
                            potEnabled = (atoi(p + 4) != 0);
                        } else if (strncmp(p, "save", 4) == 0) {
                            // Explicit, not automatic: a brightness slider drag must not
                            // burn EEPROM write cycles.
                            saveLedConfig();
                            cmdSerial.println(F("OK:SAVE"));
                        } else if (strncmp(p, "reset", 5) == 0) {
                            // Soft reboot, so a save can be proved to survive one.
                            cmdSerial.println(F("OK:RESET"));
                            cmdSerial.flush();
                            delay(50);
                            wdt_enable(WDTO_15MS);
                            for (;;) { }
                        }
                        char* comma = strchr(p, ',');
                        if (!comma) break;
                        p = comma + 1;
                    }
                    cmdSerial.println(F("OK:CFG"));
                }
                else if (strcmp(cmdBuffer, "CFG?") == 0) {
                    printLedConfig();
                }
                else if (strncmp(cmdBuffer, "DEMO:", 5) == 0) {
                    // Bench override, see demoForced. "DEMO:OFF" hands control back to CAN.
                    if (strcmp(cmdBuffer + 5, "OFF") == 0) {
                        demoForced = false;
                        cmdSerial.println(F("OK:DEMO_OFF"));
                    } else {
                        uint16_t rpm = (uint16_t)atoi(cmdBuffer + 5);
                        if (rpm > RPM_MAX) rpm = RPM_MAX;
                        demoRPM = rpm;
                        demoForced = true;
                        demoExpiresAt = millis() + DEMO_TIMEOUT_MS;
                        cmdSerial.print(F("OK:DEMO:"));
                        cmdSerial.println(demoRPM);
                    }
                }
                
                cmdIndex = 0;
            }
        } else if (cmdIndex < sizeof(cmdBuffer) - 1) {
            cmdBuffer[cmdIndex++] = c;
        }
    }
}
#endif

// ============================================================================
// CAN BUS FUNCTIONS
// ============================================================================

bool initCAN() {
    #if ENABLE_SERIAL_DEBUG
    Serial.print(F("CAN init... "));
    #endif
    
    if (canBus.begin(MCP_ANY, CAN_SPEED, CAN_CRYSTAL) != CAN_OK) {
        #if ENABLE_SERIAL_DEBUG
        Serial.println(F("FAIL"));
        #endif
        return false;
    }
    
    // Set masks to accept all messages (no filtering)
    canBus.init_Mask(0, 0, 0x00000000);
    canBus.init_Mask(1, 0, 0x00000000);
    
    // LISTEN-ONLY mode: Does NOT send ACKs or any data on the CAN bus
    // The car's ECU and other modules already ACK each other - we just eavesdrop
    canBus.setMode(MCP_LISTENONLY);
    
    // Attach hardware interrupt for message reception
    pinMode(CAN_INT_PIN, INPUT);
    attachInterrupt(digitalPinToInterrupt(CAN_INT_PIN), canInterrupt, FALLING);
    
    #if ENABLE_SERIAL_DEBUG
    Serial.println(F("OK"));
    #endif
    
    return true;
}

// Fast inline CAN message reading - optimized for RPM extraction
inline void readCANMessages() {
    unsigned long rxId;
    uint8_t len;
    uint8_t rxBuf[8];
    
    // Read all available messages
    while (canBus.checkReceive() == CAN_MSGAVAIL) {
        if (canBus.readMsgBuf(&rxId, &len, rxBuf) == CAN_OK) {
            // Any valid CAN message received - reset timeout and clear ALL error flags
            lastCANData = millis();
            errorMode = false;
            displayErrorMode = false;  // Immediately stop error animation

            // Diagnostics: which ids and how many frames actually reach the controller.
            // A strip that stays blue because its own CAN link is silent looks identical
            // to one that is being told "0 rpm", and these two numbers are the difference.
            lastCanIdSeen = rxId & 0x7FFFFFFF;
            frameCount++;

            // Parse Mazda RPM message (ID 0x201)
            // Format: bytes 0-1 = RPM * 4 (big endian)
            // Mask out extended ID flag (bit 31) for comparison
            unsigned long canId = rxId & 0x7FFFFFFF;
            if (canId == MAZDA_RPM_CAN_ID && len >= 2) {
                uint16_t rawRPM = ((uint16_t)rxBuf[0] << 8) | rxBuf[1];
                uint16_t instantRPM = rawRPM >> 2;  // Divide by 4 using bit shift
                
                // Asymmetric adaptive smoothing: track rising RPM fast (so the
                // tach sweeps up instantly when you open the throttle), settle
                // falling RPM smoothly, and snap straight to the reading on big
                // deltas (gear changes). Equivalent to an EMA but the alpha is
                // chosen per-sample based on direction and magnitude.
                if (smoothedRPM == 0.0f) {
                    smoothedRPM = instantRPM;  // Initialize on first reading
                } else {
                    float delta = (float)instantRPM - smoothedRPM;
                    float absDelta = delta < 0.0f ? -delta : delta;

                    if (absDelta >= RPM_SNAP_DELTA) {
                        // Gear change / hard throttle stab - zero lag
                        smoothedRPM = instantRPM;
                    } else {
                        float alpha = (delta >= 0.0f) ? RPM_ALPHA_RISING : RPM_ALPHA_FALLING;
                        smoothedRPM += alpha * delta;
                    }
                }
                
                currentRPM = (uint16_t)(smoothedRPM + 0.5f);  // Round to nearest integer
            }
        }
    }
    
    g_canDataReceived = 0;  // Clear interrupt flag
}

// ============================================================================
// LED FUNCTIONS - Highly optimized for speed
// ============================================================================

// Fast RGB color set without function call overhead
#define SET_LED(idx, r, g, b) strip.setPixelColor(idx, strip.Color(r, g, b))
#define CLEAR_LED(idx) strip.setPixelColor(idx, 0)

// RUNTIME COLOUR RAMP
// ============================================================================
// The ramp used to be five `#define`s compiled into the colour maths, so changing a
// zone meant reflashing. It is now a small table (rpm, colour) that the Pi can replace
// at runtime, which is what lets the strip follow the phone's theme, or a hand-picked
// set of colours, without a rebuild. The last stop is also the "full illumination" rpm.

inline void rampColorAtRpm(uint16_t rpm, uint8_t* r, uint8_t* g, uint8_t* b) {
    if (rpm <= rampStops[0].rpm) {
        *r = rampStops[0].r; *g = rampStops[0].g; *b = rampStops[0].b;
        return;
    }
    for (uint8_t i = 1; i < rampStopCount; i++) {
        if (rpm > rampStops[i].rpm) continue;
        const RampStop& a = rampStops[i - 1];
        const RampStop& z = rampStops[i];
        uint16_t span = z.rpm - a.rpm;
        float t = span ? (float)(rpm - a.rpm) / (float)span : 1.0f;
        *r = (uint8_t)((float)a.r + ((float)((int)z.r - (int)a.r) * t) + 0.5f);
        *g = (uint8_t)((float)a.g + ((float)((int)z.g - (int)a.g) * t) + 0.5f);
        *b = (uint8_t)((float)a.b + ((float)((int)z.b - (int)a.b) * t) + 0.5f);
        return;
    }
    *r = rampStops[rampStopCount - 1].r;
    *g = rampStops[rampStopCount - 1].g;
    *b = rampStops[rampStopCount - 1].b;
}

// Where this LED sits along the current fill direction, in LED slots from the root.
// Mirrored sequences have two LEDs per rank, so the "length" is half the strip.
inline uint8_t barRank(uint8_t index) {
    const uint8_t half = LED_COUNT / 2;
    switch (ledSequence) {
        case SEQ_LEFT_TO_RIGHT: return index;
        case SEQ_RIGHT_TO_LEFT: return (LED_COUNT - 1) - index;
        case SEQ_CENTER_IN:     return (index < half) ? (uint8_t)(half - 1 - index)
                                                      : (uint8_t)(index - half);
        case SEQ_CENTER_OUT:
        default:                return (index < half) ? index
                                                      : (uint8_t)((LED_COUNT - 1) - index);
    }
}

inline uint8_t barSlots() {
    return (ledSequence == SEQ_LEFT_TO_RIGHT || ledSequence == SEQ_RIGHT_TO_LEFT)
           ? (uint8_t)LED_COUNT : (uint8_t)(LED_COUNT / 2);
}

// Draw the bar for `rpm`.
//
// Colour is sampled from each LED's *share of the current rpm*, not from a fixed
// position on the strip. That is the difference between a static rainbow that grows and
// a ramp that flows: the tip is always the colour of the present rpm, the root stays at
// the bottom of the ramp, and every LED in between shifts continuously as the engine
// revs. It also removes the old single-frame jump when the leading edge crossed a zone.
inline void renderBar(uint16_t rpm) {
    if (rpm > rpmFull) rpm = rpmFull;

    const uint8_t slots = barSlots();
    // Fill length in LED units: 1 at idle (one LED is always lit) up to `slots` at rpmFull.
    // Kept fractional so the colour position moves continuously rather than in steps.
    float fill = 1.0f + ((float)rpm * (float)(slots - 1)) / (float)rpmFull;
    uint8_t full = (uint8_t)fill;
    float frac = fill - (float)full;
    float span = (fill > 1.0f) ? (fill - 1.0f) : 1.0f;

    for (uint8_t i = 0; i < LED_COUNT; i++) {
        uint8_t rank = barRank(i);
        float level;

        if (rank < full) {
            level = 1.0f;
        } else if (rank == full && frac > 0.05f) {
            level = frac;
        } else {
            CLEAR_LED(i);
            continue;
        }

        float p = (float)rank / span;
        if (p > 1.0f) p = 1.0f;

        uint8_t r, g, b;
        rampColorAtRpm((uint16_t)(p * (float)rpm), &r, &g, &b);

        uint8_t scale = themeDim ? 170 : 255;   // dark mode is dimmer by design
        SET_LED(i,
                (uint8_t)((uint16_t)r * level * scale / 255),
                (uint8_t)((uint16_t)g * level * scale / 255),
                (uint8_t)((uint16_t)b * level * scale / 255));
    }
    showIfChanged();
}

// CAN-offline pattern: two edge pixels blinking orange once a second.
//
// This exists because "the CAN controller never came up" used to look *exactly* like a
// healthy engine at 0 rpm: both ended in the blue two-pixel idle state, and the build
// ships with serial debug off, so nothing anywhere said which one it was. Diagnosing
// "the strip is always blue" then means guessing at wiring instead of reading the strip.
inline void drawCanOffline() {
    bool on = ((millis() / 500) & 1) != 0;
    strip.clear();
    if (on) {
        SET_LED(0, 255, 80, 0);
        SET_LED(LED_COUNT - 1, 255, 80, 0);
    }
    showIfChanged();
}

// Main LED update - inline for maximum speed
inline void updateLEDs() {
    // Checked before the error animation: a controller that never initialised is a
    // different fault from a bus that went quiet, and they get different patterns.
    if (!canInitialized) {
        drawCanOffline();
        return;
    }

    // Bench override: the strip renders this RPM instead of the engine's. It only
    // changes what is drawn - CAN decoding above is untouched - and it self-clears so a
    // forgotten command cannot leave a fake tachometer on the strip.
    if (demoForced) {
        if (millis() > demoExpiresAt) {
            demoForced = false;
        } else {
            currentRPM = demoRPM;
        }
    }

    if (displayErrorMode) {
        updateErrorAnimation();
        // Force a repaint when error mode ends: the scanner pattern must not be
        // mistaken for "already rendered this RPM".
        lastRenderedRPM = 0xFFFF;
        return;
    }

    // Recomputing 20 LED colours is not free on a 16 MHz AVR, and this runs after
    // every CAN read - which happens at the frame rate, not at the LED rate. The
    // bar can only change when the RPM changes, so that is the gate.
    if (currentRPM == lastRenderedRPM && !stripForceShow) {
        return;
    }
    lastRenderedRPM = currentRPM;
    
    // RPM = 0: Show single blue LED based on sequence mode
    if (currentRPM == 0) {
        strip.clear();
        switch (ledSequence) {
            case SEQ_LEFT_TO_RIGHT:
                SET_LED(0, 0, 0, 255);  // Left edge only
                break;
            case SEQ_RIGHT_TO_LEFT:
                SET_LED(LED_COUNT - 1, 0, 0, 255);  // Right edge only
                break;
            case SEQ_CENTER_IN:
                SET_LED(LED_COUNT / 2, 0, 0, 255);  // Center only
                break;
            case SEQ_CENTER_OUT:
            default:
                SET_LED(0, 0, 0, 255);
                SET_LED(LED_COUNT - 1, 0, 0, 255);  // Both edges
                break;
        }
        showIfChanged();
        return;
    }
    
    // Dispatch to the shared renderer. The four sequences only differ in the order the
    // LEDs fill, which barRank() encodes, so there is one code path for colour and fill.
    renderBar(currentRPM);
    
    // Haptic feedback at redline
    #if ENABLE_HAPTIC
    if (currentRPM >= RPM_REDLINE) {
        static unsigned long lastHapticPulse = 0;
        if (millis() - lastHapticPulse >= 500) {
            analogWrite(HAPTIC_PIN, 128);
            delay(50);
            analogWrite(HAPTIC_PIN, 0);
            lastHapticPulse = millis();
        }
    }
    #endif
}

// Error animation - Cylon scanner effect
void updateErrorAnimation() {
    unsigned long now = millis();
    
    // Update scanner position every 30ms
    if (now - lastErrorAnimation >= 30) {
        lastErrorAnimation = now;
        errorScanPosition += errorScanDirection;
        
        if (errorScanPosition >= LED_COUNT - 1) {
            errorScanPosition = LED_COUNT - 1;
            errorScanDirection = -1;
        } else if (errorScanPosition == 0) {
            errorScanDirection = 1;
        }
    }
    
    // Pulsing background
    uint8_t baseBrightness = 20 + 30 * ((now / 100) % 10 > 5 ? 1 : 0);
    
    // Draw scanner
    for (uint8_t i = 0; i < LED_COUNT; i++) {
        uint8_t dist = abs((int8_t)i - (int8_t)errorScanPosition);
        
        if (dist == 0) {
            SET_LED(i, 255, 80, 40);  // Scanner head - bright
        } else if (dist <= 3) {
            uint8_t trail = 200 - (dist * 50);
            SET_LED(i, trail, trail / 8, 0);  // Trail
        } else {
            SET_LED(i, baseBrightness, 0, 0);  // Background pulse
        }
    }
    
    strip.show();
}

// ============================================================================
// BRIGHTNESS CONTROL (Optional)
// ============================================================================

#if ENABLE_BRIGHTNESS
inline void updateBrightness() {
    // Once the app has taken ownership of brightness, stop reading the pot: it is
    // unconnected on this build (the pin floats), so it would otherwise fight the app
    // with a random value.
    if (!potEnabled) return;
    
    // Read potentiometer and invert (clockwise = brighter)
    int potValue = 1023 - analogRead(BRIGHTNESS_POT_PIN);
    uint8_t newBrightness = potValue >> 2;  // 0-1023 â†’ 0-255
    
    // Only update if changed significantly (avoid flicker)
    if (abs((int16_t)newBrightness - (int16_t)currentBrightness) > 2) {
        currentBrightness = newBrightness;
        strip.setBrightness(currentBrightness);
        stripForceShow = true;   // pixel values are unchanged, but the output is not
    }
}
#endif

// ============================================================================
// STARTUP ANIMATION
// ============================================================================

void startupAnimation() {
    // Ensure full brightness for startup (ignore pot during animation)
    strip.setBrightness(255);
    
    // Quick green flash to show LEDs are working
    for (uint8_t i = 0; i < LED_COUNT; i++) {
        strip.setPixelColor(i, strip.Color(0, 255, 0));
    }
    strip.show();
    delay(200);
    
    // Rainbow wave from edges to center
    for (uint8_t cycle = 0; cycle < 2; cycle++) {
        for (uint16_t phase = 0; phase < 256; phase += 8) {
            for (uint8_t i = 0; i < LED_COUNT; i++) {
                int distFromCenter = abs((int)i - (LED_COUNT / 2));
                uint16_t hue = ((uint32_t)distFromCenter * 65536L / (LED_COUNT / 2) + phase * 256) & 0xFFFF;
                strip.setPixelColor(i, strip.gamma32(strip.ColorHSV(hue, 255, 255)));
            }
            strip.show();
            delay(15);
        }
    }
    
    // Fade to blue idle state (shows it's ready)
    for (int step = 0; step < 20; step++) {
        for (uint8_t i = 0; i < LED_COUNT; i++) {
            if (i == 0 || i == LED_COUNT - 1) {
                // Edge LEDs fade to blue
                uint8_t blue = (step * 255) / 20;
                strip.setPixelColor(i, strip.Color(0, 0, blue));
            } else {
                // Middle LEDs fade out
                uint8_t brightness = 255 - (step * 255 / 20);
                strip.setPixelColor(i, strip.Color(brightness/4, brightness/4, brightness/4));
            }
        }
        strip.show();
        delay(30);
    }
    
    // End with blue edge LEDs (idle state)
    strip.clear();
    strip.setPixelColor(0, strip.Color(0, 0, 255));
    strip.setPixelColor(LED_COUNT - 1, strip.Color(0, 0, 255));
    strip.show();
    delay(500);
}

// ============================================================================
// SETUP
// ============================================================================

void setup() {
    #if ENABLE_SERIAL_DEBUG
    Serial.begin(115200);
    Serial.println(F("MX5-Single v1.1"));
    #elif ENABLE_SERIAL_CMD
    // Initialize USB Serial for commands from Pi at 9600 baud
    Serial.begin(9600);
    #endif
    
    // Clear any watchdog reset flag left by CFG:reset, and make sure the watchdog is off:
    // the bootloader does not always clear WDRF, and an armed watchdog would reboot the
    // strip mid-drive.
    MCUSR = 0;
    wdt_disable();
    
    // Load LED sequence from EEPROM
    loadSettingsFromEEPROM();
    
    #if ENABLE_SERIAL_DEBUG
    Serial.print(F("LED Seq: "));
    Serial.println(ledSequence);
    #endif
    
    // Restore the ramp / brightness / dim flag if a complete, CRC-valid block is stored.
    if (loadLedConfig()) {
        potEnabled = false;   // the saved brightness is authoritative, not the floating pot
        #if ENABLE_SERIAL_DEBUG
        Serial.println(F("EEPROM load: LED config restored"));
        #endif
    }
    
    // Initialize serial for LED sequence commands from Pi/ESP32
    #if ENABLE_SERIAL_CMD && !defined(ENABLE_SERIAL_DEBUG)
    // Already initialized Serial above
    #endif
    
    // Initialize haptic motor
    #if ENABLE_HAPTIC
    pinMode(HAPTIC_PIN, OUTPUT);
    analogWrite(HAPTIC_PIN, 0);
    #endif
    
    // Initialize LED strip
    strip.begin();
    strip.setBrightness(currentBrightness);
    strip.clear();
    strip.show();
    
    // Startup animation
    startupAnimation();
    
    // Initialize CAN bus
    canInitialized = initCAN();
    
    if (!canInitialized) {
        errorMode = true;
        #if ENABLE_SERIAL_DEBUG
        Serial.println(F("CAN init failed!"));
        #endif
    }
    
    lastCANData = millis();
    
    #if ENABLE_SERIAL_DEBUG
    Serial.println(F("Ready"));
    #endif
}

// ============================================================================
// MAIN LOOP - Optimized for minimum latency
// ============================================================================

void loop() {
    unsigned long now = micros();
    unsigned long nowMs = millis();
    
    // ========================================================================
    // SERIAL COMMAND PROCESSING - Handle LED sequence commands from Pi/ESP32
    // ========================================================================
    #if ENABLE_SERIAL_CMD
    handleSerialCommands();
    #endif
    
    // ========================================================================
    // CAN BUS READING - Highest priority
    // ========================================================================
    // Check if interrupt flagged new data OR poll interval elapsed
    if (g_canDataReceived || (now - lastCANPoll >= CAN_POLL_INTERVAL)) {
        lastCANPoll = now;
        
        if (canInitialized) {
            readCANMessages();
        }
        // Paint even when the controller never initialised: updateLEDs() then shows the
        // CAN-offline pattern. Skipping the paint here is what left the strip sitting on
        // the startup blues forever with no indication of a fault.
        updateLEDs();
        lastLEDUpdate = now;
    }
    
    // ========================================================================
    // TIMEOUT CHECK - Enter error mode if no CAN data (with debounce)
    // ========================================================================
    // `!canInitialized` deliberately counts as "no data": a controller that never came
    // up would otherwise not trip the watchdog at all, which is how a dead CAN link used
    // to present as a perfectly healthy idle engine.
    if (!canInitialized || (nowMs - lastCANData > TIMEOUT_MS)) {
        if (!errorMode) {
            errorMode = true;
            errorStartTime = nowMs;  // Start debounce timer
        }
        // Only show error animation after debounce period (3 seconds)
        if (!displayErrorMode && (nowMs - errorStartTime >= ERROR_DEBOUNCE_MS)) {
            displayErrorMode = true;
            #if ENABLE_SERIAL_DEBUG
            Serial.println(F("Error display ON"));
            #endif
        }
    } else {
        errorMode = false;
        displayErrorMode = false;
    }
    
    // ========================================================================
    // LED UPDATE - 100Hz for smooth animation
    // ========================================================================
    if (now - lastLEDUpdate >= LED_UPDATE_INTERVAL) {
        lastLEDUpdate = now;
        updateLEDs();
    }
    
    // ========================================================================
    // BRIGHTNESS UPDATE - 20Hz is plenty for potentiometer
    // ========================================================================
    #if ENABLE_BRIGHTNESS
    if (now - lastBrightnessRead >= BRIGHTNESS_INTERVAL) {
        lastBrightnessRead = now;
        updateBrightness();
    }
    #endif
    
    // ========================================================================
    // SERIAL STATUS - once a second, always in the shipped build
    // ========================================================================
    // TX-only, ~40 bytes/s (about 4% of 9600 baud) and buffered by the UART, so it costs
    // nothing in LED latency. It is the only way to tell a working strip from a silent
    // one without a scope: CAN=0 means the MCP2515 never came up, CAN=1 with RPM=0 means
    // the controller is fine but no engine frame is arriving.
    #if ENABLE_SERIAL_CMD
    static unsigned long lastStatusReport = 0;
    static uint16_t lastFrameCount = 0;
    if (nowMs - lastStatusReport >= 1000) {
        lastStatusReport = nowMs;
        cmdSerial.print(F("STATUS:CAN="));
        cmdSerial.print(canInitialized ? 1 : 0);
        cmdSerial.print(F(",RPM="));
        cmdSerial.print(currentRPM);
        cmdSerial.print(F(",SEQ="));
        cmdSerial.print(ledSequence);
        cmdSerial.print(F(",ERR="));
        cmdSerial.print(errorMode ? 1 : 0);
        cmdSerial.print(F(",FPS="));
        cmdSerial.print((uint16_t)(frameCount - lastFrameCount));
        lastFrameCount = frameCount;
        cmdSerial.print(F(",LAST=0x"));
        if (lastCanIdSeen < 0x100) cmdSerial.print('0');
        if (lastCanIdSeen < 0x10) cmdSerial.print('0');
        cmdSerial.print(lastCanIdSeen, HEX);
        cmdSerial.print(F(",FULL="));
        cmdSerial.print(rpmFull);
        cmdSerial.print(F(",DIM="));
        cmdSerial.print(themeDim);
        if (demoForced) {
            cmdSerial.print(F(",DEMO="));
            cmdSerial.print(demoRPM);
        }
        cmdSerial.println();
    }
    #endif
    
    // ========================================================================
    // SERIAL DEBUG OUTPUT (if enabled)
    // ========================================================================
    #if ENABLE_SERIAL_DEBUG
    static unsigned long lastDebug = 0;
    if (nowMs - lastDebug >= 1000) {
        lastDebug = nowMs;
        Serial.print(F("RPM:"));
        Serial.print(currentRPM);
        Serial.print(F(" SEQ:"));
        Serial.print(ledSequence);
        Serial.print(F(" ERR:"));
        Serial.println(errorMode ? 'Y' : 'N');
    }
    #endif
}
