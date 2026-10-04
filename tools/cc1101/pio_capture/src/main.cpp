/*
 * CC1101 Raw Bit Capture (v1)
 * ===========================
 * Host: Arduino Nano (ATmega328P)
 * Goal: capture the CC1101's raw demodulated bitstream so we can reverse-engineer
 *       what is transmitting (and later, decode TPMS frames).
 *
 * How it works:
 *   - Puts the CC1101 into "asynchronous serial mode", which pipes the raw
 *     demodulated data out on GDO0 (D2) instead of the packet engine.
 *   - Estimates the noise floor at boot, then sets a trigger ~15 dB above it.
 *   - When a signal appears (RSSI above trigger), samples GDO0 at ~250 kHz into
 *     a RAM buffer and dumps it as a hex string:
 *         CAP <numSamples> <microsTaken> <hexbytes...>
 *
 * Usage:
 *   1. Flash this sketch (replaces the live-monitor sketch).
 *   2. Open the serial monitor at 115200.
 *   3. Press a 315 MHz key fob / garage remote next to the antenna.
 *   4. Each "CAP ..." line is one ~19 ms window of raw samples (8 samples/byte,
 *      LSB = oldest). Save the lines to a file and we decode them together.
 *
 * Wiring is identical to the monitor sketch (see docs/CC1101_BENCH_TEST.md).
 */

#include <Arduino.h>
#include <SPI.h>
#include <SmartRC_CC1101.h>

SmartRC_CC1101 radio;

#define CC1101_SCK   13
#define CC1101_MISO  12
#define CC1101_MOSI  11
#define CC1101_CSN   10
#define CC1101_GDO0  2     // serial data output in async mode
#define CC1101_GDO2  3     // serial clock output (optional)

#define CAP_BYTES       600   // 600 bytes = 4800 samples (~19 ms at ~250 kHz)
#define SAMPLE_DELAY_US 3     // per-sample pacing; with loop overhead ~250 kHz
#define FLOOR_SAMPLES   50    // RSSI reads used to estimate the noise floor

static byte buf[CAP_BYTES];
int trigger = -70;

void setup() {
  Serial.begin(115200);

  radio.setSpiPin(CC1101_SCK, CC1101_MISO, CC1101_MOSI, CC1101_CSN);
  radio.setGDO(CC1101_GDO0, CC1101_GDO2);
  radio.Init();

  radio.setMHZ(315.0);
  radio.setModulation(0);     // 0 = 2-FSK (TPMS is usually FSK); 2 = ASK/OOK
  radio.setDRate(9.6);        // kbps placeholder; tune after the first capture
  radio.setDeviation(19.0);   // kHz
  radio.setRxBW(100.0);       // kHz

  // Asynchronous serial mode: raw demodulated data out on GDO0.
  radio.setPktFormat(3);
  radio.setSyncMode(0);
  radio.setManchester(false);
  radio.setFEC(false);
  radio.setCrc(false);
  radio.setWhiteData(false);
  radio.SpiWriteReg(CC1101_IOCFG0, 0x0D);   // GDO0 = serial data output
  radio.SpiWriteReg(CC1101_IOCFG2, 0x0C);   // GDO2 = serial clock output

  radio.SetRx();

  Serial.print(radio.getCC1101() ? F("CC1101 FOUND\n") : F("CC1101 NOT FOUND\n"));

  // Estimate the noise floor, then set the trigger 15 dB above it.
  long sum = 0;
  for (int i = 0; i < FLOOR_SAMPLES; i++) {
    sum += radio.getRssi();
    delay(20);
  }
  int floorDb = (int)(sum / FLOOR_SAMPLES);
  trigger = floorDb + 15;

  Serial.print(F("FLOOR "));
  Serial.print(floorDb);
  Serial.print(F(" TRIGGER "));
  Serial.println(trigger);
  Serial.println(F("Waiting for a signal. Key a fob near the antenna."));
}

void loop() {
  // Free-run: always capture a window and dump it. The analyzer separates real
  // signals from noise, so we never miss a burst because of the unreliable
  // RSSI gate.
  unsigned long t0 = micros();
  for (int i = 0; i < CAP_BYTES; i++) {
    byte b = 0;
    for (int k = 0; k < 8; k++) {
      b <<= 1;
      if (PIND & 0x04) b |= 1;   // GDO0 on D2 = PD2
      delayMicroseconds(SAMPLE_DELAY_US);
    }
    buf[i] = b;
  }
  unsigned long us = micros() - t0;

  Serial.print(F("CAP "));
  Serial.print(CAP_BYTES * 8);
  Serial.print(' ');
  Serial.print(us);
  Serial.print(' ');
  for (int i = 0; i < CAP_BYTES; i++) {
    if (buf[i] < 0x10) Serial.print('0');
    Serial.print(buf[i], HEX);
  }
  Serial.println();
}
