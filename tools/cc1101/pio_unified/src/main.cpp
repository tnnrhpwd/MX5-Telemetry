/*
 * CC1101 Unified Monitor + Raw Capture
 * ====================================
 * Streams RSSI lines for the live webapp AND captures raw demodulated bursts
 * for later decode, over one serial port.
 *
 * Serial output:
 *   "315.000 MHz   RSSI=-76 dBm"   -> RSSI line (webapp chart + events)
 *   "CAP <samples> <micros> <hex>" -> raw capture window (saved by webapp)
 *   "FREQ_OK 434.000" / "MOD_OK 2" -> command acknowledgements
 *
 * Serial commands (from the webapp):
 *   "FREQ 434.0" -> retune
 *   "MOD 0"      -> 2-FSK (TPMS)     "MOD 2" -> ASK/OOK (key fobs)
 *
 * The CC1101 runs in asynchronous serial mode: the raw demodulated data comes
 * out on GDO0, while the RSSI register stays valid for the live feed.
 */

#include <Arduino.h>
#include <SPI.h>
#include <SmartRC_CC1101.h>

SmartRC_CC1101 radio;
SmartRC_CC1101 tx;       // second module as a test transmitter (CSN D9)

#define CC1101_SCK   13
#define CC1101_MISO  12
#define CC1101_MOSI  11
#define CC1101_CSN   10
#define CC1101_GDO0  2
#define CC1101_GDO2  3
#define CC1101_TX_CSN 9

#define CAP_BYTES       600    // 600 bytes = 4800 samples per window
#define SAMPLE_DELAY_US 3      // ~4 us/sample -> ~250 kHz sample rate
#define PROBE_SAMPLES   2000   // raw GDO0 samples for the burst detector
#define PROBE_MIN_EDGES 6      // edges above this => a real signal

float currentMHz = 315.0;
byte currentMod = 0;      // 0 = 2-FSK, 2 = ASK/OOK (RX modulation)
bool txOn = false;
bool sweepMode = false;   // continuous sweep (spectrum view)
float sweepFreq = 310.0;
int sweepBand = 0;
const float SWEEP_BANDS[2][2] = {{310.0f, 348.0f}, {378.0f, 464.0f}};
static byte buf[CAP_BYTES];


// True when GDO0 is toggling (a signal is present) rather than sitting idle.
bool probeSignal() {
  uint8_t prev = (PIND & 0x04) ? 1 : 0;
  int edges = 0;
  for (int i = 0; i < PROBE_SAMPLES; i++) {
    uint8_t cur = (PIND & 0x04) ? 1 : 0;
    if (cur != prev) edges++;
    prev = cur;
  }
  return edges > PROBE_MIN_EDGES;
}


void captureAndDump() {
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


void applyAsyncConfig() {
  // Async serial mode: raw demodulated data out on GDO0.
  radio.setPktFormat(3);
  radio.setSyncMode(0);
  radio.setManchester(false);
  radio.setFEC(false);
  radio.setCrc(false);
  radio.setWhiteData(false);
  radio.SpiWriteReg(CC1101_IOCFG0, 0x0D);   // GDO0 = serial data output
  radio.SpiWriteReg(CC1101_IOCFG2, 0x0C);   // GDO2 = serial clock output
  radio.SetRx();
}


// Full RX configuration after a retune. setMHZ() alone leaves the chip's
// RSSI/AGC path in a bad state (reads -12 saturated) on the 300-348 band;
// re-applying the complete register set (as at boot) restores clean RSSI.
void tuneRx(float f, float bwKHz) {
  radio.setMHZ(f);
  radio.setModulation(currentMod);
  radio.setDRate(9.6);
  radio.setDeviation(19.0);
  radio.setRxBW(bwKHz);
  applyAsyncConfig();
}


// Bypass the library's WaitMiso() handshake for the TX module: while the TX
// chip is transmitting, its MISO line sits high and WaitMiso() times out,
// silently skipping the SIDLE strobe. Raw SPI always delivers the strobe.
void rawTxStrobe(byte cmd) {
  SPI.beginTransaction(SPISettings(4000000, MSBFIRST, SPI_MODE0));
  digitalWrite(CC1101_TX_CSN, LOW);
  SPI.transfer(cmd);
  digitalWrite(CC1101_TX_CSN, HIGH);
  SPI.endTransaction();
}


// Sweep 300-348 MHz and 378-464 MHz with a wide 540 kHz filter and report any
// energy above -85 dBm. Run while a fob button is held to find its frequency.
void sweepBands() {
  Serial.println(F("SWEEP_START"));
  const float bands[2][2] = {{310.0f, 348.0f}, {378.0f, 464.0f}};
  for (int b = 0; b < 2; b++) {
    for (float f = bands[b][0]; f <= bands[b][1] + 0.001f; f += 0.5f) {
      tuneRx(f, 540.0);
      delay(4);
      int r = radio.getRssi();
      if (r > -85) {
        Serial.print(F("HIT "));
        Serial.print(f, 1);
        Serial.print(' ');
        Serial.println(r);
      }
    }
  }
  tuneRx(currentMHz, 100.0);
  Serial.println(F("SWEEP_END"));
}


// One step of the continuous sweep: retune, print RSSI, advance frequency.
void sweepStep() {
  tuneRx(sweepFreq, 540.0);
  delay(2);
  int r = radio.getRssi();
  Serial.print(sweepFreq, 1);
  Serial.print(F(" MHz   RSSI="));
  Serial.print(r);
  Serial.println(F(" dBm"));

  sweepFreq += 0.5f;
  if (sweepFreq > SWEEP_BANDS[sweepBand][1]) {
    if (sweepBand == 0) { sweepBand = 1; sweepFreq = SWEEP_BANDS[1][0]; }
    else { sweepBand = 0; sweepFreq = SWEEP_BANDS[0][0]; }
  }
}


void handleCommands() {
  while (Serial.available()) {
    String cmd = Serial.readStringUntil('\n');
    cmd.trim();

    if (cmd.startsWith("FREQ ")) {
      float f = cmd.substring(5).toFloat();
      if (f >= 200.0f && f <= 930.0f) {
        currentMHz = f;
        tuneRx(f, 100.0);
        Serial.print(F("FREQ_OK "));
        Serial.println(f, 3);
      }
    } else if (cmd.startsWith("MOD ")) {
      int m = cmd.substring(4).toInt();
      if (m == 0 || m == 2) {                 // 0 = 2-FSK, 2 = ASK/OOK
        currentMod = m;
        radio.setModulation(m);
        applyAsyncConfig();
        Serial.print(F("MOD_OK "));
        Serial.println(m);
      }
    } else if (cmd == "TXON") {
      tx.Init();
      tx.setMHZ(currentMHz);
      tx.setModulation(0);
      tx.setPA(10);
      rawTxStrobe(CC1101_SIDLE);
      rawTxStrobe(CC1101_STX);
      txOn = true;
      Serial.println(F("TX_ON"));
    } else if (cmd == "TXOFF") {
      rawTxStrobe(CC1101_SIDLE);
      rawTxStrobe(CC1101_SFTX);
      rawTxStrobe(CC1101_SRES);   // full software reset — guaranteed off
      txOn = false;
      Serial.println(F("TX_OFF"));
    } else if (cmd == "SWEEP") {
      sweepBands();
    } else if (cmd == "SWEEPON") {
      sweepMode = true;
      sweepFreq = 310.0;
      sweepBand = 0;
      Serial.println(F("SWEEP_ON"));
    } else if (cmd == "SWEEPOFF") {
      sweepMode = false;
      tuneRx(currentMHz, 100.0);
      Serial.println(F("SWEEP_OFF"));
    }
  }
}


void setup() {
  Serial.begin(115200);

  radio.setSpiPin(CC1101_SCK, CC1101_MISO, CC1101_MOSI, CC1101_CSN);
  radio.setGDO(CC1101_GDO0, CC1101_GDO2);
  radio.Init();

  tuneRx(currentMHz, 100.0);

  // Second module as a test transmitter (off by default).
  tx.setSpiPin(CC1101_SCK, CC1101_MISO, CC1101_MOSI, CC1101_TX_CSN);
  tx.Init();
  tx.setMHZ(currentMHz);
  tx.setModulation(0);
  tx.setPA(10);
  tx.setSidle();

  Serial.print(radio.getCC1101() ? F("CC1101 FOUND\n") : F("CC1101 NOT FOUND\n"));
  Serial.print(tx.getCC1101() ? F("TX FOUND\n") : F("TX NOT FOUND\n"));
  Serial.println(F("READY"));
}


void loop() {
  handleCommands();

  if (sweepMode) {
    sweepStep();
    return;
  }

  // Live RSSI line every ~50 ms (4-read average for a steadier chart).
  static unsigned long lastRssi = 0;
  if (millis() - lastRssi >= 50) {
    lastRssi = millis();
    long sum = 0;
    for (int i = 0; i < 4; i++) {
      sum += radio.getRssi();
      delay(1);
    }
    int rssi = (int)(sum / 4);
    Serial.print(currentMHz, 3);
    Serial.print(F(" MHz   RSSI="));
    Serial.print(rssi);
    Serial.println(F(" dBm"));
  }

  // Raw burst capture, triggered by GDO0 activity.
  if (probeSignal()) {
    captureAndDump();
  }
}
