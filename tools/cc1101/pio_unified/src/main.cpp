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
#define SAMPLE_DELAY_US 45     // ~48 us/sample -> ~21 kHz. At a 2 kbps fob
                               // rate (~480 us/bit) that's ~10 samples/bit and
                               // a ~230 ms window — enough for a full frame.
#define PROBE_SAMPLES   2000   // raw GDO0 samples for the burst detector
#define PROBE_MIN_EDGES 6      // edges above this => a real signal

float currentMHz = 315.0;
byte currentMod = 2;      // 0 = 2-FSK, 2 = ASK/OOK. The library's Init()
                          // already defaults to OOK (modulation=2) + async
                          // serial mode; the fobs are OOK, so stay on 2.
bool txOn = false;
static byte buf[CAP_BYTES];

// Continuous non-blocking sweep state. The sweep steps through the bands and
// measures the GDO0 edge rate (a signal-strength proxy) instead of RSSI,
// because the RSSI register read is unreliable on this two-module bus.
bool sweepActive = false;
float sweepFreq = 300.0;
byte sweepStage = 0;
int sweepEdges = 0;
uint8_t sweepPrev = 0;
unsigned long sweepStepStart = 0;

void configRadioOok(float mhz);   // forward decl (defined below rawWriteReg)
void applyAsyncConfig();
void rawRxStrobe(byte cmd);
void rawWriteBurst(byte addr, const byte* buf, byte n);
byte rawReadStatus(byte addr);
byte rawReadReg(byte addr);
int rawGetRssi();


// True when GDO0 is toggling (a signal is present) rather than sitting idle.
// The window must span several bit periods: at 2 kbps (~480 us/bit) six edges
// take ~2.9 ms, so 2000 samples x 5 us = 10 ms catches ~20 edges reliably.
bool probeSignal() {
  uint8_t prev = (PIND & 0x04) ? 1 : 0;
  int edges = 0;
  for (int i = 0; i < PROBE_SAMPLES; i++) {
    uint8_t cur = (PIND & 0x04) ? 1 : 0;
    if (cur != prev) edges++;
    prev = cur;
    delayMicroseconds(5);
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
  // Re-assert the full OOK config raw (no WaitMiso skipping), then enter RX
  // TWICE with a settle matching the boot: the first SRX reads flat, the
  // second completes the AGC/RSSI calibration to the quiet floor.
  configRadioOok(currentMHz);
  radio.SetRx();
  delay(300);
  radio.SetRx();
  delay(300);
}


// RX configuration after a retune: full raw OOK config at the new frequency.
void tuneRx(float f, float bwKHz) {
  configRadioOok(f);
  radio.SetRx();
  delay(300);
  radio.SetRx();
  delay(300);
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


// Raw register write for the RX chip (CSN D10), bypassing the library's
// WaitMiso() handshake. WaitMiso() reads the shared MISO line, which can sit
// HIGH (the second module, or the async-serial data path) and cause the
// library's writes to be silently skipped — leaving the RX at power-on
// defaults. Raw writes always go through.
void rawWriteReg(byte addr, byte value) {
  SPI.beginTransaction(SPISettings(4000000, MSBFIRST, SPI_MODE0));
  digitalWrite(CC1101_CSN, LOW);
  SPI.transfer(addr);
  SPI.transfer(value);
  digitalWrite(CC1101_CSN, HIGH);
  SPI.endTransaction();
}


// Raw strobe to the RX chip (CSN D10).
void rawRxStrobe(byte cmd) {
  SPI.beginTransaction(SPISettings(4000000, MSBFIRST, SPI_MODE0));
  digitalWrite(CC1101_CSN, LOW);
  SPI.transfer(cmd);
  digitalWrite(CC1101_CSN, HIGH);
  SPI.endTransaction();
}


// Raw status-register read from the RX chip (CSN D10), no WaitMiso gate.
// Status registers use the burst-access bit (0xC0) on the address.
byte rawReadStatus(byte addr) {
  SPI.beginTransaction(SPISettings(4000000, MSBFIRST, SPI_MODE0));
  digitalWrite(CC1101_CSN, LOW);
  SPI.transfer(addr | 0xC0);
  byte value = SPI.transfer(0);
  digitalWrite(CC1101_CSN, HIGH);
  SPI.endTransaction();
  return value;
}


// Raw config-register read from the RX chip (single-access bit 0x80).
byte rawReadReg(byte addr) {
  SPI.beginTransaction(SPISettings(4000000, MSBFIRST, SPI_MODE0));
  digitalWrite(CC1101_CSN, LOW);
  SPI.transfer(addr | 0x80);
  byte value = SPI.transfer(0);
  digitalWrite(CC1101_CSN, HIGH);
  SPI.endTransaction();
  return value;
}


// RSSI in dBm from the raw RSSI status register (0x34). Matches the library's
// conversion so the floor/peak numbers stay comparable.
int rawGetRssi() {
  int rssi = rawReadStatus(CC1101_RSSI);
  if (rssi >= 128) return (rssi - 256) / 2 - 74;
  return (rssi / 2) - 74;
}


// Raw burst write to the RX chip.
void rawWriteBurst(byte addr, const byte* buf, byte n) {
  SPI.beginTransaction(SPISettings(4000000, MSBFIRST, SPI_MODE0));
  digitalWrite(CC1101_CSN, LOW);
  SPI.transfer(addr | 0x40);   // burst write
  for (byte i = 0; i < n; i++) SPI.transfer(buf[i]);
  digitalWrite(CC1101_CSN, HIGH);
  SPI.endTransaction();
}


// Bit-bang one OOK frame: carrier on (STX) for 1 bits, off (SIDLE) for 0 bits.
// bit_us is the on/off dwell per bit; reps repeats the frame with a small gap,
// like a real held fob.
void txFrame(const byte* frame, byte nbytes, int bit_us, int reps) {
  for (int rep = 0; rep < reps; rep++) {
    for (int b = 0; b < nbytes; b++) {
      for (int bit = 7; bit >= 0; bit--) {
        if ((frame[b] >> bit) & 1) rawTxStrobe(CC1101_STX);
        else rawTxStrobe(CC1101_SIDLE);
        delayMicroseconds(bit_us);
      }
    }
    rawTxStrobe(CC1101_SIDLE);
    delayMicroseconds(4000);      // inter-frame gap
  }
  // Guarantee the carrier is fully off after the burst.
  rawTxStrobe(CC1101_SIDLE);
  rawTxStrobe(CC1101_SFTX);
  rawTxStrobe(CC1101_SRES);
  txOn = false;
}


// Transmit an OOK burst that mimics a 315 MHz key fob. STX = carrier on
// (mark), SIDLE = carrier off (space). 2 kbps, 12 reps ~740 ms total.
void txFobBurst() {
  tx.Init();
  tx.setMHZ(currentMHz);
  tx.setModulation(2);   // ASK/OOK
  tx.setPA(10);

  const int BIT_US = 480;          // ~2.1 kbps
  // Preamble (alternating) + a sync word + data, 16 bytes total.
  const byte frame[16] = {
    0xAA, 0xAA, 0xAA, 0xAA, 0xAA, 0xAA, 0xAA, 0xAA,   // preamble
    0x2D, 0xD4,                                        // sync word
    0x01, 0x02, 0x04, 0x08, 0x10, 0x20                // data
  };
  txFrame(frame, 16, BIT_US, 12);

  // Report the transmitted frame so the webapp can label the burst it is
  // about to receive (the TX's own burst can't be captured: txFobBurst()
  // blocks loop() while transmitting, so the GDO0 probe only ever sees it
  // after it has finished).
  Serial.print(F("TXCODE AAAAAAAAAAAAAAAA2DD4010204081020\n"));
  Serial.println(F("FOBBURST_DONE"));
}


// Transmit an arbitrary OOK frame from a hex string, at a given bit period.
// Command: "TXHEX <bit_us> <hex>". Lets the TX replay a captured real fob code
// so the Fob Burst button can act identically to the real key.
void txHexFrame(const char* hex, int bit_us) {
  byte frame[32];
  byte n = 0;
  int hi = -1;
  for (const char* p = hex; *p && n < 32; p++) {
    char c = *p;
    int v = -1;
    if (c >= '0' && c <= '9') v = c - '0';
    else if (c >= 'a' && c <= 'f') v = c - 'a' + 10;
    else if (c >= 'A' && c <= 'F') v = c - 'A' + 10;
    if (v < 0) continue;
    if (hi < 0) { hi = v; }
    else { frame[n++] = (hi << 4) | v; hi = -1; }
  }
  if (n == 0) { Serial.println(F("TXHEX_EMPTY")); return; }

  tx.Init();
  tx.setMHZ(currentMHz);
  tx.setModulation(2);
  tx.setPA(10);
  txFrame(frame, n, bit_us > 0 ? bit_us : 480, 12);

  // Echo the code (canonical hex) for the webapp to label.
  Serial.print(F("TXCODE "));
  for (byte i = 0; i < n; i++) {
    if (frame[i] < 0x10) Serial.print('0');
    Serial.print(frame[i], HEX);
  }
  Serial.println();
  Serial.println(F("FOBBURST_DONE"));
}


// Loopback self-test: transmit a fob frame over the air while SIMULTANEOUSLY
// sampling the RX's GDO0 output. This exercises the whole chain (TX -> air ->
// RX -> demod -> capture) without needing a real fob, and emits a normal CAP
// line so the webapp decodes it like any other capture.
void txLoopback() {
  tx.Init();
  tx.setMHZ(currentMHz);
  tx.setModulation(2);
  tx.setPA(10);

  const byte frame[16] = {
    0xAA, 0xAA, 0xAA, 0xAA, 0xAA, 0xAA, 0xAA, 0xAA,
    0x2D, 0xD4, 0x01, 0x02, 0x04, 0x08, 0x10, 0x20
  };

  unsigned long t0 = micros();
  int n = 0;
  byte acc = 0;
  byte accBits = 0;
  for (int rep = 0; rep < 3 && n < CAP_BYTES; rep++) {
    for (int b = 0; b < 16 && n < CAP_BYTES; b++) {
      for (int bit = 7; bit >= 0 && n < CAP_BYTES; bit--) {
        if ((frame[b] >> bit) & 1) rawTxStrobe(CC1101_STX);
        else rawTxStrobe(CC1101_SIDLE);
        // Sample GDO0 once every ~45 us through this ~480 us bit (~10 samples).
        for (int s = 0; s < 10 && n < CAP_BYTES; s++) {
          acc = (acc << 1) | ((PIND & 0x04) ? 1 : 0);
          if (++accBits == 8) {
            buf[n++] = acc;
            acc = 0;
            accBits = 0;
          }
          delayMicroseconds(SAMPLE_DELAY_US);
        }
      }
    }
  }
  unsigned long us = micros() - t0;

  rawTxStrobe(CC1101_SIDLE);
  rawTxStrobe(CC1101_SFTX);
  rawTxStrobe(CC1101_SRES);
  txOn = false;

  Serial.print(F("CAP "));
  Serial.print(n * 8);
  Serial.print(' ');
  Serial.print(us);
  Serial.print(' ');
  for (int i = 0; i < n; i++) {
    if (buf[i] < 0x10) Serial.print('0');
    Serial.print(buf[i], HEX);
  }
  Serial.println();
}


// Full explicit OOK RX config for 315 MHz (TI SmartRF values). Written raw
// because the library's WaitMiso()-gated writes skip on this setup. This is
// the config that reads a live 315 MHz OOK noise floor.
void configRadioOok(float mhz) {
  // Enter IDLE before touching the FREQ registers. The CC1101 only runs its
  // frequency/AGC calibration (FS_AUTOCAL, MCSM0=0x18) on an IDLE->RX
  // transition, so retuning while still in RX leaves the VCO on the old
  // frequency and the receiver goes deaf (AGC rails to -12). SIDLE first,
  // write registers, then the caller's SRX re-enters RX and recalibrates.
  rawRxStrobe(CC1101_SIDLE);
  delayMicroseconds(100);

  uint32_t f = (uint32_t)(mhz * 65536.0f / 26.0f);
  rawWriteReg(CC1101_FREQ2, (f >> 16) & 0xFF);
  rawWriteReg(CC1101_FREQ1, (f >> 8) & 0xFF);
  rawWriteReg(CC1101_FREQ0, f & 0xFF);

  // IF frequency + VCO calibration, frequency-dependent (matches the library's
  // Calibrate()). The 315 MHz band needs FSCTRL0 ~24-28 and TEST0=0x0B below
  // 322.88 MHz to enable VCO selection calibration.
  byte fst = 0x0F;
  byte tst = 0x09;
  if (mhz >= 300.0f && mhz <= 348.0f) {
    fst = (byte)map(mhz, 300, 348, 24, 28);
    tst = (mhz < 322.88f) ? 0x0B : 0x09;
  } else if (mhz >= 378.0f && mhz <= 464.0f) {
    fst = (byte)map(mhz, 378, 464, 31, 38);
    tst = (mhz < 430.5f) ? 0x0B : 0x09;
  }
  rawWriteReg(CC1101_FSCTRL1, 0x06);
  rawWriteReg(CC1101_FSCTRL0, fst);

  // ASK/OOK, no manchester, no sync
  rawWriteReg(CC1101_MDMCFG2, 0x30);
  rawWriteReg(CC1101_MDMCFG1, 0x22);
  rawWriteReg(CC1101_MDMCFG0, 0xF8);

  // Channel BW ~101 kHz, data rate ~4.8 kbps
  rawWriteReg(CC1101_MDMCFG4, 0xC8);
  rawWriteReg(CC1101_MDMCFG3, 0x93);
  rawWriteReg(CC1101_DEVIATN, 0x47);

  // OOK front-end (bit 0 of FREND0 = OOK LNA path)
  rawWriteReg(CC1101_FREND1, 0x56);
  rawWriteReg(CC1101_FREND0, 0x11);

  // AGC: AGC_FREEZE=1 (AGCCTRL0=0xB2) quiets the OOK slicer at idle, while
  // MAX_DVGA_GAIN=0 keeps the digital gain from railing the RSSI to a constant.
  rawWriteReg(CC1101_AGCCTRL2, 0x43);
  rawWriteReg(CC1101_AGCCTRL1, 0x00);
  rawWriteReg(CC1101_AGCCTRL0, 0xB2);

  // PATABLE[0] is the RX AGC gain reference that sets the RSSI offset. 0xC0
  // keeps the RSSI direction correct (strong signal = higher dBm) so the
  // spectrum's Y axis means something.
  const byte paTable[8] = {0xC0, 0x00, 0x00, 0x00, 0x00, 0x00, 0x00, 0x00};
  rawWriteBurst(CC1101_PATABLE, paTable, 8);

  // Async serial mode (raw demodulated data out GDO0), no packet engine
  rawWriteReg(CC1101_PKTCTRL1, 0x04);
  rawWriteReg(CC1101_PKTCTRL0, 0x32);
  rawWriteReg(CC1101_ADDR, 0x00);
  rawWriteReg(CC1101_PKTLEN, 0xFF);

  // GDO0 = serial data out, GDO2 = serial clock out
  rawWriteReg(CC1101_IOCFG0, 0x0D);
  rawWriteReg(CC1101_IOCFG2, 0x0D);

  // MCSM0: FS_AUTOCAL from IDLE, RX timeout disabled
  rawWriteReg(CC1101_MCSM0, 0x18);
  rawWriteReg(CC1101_FOCCFG, 0x16);
  rawWriteReg(CC1101_BSCFG, 0x1C);

  // Calibration values
  rawWriteReg(CC1101_FSCAL3, 0xE9);
  rawWriteReg(CC1101_FSCAL2, 0x2A);
  rawWriteReg(CC1101_FSCAL1, 0x00);
  rawWriteReg(CC1101_FSCAL0, 0x1F);
  rawWriteReg(CC1101_FSTEST, 0x59);
  rawWriteReg(CC1101_TEST2, 0x81);
  rawWriteReg(CC1101_TEST1, 0x35);
  rawWriteReg(CC1101_TEST0, tst);
}


// Continuous sweep: step through both bands, one frequency at a time, and
// report the GDO0 edge rate at each step. The edge rate spikes at a frequency
// where a transmitter is active (the OOK slicer toggles with the data) and
// stays low elsewhere, so the webapp can draw a spectrum (x = MHz, y = edges)
// and the user sees the fob's frequency light up.
void sweepStart() {
  sweepActive = true;
  sweepFreq = 300.0;
  sweepStage = 0;
  Serial.println(F("SCAN_START"));
}

void sweepStop() {
  sweepActive = false;
  applyAsyncConfig();   // return to the fixed 315 MHz monitor
  Serial.println(F("SCAN_END"));
}

// Non-blocking: called every loop() while the sweep is active. One PIND sample
// per call (4 us apart), so the loop stays responsive and a "SCAN" toggle is
// honoured within one 24 ms step. The sweep cycles 300->348 and 420->470 MHz
// continuously; the webapp records the per-step edge rate as a signal proxy.
void sweepTick() {
  if (!sweepActive) return;
  if (sweepStage == 0) {
    configRadioOok(sweepFreq);
    radio.SetRx();
    sweepEdges = 0;
    sweepPrev = (PIND & 0x04) ? 1 : 0;
    sweepStepStart = millis();
    sweepStage = 1;
  } else {
    uint8_t cur = (PIND & 0x04) ? 1 : 0;
    if (cur != sweepPrev) sweepEdges++;
    sweepPrev = cur;
    delayMicroseconds(4);
    if (millis() - sweepStepStart >= 24) {
      Serial.print(F("SCAN "));
      Serial.print(sweepFreq, 1);
      Serial.print(' ');
      Serial.println(sweepEdges);
      sweepFreq += 0.5f;
      if (sweepFreq > 348.05f && sweepFreq < 420.0f) sweepFreq = 420.0f;   // 348 band -> 420 band
      else if (sweepFreq > 470.05f) sweepFreq = 300.0f;                     // wrap back to start
      sweepStage = 0;
    }
  }
}


void handleCommands() {
  while (Serial.available()) {
    String cmd = Serial.readStringUntil('\n');
    cmd.trim();

    if (cmd.startsWith("FREQ ")) {
      float f = cmd.substring(5).toFloat();
      if (f >= 200.0f && f <= 930.0f) {
        // Skip a redundant retune to the SAME frequency: re-writing the FREQ
        // registers while already in RX at that frequency glitches the AGC /
        // RSSI path (315 OOK reads flat -138 afterwards). The webapp sends
        // "FREQ 315.000" before "MOD 2" on connect, so this skip is what
        // keeps the fob path live.
        if (fabs(f - currentMHz) >= 0.5f) {
          currentMHz = f;
          tuneRx(f, 100.0);
        }
        Serial.print(F("FREQ_OK "));
        Serial.println(f, 3);
      }
    } else if (cmd.startsWith("MOD ")) {
      int m = cmd.substring(4).toInt();
      if (m == 0 || m == 2) {                 // 0 = 2-FSK, 2 = ASK/OOK
        currentMod = m;
        applyAsyncConfig();   // raw config + double SetRx (bypasses the library)
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
    } else if (cmd == "FOBBURST") {
      txFobBurst();
    } else if (cmd == "TXLOOP") {
      txLoopback();
    } else if (cmd.startsWith("TXHEX ")) {
      // "TXHEX <bit_us> <hex>" -> replay an arbitrary captured fob frame.
      int sp = cmd.indexOf(' ', 6);
      if (sp > 0) {
        int bitUs = cmd.substring(6, sp).toInt();
        String hex = cmd.substring(sp + 1);
        hex.trim();
        txHexFrame(hex.c_str(), bitUs);
      } else {
        Serial.println(F("TXHEX_BAD"));
      }
    } else if (cmd == "DUMP") {
      Serial.print(F("PARTNUM="));   Serial.println(rawReadStatus(CC1101_PARTNUM), HEX);
      Serial.print(F("VERSION="));   Serial.println(rawReadStatus(CC1101_VERSION), HEX);
      Serial.print(F("MARCSTATE=")); Serial.println(rawReadStatus(CC1101_MARCSTATE), HEX);
      Serial.print(F("MDMCFG2="));   Serial.println(rawReadReg(CC1101_MDMCFG2), HEX);
      Serial.print(F("MDMCFG4="));   Serial.println(rawReadReg(CC1101_MDMCFG4), HEX);
      Serial.print(F("FREND0="));    Serial.println(rawReadReg(CC1101_FREND0), HEX);
      Serial.print(F("FSCTRL0="));   Serial.println(rawReadReg(CC1101_FSCTRL0), HEX);
      Serial.print(F("AGCCTRL2="));  Serial.println(rawReadReg(CC1101_AGCCTRL2), HEX);
      Serial.print(F("AGCCTRL1="));  Serial.println(rawReadReg(CC1101_AGCCTRL1), HEX);
      Serial.print(F("AGCCTRL0="));  Serial.println(rawReadReg(CC1101_AGCCTRL0), HEX);
      Serial.print(F("PKTCTRL0="));  Serial.println(rawReadReg(CC1101_PKTCTRL0), HEX);
      Serial.print(F("MCSM0="));     Serial.println(rawReadReg(CC1101_MCSM0), HEX);
      Serial.print(F("RSSI_RAW="));  Serial.println(rawReadStatus(CC1101_RSSI), HEX);
      Serial.println(F("DUMP_END"));
    } else if (cmd == "TXOFF") {
      rawTxStrobe(CC1101_SIDLE);
      rawTxStrobe(CC1101_SFTX);
      rawTxStrobe(CC1101_SRES);   // full software reset — guaranteed off
      txOn = false;
      Serial.println(F("TX_OFF"));
    } else if (cmd == "SCAN") {
      // Toggle the continuous sweep: on -> off, off -> on.
      if (sweepActive) sweepStop();
      else sweepStart();
    }
  }
}


void setup() {
  Serial.begin(115200);

  // CRITICAL: de-assert BOTH chip-selects before touching either chip. Two
  // CC1101s share one SPI bus (MISO/MOSI/SCK). A floating CSn lets the other
  // chip drive MISO and corrupts register writes.
  pinMode(CC1101_TX_CSN, OUTPUT);
  digitalWrite(CC1101_TX_CSN, HIGH);
  pinMode(CC1101_CSN, OUTPUT);
  digitalWrite(CC1101_CSN, HIGH);

  // Configure and power down the TX module FIRST, so its SPI activity can't
  // disturb the RX's AGC after the RX settles.
  tx.setSpiPin(CC1101_SCK, CC1101_MISO, CC1101_MOSI, CC1101_TX_CSN);
  tx.Init();
  tx.setMHZ(currentMHz);
  tx.setModulation(0);
  tx.setPA(10);
  rawTxStrobe(CC1101_SIDLE);
  rawTxStrobe(CC1101_SPWD);
  rawTxStrobe(CC1101_SRES);   // full reset — guaranteed no carrier
  delay(10);                  // let the TX finish resetting before RX config

  radio.setSpiPin(CC1101_SCK, CC1101_MISO, CC1101_MOSI, CC1101_CSN);
  radio.setGDO(CC1101_GDO0, CC1101_GDO2);
  radio.Init();          // SRES + SPI.begin; its register writes are unreliable

  // The library's Reset() gates its SRES on WaitMiso, which can skip on this
  // two-module bus. Force a raw SRES so the RX starts from a known IDLE state
  // before we write the OOK config (the first SRX from IDLE then recalibrates
  // the VCO for 315 MHz).
  rawRxStrobe(CC1101_SRES);
  delay(10);

  // The library's setGDO() leaves GDO0 as an OUTPUT (for its TX examples).
  // We READ GDO0 as the CC1101's demodulated serial-data output, so it must
  // be an input — otherwise the Arduino drives the pin against the CC1101 and
  // the burst probe/capture reads garbage.
  pinMode(CC1101_GDO0, INPUT);

  // Write the full OOK config ourselves (raw SPI, no WaitMiso skipping), then
  // enter RX twice — the first SRX after power-on reads flat, the second one
  // completes the AGC/RSSI calibration and the floor reads live.
  configRadioOok(currentMHz);
  radio.SetRx();
  delay(500);
  radio.SetRx();
  delay(1000);  // long settle so the AGC reaches its quiet floor, not -12

  // Diagnostic: count GDO0 edges over 100 ms. A correctly-configured OOK
  // slicer is quiet at idle (near 0 edges); a railed or misconfigured one
  // toggles constantly (hundreds of edges) and floods the burst probe.
  {
    int edges = 0;
    uint8_t prev = (PIND & 0x04) ? 1 : 0;
    for (int i = 0; i < 20000; i++) {
      uint8_t cur = (PIND & 0x04) ? 1 : 0;
      if (cur != prev) edges++;
      prev = cur;
      delayMicroseconds(5);
    }
    Serial.print(F("GDO_EDGES "));
    Serial.println(edges);
  }

  Serial.print(radio.getCC1101() ? F("CC1101 FOUND\n") : F("CC1101 NOT FOUND\n"));
  Serial.print(tx.getCC1101() ? F("TX FOUND\n") : F("TX NOT FOUND\n"));
  Serial.println(F("READY"));
}


void loop() {
  handleCommands();

  // Continuous sweep mode replaces the live RSSI + capture monitor while it
  // runs, so the frequency stepping isn't disturbed by the 50 ms RSSI loop.
  if (sweepActive) {
    sweepTick();
    return;
  }

  // Live level line every ~50 ms. The RSSI register read is unreliable on this
  // two-module bus, so measure the GDO0 edge rate over a short window and map
  // it to a dBm-like scale (same one the sweep uses): a quiet channel reads
  // ~-107 dBm, and a fob burst spikes it upward.
  static unsigned long lastRssi = 0;
  if (millis() - lastRssi >= 50) {
    lastRssi = millis();
    int edges = 0;
    uint8_t prev = (PIND & 0x04) ? 1 : 0;
    unsigned long t0 = millis();
    while (millis() - t0 < 24) {
      uint8_t cur = (PIND & 0x04) ? 1 : 0;
      if (cur != prev) edges++;
      prev = cur;
      delayMicroseconds(4);
    }
    int rssi = -110 + (80 * (edges > 250 ? 250 : edges)) / 250;
    Serial.print(currentMHz, 3);
    Serial.print(F(" MHz   RSSI="));
    Serial.print(rssi);
    Serial.println(F(" dBm"));
  }

  // Raw burst capture, triggered by GDO0 activity. Debounced just enough to
  // let the ~105 ms serial dump drain: at 115200 baud a 600-byte CAP line
  // takes ~105 ms, so a 350 ms debounce gives ~3 captures/sec — frequent
  // enough that a ~300 ms fob press lands inside a capture window. The decode
  // quality gate on the webapp separates the fob's clean burst from the idle
  // slicer noise that surrounds it.
  static unsigned long lastCap = 0;
  if (probeSignal() && millis() - lastCap > 350) {
    lastCap = millis();
    captureAndDump();
  }
}
