/*
 * CC1101 loopback test
 * ====================
 * Drives TWO CC1101 modules on the same Nano over one shared SPI bus:
 *
 *   RX module : CSN = D10, GDO0 = D2, GDO2 = D3   (the one already wired)
 *   TX module : CSN = D9  (SCK/MOSI/MISO shared)  (your second module)
 *
 * The TX module emits a continuous carrier (no GDO wiring needed). The RX
 * module prints a live RSSI reading. If the RX hears the TX, RSSI jumps from
 * ~-124 to a strong value; the gap between 433 MHz and 315 MHz shows exactly
 * how much sensitivity this 433-tuned module loses at 315.
 *
 * Serial command:
 *   "F 433.92" or "F 315.0" -> retune BOTH modules and keep carrier on
 *   "P 10" / "P -20" / "P -30" -> set TX power in dBm
 */

#include <Arduino.h>
#include <SPI.h>
#include <SmartRC_CC1101.h>

SmartRC_CC1101 rx;   // receiver (already wired)
SmartRC_CC1101 tx;   // transmitter (second module)

#define RX_CSN 10
#define TX_CSN 9

float currentMHz = 433.92;
int txPower = -20;

void tuneRx() {
  rx.setMHZ(currentMHz);
  rx.SetRx();
}

void tuneTx() {
  tx.setMHZ(currentMHz);
  tx.setPA(txPower);
  tx.SetTx();   // continuous carrier
}

void setup() {
  Serial.begin(115200);

  // --- RX module ---
  rx.setSpiPin(13, 12, 11, RX_CSN);
  rx.setGDO(2, 3);
  rx.Init();
  rx.setMHZ(currentMHz);
  rx.setModulation(0);      // 2-FSK (a plain carrier)
  rx.setDRate(9.6);
  rx.setDeviation(19.0);
  rx.setRxBW(100.0);
  rx.SetRx();

  // --- TX module ---
  tx.setSpiPin(13, 12, 11, TX_CSN);
  tx.Init();
  tx.setMHZ(currentMHz);
  tx.setModulation(0);      // 2-FSK
  tx.setDRate(9.6);
  tx.setDeviation(19.0);
  tx.setRxBW(100.0);
  tx.setPA(txPower);
  tx.SetTx();               // start the carrier

  Serial.print(rx.getCC1101() ? F("RX FOUND\n") : F("RX NOT FOUND\n"));
  Serial.print(tx.getCC1101() ? F("TX FOUND\n") : F("TX NOT FOUND\n"));
  Serial.println(F("READY"));
}

void handleCommands() {
  while (Serial.available()) {
    String cmd = Serial.readStringUntil('\n');
    cmd.trim();

    if (cmd.startsWith("F ")) {
      float f = cmd.substring(2).toFloat();
      if (f >= 200.0f && f <= 930.0f) {
        currentMHz = f;
        tuneRx();
        tuneTx();
        Serial.print(F("FREQ "));
        Serial.println(f, 3);
      }
    } else if (cmd.startsWith("P ")) {
      txPower = cmd.substring(2).toInt();
      tuneTx();
      Serial.print(F("PWR "));
      Serial.println(txPower);
    }
  }
}

void loop() {
  handleCommands();

  static unsigned long lastRssi = 0;
  if (millis() - lastRssi >= 50) {
    lastRssi = millis();
    long sum = 0;
    for (int i = 0; i < 4; i++) {
      sum += rx.getRssi();
      delay(1);
    }
    Serial.print(currentMHz, 3);
    Serial.print(F(" MHz   RSSI="));
    Serial.print((int)(sum / 4));
    Serial.println(F(" dBm"));
  }
}
