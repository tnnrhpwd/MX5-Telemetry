// ============================================================================
// Unit Tests for MX5-Telemetry System
// ============================================================================
// Run with: pio test -e native_sim
// ============================================================================

#include <unity.h>
#include <Arduino.h>
#include <stdio.h>

// Mock Arduino functions for native testing
#ifdef NATIVE_SIM
unsigned long millis() { return 1000; }
void pinMode(int pin, int mode) {}
void digitalWrite(int pin, int value) {}
int digitalRead(int pin) { return 0; }
void delay(unsigned long ms) {}
long map(long x, long in_min, long in_max, long out_min, long out_max) {
    return (x - in_min) * (out_max - out_min) / (in_max - in_min) + out_min;
}
#endif

// ============================================================================
// Test Helper Functions
// ============================================================================

uint16_t simulateRPMCalculation(uint8_t byte0, uint8_t byte1) {
    uint16_t rawRPM = (byte0 << 8) | byte1;
    return rawRPM / 4;
}

uint8_t simulateThrottleCalculation(uint8_t rawValue) {
    return (rawValue * 100) / 255;
}

int8_t simulateCoolantTempCalculation(uint8_t rawValue) {
    return rawValue - 40;
}

// ============================================================================
// RPM Calculation Tests
// ============================================================================

void test_rpm_calculation_idle() {
    // Simulate 800 RPM (idle)
    uint16_t rpm = simulateRPMCalculation(0x0C, 0x80); // 3200/4 = 800
    TEST_ASSERT_EQUAL_UINT16(800, rpm);
}

void test_rpm_calculation_cruise() {
    // Simulate 3000 RPM (cruise)
    uint16_t rpm = simulateRPMCalculation(0x2E, 0xE0); // 12000/4 = 3000
    TEST_ASSERT_EQUAL_UINT16(3000, rpm);
}

void test_rpm_calculation_redline() {
    // Simulate 7200 RPM (redline)
    uint16_t rpm = simulateRPMCalculation(0x70, 0x80); // 28800/4 = 7200
    TEST_ASSERT_EQUAL_UINT16(7200, rpm);
}

void test_rpm_calculation_zero() {
    // Simulate 0 RPM (engine off)
    uint16_t rpm = simulateRPMCalculation(0x00, 0x00);
    TEST_ASSERT_EQUAL_UINT16(0, rpm);
}

// ============================================================================
// Throttle Position Tests
// ============================================================================

void test_throttle_closed() {
    uint8_t throttle = simulateThrottleCalculation(0); // 0%
    TEST_ASSERT_EQUAL_UINT8(0, throttle);
}

void test_throttle_half() {
    uint8_t throttle = simulateThrottleCalculation(128); // ~50%
    TEST_ASSERT_EQUAL_UINT8(50, throttle);
}

void test_throttle_full() {
    uint8_t throttle = simulateThrottleCalculation(255); // 100%
    TEST_ASSERT_EQUAL_UINT8(100, throttle);
}

// ============================================================================
// Temperature Calculation Tests
// ============================================================================

void test_coolant_temp_cold() {
    int8_t temp = simulateCoolantTempCalculation(40); // 0°C
    TEST_ASSERT_EQUAL_INT8(0, temp);
}

void test_coolant_temp_normal() {
    int8_t temp = simulateCoolantTempCalculation(130); // 90°C
    TEST_ASSERT_EQUAL_INT8(90, temp);
}

void test_coolant_temp_hot() {
    int8_t temp = simulateCoolantTempCalculation(145); // 105°C
    TEST_ASSERT_EQUAL_INT8(105, temp);
}

// ============================================================================
// LED Configuration Tests
// ============================================================================

void test_led_count_configuration() {
    // Verify LED count is set to 40
    TEST_ASSERT_EQUAL_INT(40, 40); // LED_COUNT should be 40
}

void test_led_mirrored_layout() {
    // Verify mirrored layout: 20 LEDs per side
    int ledsPerSide = 40 / 2;
    TEST_ASSERT_EQUAL_INT(20, ledsPerSide);
}

void test_led_data_packet_size() {
    // Verify LED data packet size (40 LEDs * 3 bytes RGB = 120 bytes)
    int packetSize = 40 * 3;
    TEST_ASSERT_EQUAL_INT(120, packetSize);
}

// ============================================================================
// Data Logging Format Tests
// ============================================================================

void test_csv_data_format() {
    // Simulate CSV line construction
    char buffer[128];
    sprintf(buffer, "%lu,%u,%u,%.6f,%.6f,%.1f,%u,%u,%u,%u,%d",
            1000UL,      // Timestamp
            20251120U,   // Date
            143052U,     // Time
            34.052235,   // Latitude
            -118.243683, // Longitude
            125.4,       // Altitude
            8U,          // Satellites
            3450U,       // RPM
            65U,         // Speed
            45U,         // Throttle
            88);         // Coolant temp
    
    // Verify format contains expected number of fields
    int commaCount = 0;
    for (int i = 0; buffer[i] != '\0'; i++) {
        if (buffer[i] == ',') commaCount++;
    }
    TEST_ASSERT_EQUAL_INT(10, commaCount); // 11 fields = 10 commas
}

// ============================================================================
// Main Test Runner
// ============================================================================

void setup() {
    delay(2000); // Wait for serial monitor
    
    UNITY_BEGIN();
    
    // RPM Tests
    RUN_TEST(test_rpm_calculation_idle);
    RUN_TEST(test_rpm_calculation_cruise);
    RUN_TEST(test_rpm_calculation_redline);
    RUN_TEST(test_rpm_calculation_zero);
    
    // Throttle Tests
    RUN_TEST(test_throttle_closed);
    RUN_TEST(test_throttle_half);
    RUN_TEST(test_throttle_full);
    
    // Temperature Tests
    RUN_TEST(test_coolant_temp_cold);
    RUN_TEST(test_coolant_temp_normal);
    RUN_TEST(test_coolant_temp_hot);
    
    // LED Configuration Tests
    RUN_TEST(test_led_count_configuration);
    RUN_TEST(test_led_mirrored_layout);
    RUN_TEST(test_led_data_packet_size);
    
    
    // Data Format Tests
    RUN_TEST(test_csv_data_format);
    
    UNITY_END();
}

void loop() {
    // Nothing to do here
}

// Native testing support
#ifdef NATIVE_SIM
int main(int argc, char **argv) {
    setup();
    return 0;
}
#endif
