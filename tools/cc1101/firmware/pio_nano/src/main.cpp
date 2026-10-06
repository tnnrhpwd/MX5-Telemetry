/*
 * CC1101 Bedroom Signal Scan — Bench Test (PlatformIO build)
 * ==========================================================
 * Host: Arduino Nano (ATmega328P, 5V logic)
 * Goal: prove the CC1101 module powers up, talks SPI, and hears RF energy
 *       before we build the real 315 MHz TPMS decoder.
 *
 * Wiring (Nano -> CC1101 module, 8-pin header):
 *   pin 2 VCC  -> 3V3   (module has NO regulator; VCC range 1.8-3.6 V)
 *   pin 1 GND  -> GND
 *   pin 5 SCK  -> D13   (5V->3.3V divider recommended; direct OK for a quick test)
 *   pin 6 MOSI -> D11   (divider recommended)
 *   pin 7 MISO <- D12   (direct — 3.3V out is safe into 5V input)
 *   pin 4 CSN  -> D10   (divider recommended)
 *   pin 3 GDO0 -> D2    (direct)
 *   pin 8 GDO2 -> D3    (direct, optional)
 *
 * Library: SmartRC-CC1101-Driver-Lib (declared in platformio.ini).
 */

#include <Arduino.h>
#include <SPI.h>
#include <SmartRC_CC1101.h>

SmartRC_CC1101 radio;

// Nano wiring (library defaults for Uno/Nano, listed explicitly for clarity)
#define CC1101_SCK   13
#define CC1101_MISO  12
#define CC1101_MOSI  11
#define CC1101_CSN   10
#define CC1101_GDO0  2
#define CC1101_GDO2  3

// Anything above this RSSI in the monitor phase counts as "a real signal".
#define SIGNAL_THRESHOLD_DBM  (-85)

float currentMHz = 315.0;

void sweepBand(float startMHz, float stopMHz, float stepMHz) {
  for (float f = startMHz; f <= stopMHz + 1e-6; f += stepMHz) {
    radio.setMHZ(f);
    radio.SetRx();
    delay(5);                       // let PLL settle + RSSI register update
    int rssi = radio.getRssi();
    Serial.print(F("F="));
    Serial.print(f, 1);
    Serial.print(F(" MHz   RSSI="));
    Serial.print(rssi);
    Serial.println(F(" dBm"));
  }
}

void setup() {
  Serial.begin(115200);
  unsigned long t0 = millis();
  while (!Serial && (millis() - t0) < 2000) { /* wait for USB serial, bounded */ }

  Serial.println(F("\n--- CC1101 Bench Scan ---"));

  // Must be called BEFORE Init().
  radio.setSpiPin(CC1101_SCK, CC1101_MISO, CC1101_MOSI, CC1101_CSN);
  radio.setGDO(CC1101_GDO0, CC1101_GDO2);

  radio.Init();
  radio.setMHZ(315.0);
  radio.SetRx();

  if (radio.getCC1101()) {
    Serial.println(F("CC1101: FOUND  (SPI link + chip OK)"));
  } else {
    Serial.println(F("CC1101: NOT FOUND — check wiring, VCC and GND"));
  }

  Serial.println(F("\nSweep 300.0 - 348.0 MHz (your TPMS band)..."));
  sweepBand(300.0, 348.0, 1.0);

  Serial.println(F("\nSweep 430.0 - 435.0 MHz (common 433 devices, sanity check)..."));
  sweepBand(430.0, 435.0, 0.5);

  // Return to the band we actually care about and monitor live.
  radio.setMHZ(315.0);
  radio.SetRx();

  Serial.println(F("\nMonitoring 315.000 MHz (RSSI updated 4x/sec)."));
  Serial.println(F("A quiet bedroom should sit around -90..-105 dBm."));
  Serial.println(F("Press a key fob or garage remote near the antenna to see a spike.\n"));
}

void loop() {
  // Handle band-change commands from the PC (e.g. "FREQ 434.0").
  while (Serial.available()) {
    String cmd = Serial.readStringUntil('\n');
    cmd.trim();
    if (cmd.startsWith("FREQ ")) {
      float f = cmd.substring(5).toFloat();
      if (f >= 200.0f && f <= 930.0f) {
        currentMHz = f;
        radio.setMHZ(f);
        radio.SetRx();
        Serial.print(F("FREQ_OK "));
        Serial.println(f, 3);
      }
    }
  }

  static unsigned long last = 0;
  if (millis() - last >= 50) {
    last = millis();

    long sum = 0;
    const int N = 10;
    for (int i = 0; i < N; i++) {
      sum += radio.getRssi();
      delay(3);
    }
    int rssi = (int)(sum / N);

    Serial.print(currentMHz, 3);
    Serial.print(F(" MHz   RSSI="));
    Serial.print(rssi);
    Serial.println(F(" dBm"));
  }
}
