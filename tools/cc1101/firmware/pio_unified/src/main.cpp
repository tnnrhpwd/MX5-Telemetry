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
 *   "DRATE 10000" -> RX data rate in bits/s (must match the target signal)
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
#define SAMPLE_DELAY_US 10     // ~11 us/sample -> a ~48 ms window. This fob is
                               // ~10 kbps, so a bit is ~100 us: at 10 us/sample
                               // that is ~10 samples/bit, which is decodable.
                               // The earlier 45 us/sample gave only ~2 samples
                               // per bit, so no fob frame could ever decode.
#define PROBE_SAMPLES   500    // raw GDO0 samples for the burst detector
#define PROBE_MIN_EDGES 6      // edges above this => a real signal

float currentMHz = 315.0;
byte currentMod = 2;      // 0 = 2-FSK, 2 = ASK/OOK. The library's Init()
                          // already defaults to OOK (modulation=2) + async
                          // serial mode; the fobs are OOK, so stay on 2.
// RX data rate in bits/s. 10 kbps is what this 315 MHz OOK fob transmits at:
// it is why the fob used to put ~120 GDO0 edges into a 24 ms window (~-72 dBm
// on the edge-rate proxy) while a 2 kbps setting left it at ~-102 dBm, i.e.
// almost invisible. The live level is an EDGE RATE, so it scales with this
// value — the RX rate must match the signal being hunted.
uint32_t currentDRate = 10000;
bool txOn = false;
// TX output power index (0 = minimum, 10 = 10 dBm, 12 = max). The loopback
// calibration needs this: two modules on one desk saturate the RX at full
// power, which rails the slicer high and makes the fidelity test meaningless.
byte txPa = 10;
// TX PKTCTRL0. 0x32 is ASYNC SERIAL, which is right for the RX (it outputs
// demodulated data) but wrong for the TX: in async TX mode the CC1101 keys the
// carrier from the GDO0 INPUT pin, and the TX module's GDO0 is not wired to
// anything - so strobing STX starts a transmit whose PA follows an unconnected
// pin and nothing is radiated. That would explain why the SPI-free test shows
// no difference between carrier on and carrier off. Switchable so the
// alternative can be tested without a reflash.
byte txPktCtrl = 0x32;
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

void configRadio(float mhz);   // forward decl (defined below rawWriteReg)
void configureTx(float mhz);
void applyAsyncConfig();
void rawRxStrobe(byte cmd);
void rawEnterRx();
void rawWriteBurst(byte addr, const byte* buf, byte n);
byte rawReadStatus(byte addr);
byte rawReadReg(byte addr);
int rawGetRssi();


// True when GDO0 is toggling (a signal is present) rather than sitting idle.
// The window must span several bit periods: at 10 kbps a bit is 100 us, so six
// edges take ~0.6 ms and 500 samples x 5 us = 2.5 ms catches them with room to
// spare. This used to be 2000 samples (10 ms), which cost 10 ms on EVERY loop
// iteration and left the loop saturated with no idle time — the live level
// line could only fire every ~74 ms instead of every 50 ms, and a capture
// trigger was delayed by up to 10 ms. Shorter is strictly better here: idle
// measures ~0.2 edges per 2.5 ms against a threshold of 6.
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


void captureAndDump(uint8_t delayUs) {
  unsigned long t0 = micros();
  for (int i = 0; i < CAP_BYTES; i++) {
    byte b = 0;
    for (int k = 0; k < 8; k++) {
      b <<= 1;
      if (PIND & 0x04) b |= 1;   // GDO0 on D2 = PD2
      if (delayUs) delayMicroseconds(delayUs);
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
  // Re-assert the full config raw, then enter RX with raw strobes. This never
  // uses the library's WaitMiso-gated SetRx(), which can silently skip SRX.
  configRadio(currentMHz);
  rawEnterRx();
}


// RX configuration after a retune: full raw config at the new frequency.
void tuneRx(float f, float bwKHz) {
  configRadio(f);
  rawEnterRx();
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


// Raw register access for the TX chip (CSN D9), for the same reason the RX ones
// exist: the library gates its SPI on WaitMiso(), which READS the contended
// shared MISO line, so its writes can be silently skipped and the chip left at
// power-on defaults - i.e. radiating nothing.
void rawTxWriteReg(byte addr, byte value) {
  SPI.beginTransaction(SPISettings(4000000, MSBFIRST, SPI_MODE0));
  digitalWrite(CC1101_TX_CSN, LOW);
  SPI.transfer(addr);
  SPI.transfer(value);
  digitalWrite(CC1101_TX_CSN, HIGH);
  SPI.endTransaction();
}


void rawTxWriteBurst(byte addr, const byte* buf, byte n) {
  SPI.beginTransaction(SPISettings(4000000, MSBFIRST, SPI_MODE0));
  digitalWrite(CC1101_TX_CSN, LOW);
  SPI.transfer(addr | 0x40);
  for (byte i = 0; i < n; i++) SPI.transfer(buf[i]);
  digitalWrite(CC1101_TX_CSN, HIGH);
  SPI.endTransaction();
}


byte rawTxReadStatus(byte addr) {
  SPI.beginTransaction(SPISettings(4000000, MSBFIRST, SPI_MODE0));
  digitalWrite(CC1101_TX_CSN, LOW);
  SPI.transfer(addr | 0xC0);
  byte v = SPI.transfer(0);
  digitalWrite(CC1101_TX_CSN, HIGH);
  SPI.endTransaction();
  return v;
}


byte rawTxReadReg(byte addr) {
  SPI.beginTransaction(SPISettings(4000000, MSBFIRST, SPI_MODE0));
  digitalWrite(CC1101_TX_CSN, LOW);
  SPI.transfer(addr | 0x80);
  byte v = SPI.transfer(0);
  digitalWrite(CC1101_TX_CSN, HIGH);
  SPI.endTransaction();
  return v;
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


// Enter RX reliably, with raw strobes only - never the library's SetRx().
// SetRx() gates its SRX on WaitMiso(), which READS the shared MISO line; on
// this two-module bus that read is unreliable, so the strobe can be silently
// skipped and the chip left out of RX. That is a BISTABLE failure - the
// receiver either tracks a signal or sits at a constant output level - and it
// matches the bench exactly: a "live" state (idle output chatters, ~80 % of a
// keyed carrier followed) alternating with a "stuck" state (idle quiet, ~13 %
// followed, captures railing to all-ones). Entering twice with a settle is kept
// because the AGC needs the extra transition, but both now go out raw.
void rawEnterRx() {
  rawRxStrobe(CC1101_SRX);
  delay(300);
  rawRxStrobe(CC1101_SRX);
  delay(300);
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
  configureTx(currentMHz);

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

  configureTx(currentMHz);
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
//
// spb = captured samples per transmitted bit. Each sample costs ~11 us, so the
// TX bit period is spb * ~11 us. This is the knob that matters: txFrame keys the
// carrier by strobing STX/SIDLE, and the CC1101 PLL needs ~100-200 us to settle
// between those states. At spb=10 (~110 us/bit) the carrier never changes state,
// so the chip radiates a CONTINUOUS carrier - measured as a 98%-high capture
// with no payload present, at every TX power level from 0 to 12. Sweeping spb
// finds the fastest bit rate that actually keys the carrier.
void txLoopback(int spb) {
  // Baseline capture FIRST, before the TX is touched at all. If this is also a
  // rail, then the rail is the RX's own state (AGC / slicer) and has nothing to
  // do with the transmission - which is what the power and bit-rate sweeps
  // implied but could not prove. LB_BASE / LB_TX bracketing lets the host tell
  // the two captures apart.
  Serial.println(F("LB_BASE"));
  captureAndDump(SAMPLE_DELAY_US);
  Serial.println(F("LB_TX"));

  configureTx(currentMHz);

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
        for (int s = 0; s < spb && n < CAP_BYTES; s++) {
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


// Keyed-carrier test: strobe a square-wave carrier for `ms` while counting the
// RX's GDO0 edges. This is the TX-side calibration, and it uses EDGES rather
// than levels on purpose: with no signal the OOK demod output sits at a single
// level (a "rail"), so a carrier and silence are indistinguishable by level.
// A carrier that actually reaches the receiver MUST make the output toggle.
//
// doTx=0 runs the identical timing loop with no strobes at all, giving the
// silent control measured in the same instant - without it a low edge count
// cannot be attributed to the TX rather than to a desensitised RX.
//
// doTx=2 is the sharper control: the SAME init and the SAME number of SPI
// strobes at the SAME instants, but 0x3D (SNOP) is a no-operation strobe so the
// carrier never changes. doTx=1 vs doTx=2 therefore isolates real RF from plain
// SPI crosstalk onto the GDO0 line - and "the count does not depend on TX power
// at all" is exactly what crosstalk would look like.
void txKeyTest(int bit_us, int ms, int doTx) {
  if (doTx) {
    configureTx(currentMHz);
  }
  if (bit_us < 1) bit_us = 480;
  if (ms < 1) ms = 200;

  int edges = 0;
  uint8_t prev = (PIND & 0x04) ? 1 : 0;
  bool on = false;
  unsigned long t0 = millis();
  while (millis() - t0 < (unsigned long)ms) {
    if (doTx == 1) {
      on = !on;
      rawTxStrobe(on ? CC1101_STX : CC1101_SIDLE);
    } else if (doTx == 2) {
      on = !on;
      rawTxStrobe(0x3D);   // SNOP: identical SPI, carrier untouched
    }
    unsigned long b0 = micros();
    while (micros() - b0 < (unsigned long)bit_us) {
      uint8_t cur = (PIND & 0x04) ? 1 : 0;
      if (cur != prev) edges++;
      prev = cur;
    }
  }

  if (doTx) {
    rawTxStrobe(CC1101_SIDLE);
    rawTxStrobe(CC1101_SFTX);
    rawTxStrobe(CC1101_SRES);
    txOn = false;
  }

  Serial.print(F("TXKEY_EDGES "));
  Serial.print(edges);
  Serial.print(' ');
  Serial.print(bit_us);
  Serial.print(' ');
  Serial.print(ms);
  Serial.print(' ');
  Serial.println(doTx);
}


// SPI-free carrier comparison - the measurement TXKEY could not make.
//
// GDO0 picks up SPI crosstalk, and that crosstalk is LARGER than anything the
// radio has produced in these tests (keyed 88 vs spi-only 136 edges), so an
// edge COUNT cannot see RF at all: the counter measures the SPI traffic in its
// own loop. Here the carrier is set ONCE with a single strobe and the capture
// that follows injects NO SPI - captureAndDump only reads PIND. Comparing
// carrier-on against carrier-off therefore tests the RF path with nothing else
// happening in the window.
//
// The keyed phase is deliberately SLOW (milliseconds per state). A real carrier
// shows up as LONG runs - msPerState * 1000 / ~11 samples each - whereas
// crosstalk shows up as isolated edges, so the two stay distinguishable by run
// length even though this phase does inject SPI.
void rxDiff(int msPerState) {
  if (msPerState < 200) msPerState = 4000;

  // Baseline BEFORE the TX is touched at all. If this differs from DIFF_OFF,
  // then tx.Init() itself is disturbing the RX - and every TX experiment in
  // this project has been measured with whatever state that left behind.
  Serial.println(F("DIFF_PRE"));
  captureAndDump(SAMPLE_DELAY_US);

  configureTx(currentMHz);

  // Re-assert the FULL RX config AFTER the TX init. The documented rule for
  // this two-module bus is "init/SRES the TX first, then configure the RX" -
  // txKeyTest, txLoopback and the first rxDiff all did the opposite and never
  // restored the RX, so a "no RF" result may just be a receiver that tx.Init()
  // had already upset. This is the one difference from that earlier version.
  applyAsyncConfig();

  rawTxStrobe(CC1101_SIDLE);
  delay(600);
  Serial.println(F("DIFF_OFF"));
  captureAndDump(SAMPLE_DELAY_US);

  rawTxStrobe(CC1101_STX);
  delay(600);
  Serial.println(F("DIFF_ON"));
  captureAndDump(SAMPLE_DELAY_US);

  Serial.println(F("DIFF_KEY"));
  {
    unsigned long t0 = micros();
    unsigned long lastToggle = micros();
    bool on = false;
    int n = 0;
    byte acc = 0, accBits = 0;
    while (n < CAP_BYTES) {
      if (micros() - lastToggle >= (unsigned long)msPerState * 1000UL) {
        lastToggle = micros();
        on = !on;
        rawTxStrobe(on ? CC1101_STX : CC1101_SIDLE);
      }
      acc = (acc << 1) | ((PIND & 0x04) ? 1 : 0);
      if (++accBits == 8) { buf[n++] = acc; acc = 0; accBits = 0; }
      delayMicroseconds(SAMPLE_DELAY_US);
    }
    unsigned long us = micros() - t0;
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

  rawTxStrobe(CC1101_SIDLE);
  rawTxStrobe(CC1101_SFTX);
  rawTxStrobe(CC1101_SRES);
  txOn = false;
  Serial.println(F("DIFF_DONE"));
}


// Program the RX data rate from bits/s. rate = ((256 + DRATE_M) * 2^DRATE_E *
// F_OSC) / 2^28, so (256 + DRATE_M) * 2^DRATE_E = bps * 2^28 / F_OSC. The
// channel-bandwidth bits (MDMCFG4 high nibble) stay at 0xC0 (~101 kHz), which
// suits any rate in this range.
static void writeDRate(uint32_t bps) {
  if (bps < 600) bps = 600;
  if (bps > 500000) bps = 500000;
  uint32_t target = (uint32_t)(((uint64_t)bps << 28) / 26000000ULL);
  int e = 0;
  while (e < 15 && (target >> (e + 1)) >= 256) e++;
  uint32_t m = (target + (1UL << e) / 2) >> e;   // round to nearest
  if (m < 256) m = 256;
  if (m > 511) m = 511;
  rawWriteReg(CC1101_MDMCFG4, (byte)(0xC0 | (e & 0x0F)));
  rawWriteReg(CC1101_MDMCFG3, (byte)(m - 256));
}


// Full explicit RX config for 315 MHz (TI SmartRF values), for whichever
// modulation currentMod selects. Written raw because the library's
// WaitMiso()-gated writes skip on this two-module setup.
void configRadio(float mhz) {
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

  // Modulation. MDMCFG2[6:4]: 000 = 2-FSK, 011 = ASK/OOK; no manchester and no
  // sync either way. FREND0 bit 0 selects the OOK PA/LNA path.
  // This block used to be hardcoded to OOK, so "MOD 0" (FSK) from the webapp
  // only set currentMod and left the radio configured as OOK — the FSK button
  // did nothing, which made an FSK/ASK comparison impossible.
  if (currentMod == 0) {
    rawWriteReg(CC1101_MDMCFG2, 0x00);   // 2-FSK
    rawWriteReg(CC1101_FREND0, 0x10);
    rawWriteReg(CC1101_DEVIATN, 0x43);   // ~35 kHz deviation
  } else {
    rawWriteReg(CC1101_MDMCFG2, 0x30);   // ASK/OOK
    rawWriteReg(CC1101_FREND0, 0x11);    // OOK PA/LNA path
    rawWriteReg(CC1101_DEVIATN, 0x47);   // unused when OOK
  }
  rawWriteReg(CC1101_MDMCFG1, 0x22);
  rawWriteReg(CC1101_MDMCFG0, 0xF8);

  // Channel BW ~101 kHz (MDMCFG4 high nibble 0xC0) at the current data rate.
  writeDRate(currentDRate);

  rawWriteReg(CC1101_FREND1, 0x56);

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


// Full explicit TX config, RAW SPI - the same register set configRadio() uses,
// including the 315 MHz special-casing, but addressed to the TX chip (CSN D9).
//
// The TX was the last radio still driven by the library (tx.Init + setMHZ +
// setModulation + setPA), and the library gates its writes on WaitMiso(). If
// those writes are skipped the TX chip stays at power-on defaults and radiates
// nothing - which is exactly what the SPI-free RXDIFF test measured: the RX
// output is bit-for-bit unchanged whether the carrier is keyed on or off, at
// both 315 and 433.92 MHz, while a real fob a metre away is demodulated fine.
void configureTx(float mhz) {
  rawTxStrobe(CC1101_SRES);
  delay(10);

  uint32_t f = (uint32_t)(mhz * 65536.0f / 26.0f);
  rawTxWriteReg(CC1101_FREQ2, (f >> 16) & 0xFF);
  rawTxWriteReg(CC1101_FREQ1, (f >> 8) & 0xFF);
  rawTxWriteReg(CC1101_FREQ0, f & 0xFF);

  // Same frequency-dependent IF/VCO handling the RX needs: 315 MHz requires
  // FSCTRL0 ~24-28 and TEST0=0x0B below 322.88 MHz for VCO selection.
  byte fst = 0x0F;
  byte tst = 0x09;
  if (mhz >= 300.0f && mhz <= 348.0f) {
    fst = (byte)map(mhz, 300, 348, 24, 28);
    tst = (mhz < 322.88f) ? 0x0B : 0x09;
  } else if (mhz >= 378.0f && mhz <= 464.0f) {
    fst = (byte)map(mhz, 378, 464, 31, 38);
    tst = (mhz < 430.5f) ? 0x0B : 0x09;
  }
  rawTxWriteReg(CC1101_FSCTRL1, 0x06);
  rawTxWriteReg(CC1101_FSCTRL0, fst);

  rawTxWriteReg(CC1101_MDMCFG4, 0xC8);   // BW ~101 kHz, DRATE_E=8
  rawTxWriteReg(CC1101_MDMCFG3, 0x93);   // -> ~10 kbps, matching the fob
  rawTxWriteReg(CC1101_MDMCFG2, 0x30);   // ASK/OOK, no sync, no manchester
  rawTxWriteReg(CC1101_MDMCFG1, 0x22);
  rawTxWriteReg(CC1101_MDMCFG0, 0xF8);
  rawTxWriteReg(CC1101_DEVIATN, 0x47);
  rawTxWriteReg(CC1101_FREND1, 0x56);
  rawTxWriteReg(CC1101_FREND0, 0x11);    // OOK PA/LNA path

  rawTxWriteReg(CC1101_PKTCTRL1, 0x04);
  rawTxWriteReg(CC1101_PKTCTRL0, txPktCtrl);   // see the note on txPktCtrl
  rawTxWriteReg(CC1101_ADDR, 0x00);
  rawTxWriteReg(CC1101_PKTLEN, 0xFF);
  rawTxWriteReg(CC1101_IOCFG0, 0x0D);
  rawTxWriteReg(CC1101_IOCFG2, 0x0D);
  rawTxWriteReg(CC1101_MCSM0, 0x18);     // FS_AUTOCAL from IDLE

  rawTxWriteReg(CC1101_FOCCFG, 0x16);
  rawTxWriteReg(CC1101_BSCFG, 0x1C);
  rawTxWriteReg(CC1101_FSCAL3, 0xE9);
  rawTxWriteReg(CC1101_FSCAL2, 0x2A);
  rawTxWriteReg(CC1101_FSCAL1, 0x00);
  rawTxWriteReg(CC1101_FSCAL0, 0x1F);
  rawTxWriteReg(CC1101_FSTEST, 0x59);
  rawTxWriteReg(CC1101_TEST2, 0x81);
  rawTxWriteReg(CC1101_TEST1, 0x35);
  rawTxWriteReg(CC1101_TEST0, tst);

  // TX power table. OOK/ASK keys the carrier from PATABLE, so PATABLE[0] is the
  // on-state and PATABLE[1] the off-state. Indexed by txPa so TXPA still scales
  // it (0 = off, 9+ = ~+10 dBm). 0xC2 is full power on this table.
  const byte paIndex[16] = {0x00, 0x01, 0x03, 0x04, 0x0C, 0x18, 0x30, 0x60,
                            0xC0, 0xC2, 0xC2, 0xC2, 0xC2, 0xC2, 0xC2, 0xC2};
  const byte pa[8] = {paIndex[txPa & 0x0F], 0x00, 0x00, 0x00,
                      0x00, 0x00, 0x00, 0x00};
  rawTxWriteBurst(CC1101_PATABLE, pa, 8);
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
    configRadio(sweepFreq);
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
    } else if (cmd.startsWith("DRATE ")) {
      uint32_t bps = (uint32_t)cmd.substring(6).toInt();
      if (bps >= 600 && bps <= 500000) {
        currentDRate = bps;
        applyAsyncConfig();   // raw config + double SetRx at the new rate
        Serial.print(F("DRATE_OK "));
        Serial.println(bps);
      } else {
        Serial.println(F("DRATE_BAD"));
      }
    } else if (cmd.startsWith("TXCFG")) {
      // "TXCFG [mhz]" -> apply the full RAW TX config (defaults to currentMHz).
      float m = (cmd.length() > 6) ? cmd.substring(6).toFloat() : currentMHz;
      if (m < 300.0f || m > 500.0f) m = currentMHz;
      configureTx(m);
      Serial.print(F("TXCFG_OK "));
      Serial.println(m, 3);
    } else if (cmd == "TXSTATE") {
      // Is the STX strobe actually landing? Most reads on this bus are
      // unstable (FREQ2 read 0x0C then 0x1E for the same config), but MARCSTATE
      // has been consistent and correct - it reports IDLE (1) after a reset.
      // So TX (0x13) vs IDLE here is real evidence about whether the chip
      // transmits, which is the one thing still unknown.
      Serial.print(F("TXSTATE_CONST_STX="));  Serial.println((byte)CC1101_STX, HEX);
      Serial.print(F("TXSTATE_CONST_SIDLE=")); Serial.println((byte)CC1101_SIDLE, HEX);
      Serial.print(F("TXSTATE_CONST_SRES=")); Serial.println((byte)CC1101_SRES, HEX);
      configureTx(currentMHz);
      rawTxStrobe(CC1101_SIDLE);
      delay(20);
      Serial.print(F("TXSTATE_IDLE="));
      Serial.println(rawTxReadStatus(CC1101_MARCSTATE), HEX);
      // Literal 0x35 as well as the library constant, in case the library's
      // enum is not the raw command byte. A CC1101 emits TX (0x13).
      rawTxStrobe(0x35);
      delay(50);
      Serial.print(F("TXSTATE_LIT35="));
      Serial.println(rawTxReadStatus(CC1101_MARCSTATE), HEX);
      rawTxStrobe(CC1101_STX);
      delay(50);
      Serial.print(F("TXSTATE_STX1="));
      Serial.println(rawTxReadStatus(CC1101_MARCSTATE), HEX);
      delay(50);
      Serial.print(F("TXSTATE_STX2="));
      Serial.println(rawTxReadStatus(CC1101_MARCSTATE), HEX);
      // FS_AUTOCAL=00 is the permissive setting (calibrate on IDLE->TX); 0x18
      // has it at 10 (only on ->IDLE), which is what the library defaults to.
      rawTxWriteReg(CC1101_MCSM0, 0x08);
      rawTxStrobe(CC1101_SIDLE);
      delay(20);
      rawTxStrobe(CC1101_STX);
      delay(80);
      Serial.print(F("TXSTATE_AUTOCAL00="));
      Serial.println(rawTxReadStatus(CC1101_MARCSTATE), HEX);

      // THE DISCRIMINATOR: does ANY strobe land, or only SRES? If the chip
      // enters RX (MARCSTATE 0x0D) then the SPI wiring is fine and it is the TX
      // path specifically that fails; if nothing ever moves off IDLE then no
      // strobe is reaching the chip at all, which is a CSN/wiring fault. FSTXON
      // (0x31) is the second half: it runs the PLL without transmitting, so it
      // separates "the synthesizer works" from "the PA/TX state is blocked".
      rawTxStrobe(CC1101_SIDLE);
      delay(20);
      rawTxStrobe(0x34);                       // SRX
      delay(200);
      Serial.print(F("TXSTATE_SRX="));
      Serial.println(rawTxReadStatus(CC1101_MARCSTATE), HEX);
      rawTxStrobe(CC1101_SIDLE);
      delay(20);
      rawTxStrobe(0x31);                       // SFSTXON
      delay(200);
      Serial.print(F("TXSTATE_FSTXON="));
      Serial.println(rawTxReadStatus(CC1101_MARCSTATE), HEX);
      rawTxStrobe(CC1101_SIDLE);
      delay(20);
      rawTxStrobe(0x33);                       // SCAL
      delay(200);
      Serial.print(F("TXSTATE_SCAL="));
      Serial.println(rawTxReadStatus(CC1101_MARCSTATE), HEX);

      rawTxStrobe(CC1101_SIDLE);
      rawTxStrobe(CC1101_SFTX);
      txOn = false;
      Serial.println(F("TXSTATE_DONE"));
    } else if (cmd.startsWith("TXPKT ")) {
      // "TXPKT <hex>" -> TX PKTCTRL0 (0x32 async serial, 0x04 infinite length,
      // 0x02 random TX). Lets the carrier-keying mode be varied without a reflash.
      long v = strtol(cmd.substring(6).c_str(), NULL, 16);
      txPktCtrl = (byte)v;
      configureTx(currentMHz);
      Serial.print(F("TXPKT_OK "));
      Serial.println(txPktCtrl, HEX);
    } else if (cmd == "TXV") {
      // Does the TX chip answer on CSN D9 at all? A CC1101 reports PARTNUM=0x00
      // and VERSION=0x14. Anything else - or a constant 0x00/0xFF - means the
      // chip is not responding, and no amount of register-writing will make it
      // transmit. These are STATUS reads (burst bit) since config-register
      // reads are the ones known to come back bit-shifted on this bus.
      Serial.print(F("TX_PARTNUM="));   Serial.println(rawTxReadStatus(CC1101_PARTNUM), HEX);
      Serial.print(F("TX_VERSION="));   Serial.println(rawTxReadStatus(CC1101_VERSION), HEX);
      Serial.print(F("TX_MARCSTATE=")); Serial.println(rawTxReadStatus(CC1101_MARCSTATE), HEX);
      Serial.print(F("TX_MDMCFG2="));   Serial.println(rawTxReadReg(CC1101_MDMCFG2), HEX);
      Serial.print(F("TX_MDMCFG4="));   Serial.println(rawTxReadReg(CC1101_MDMCFG4), HEX);
      Serial.print(F("TX_FREQ2="));     Serial.println(rawTxReadReg(CC1101_FREQ2), HEX);
      Serial.print(F("TX_FREND0="));    Serial.println(rawTxReadReg(CC1101_FREND0), HEX);
    } else if (cmd == "TXON") {
      configureTx(currentMHz);
      rawTxStrobe(CC1101_SIDLE);
      rawTxStrobe(CC1101_STX);
      txOn = true;
      Serial.println(F("TX_ON"));
    } else if (cmd == "FOBBURST") {
      txFobBurst();
    } else if (cmd == "TXLOOP" || cmd.startsWith("TXLOOP ")) {
      // "TXLOOP [samples_per_bit]" -> loopback self-test. Default 10 (~110 us
      // bit, ~9 kbps); raise it to find the fastest rate that keys the carrier.
      int spb = (cmd.length() > 7) ? cmd.substring(7).toInt() : 10;
      if (spb < 1) spb = 1;
      txLoopback(spb);
    } else if (cmd.startsWith("TXPA ")) {
      // "TXPA <0-15>" -> TX output power index, for the loopback calibration.
      int pa = cmd.substring(5).toInt();
      if (pa >= 0 && pa <= 15) {
        txPa = (byte)pa;
        Serial.print(F("TXPA_OK "));
        Serial.println(pa);
      } else {
        Serial.println(F("TXPA_BAD"));
      }
    } else if (cmd.startsWith("TXKEY ")) {
      // "TXKEY <bit_us> <ms> <txon>" -> keyed-carrier edge-rate test.
      int s1 = cmd.indexOf(' ', 6);
      int s2 = (s1 > 0) ? cmd.indexOf(' ', s1 + 1) : -1;
      if (s2 > 0) {
        txKeyTest(cmd.substring(6, s1).toInt(),
                  cmd.substring(s1 + 1, s2).toInt(),
                  cmd.substring(s2 + 1).toInt());
      } else {
        Serial.println(F("TXKEY_BAD"));
      }
    } else if (cmd == "RXDIFF" || cmd.startsWith("RXDIFF ")) {
      // "RXDIFF [ms_per_state]" -> SPI-free carrier-on/off comparison plus a
      // slow-keyed capture. See rxDiff() for why the window must be SPI-free.
      int mps = (cmd.length() > 7) ? cmd.substring(7).toInt() : 4000;
      rxDiff(mps);
    } else if (cmd.startsWith("RXREG ")) {
      // "RXREG <addr_hex> <val_hex>" -> apply the full config, then override ONE
      // register and re-enter RX. Sweeps an AGC/threshold register against a
      // measurable objective without a reflash. NOTE: the override must be last,
      // because configRadio() rewrites every register and would undo it.
      int sp = cmd.indexOf(' ', 6);
      if (sp > 0) {
        long a = strtol(cmd.substring(6, sp).c_str(), NULL, 16);
        long v = strtol(cmd.substring(sp + 1).c_str(), NULL, 16);
        configRadio(currentMHz);
        rawWriteReg((byte)a, (byte)v);
        rawEnterRx();
        Serial.print(F("RXREG_OK "));
        Serial.print(a, HEX);
        Serial.print(' ');
        Serial.println(v, HEX);
      } else {
        Serial.println(F("RXREG_BAD"));
      }
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
    } else if (cmd == "FASTCAP") {
      // Diagnostic: capture with NO inter-sample delay (tight loop, ~1-2 MHz)
      // so the true GDO0 waveform is visible instead of an alias of it.
      captureAndDump(0);
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

  // Write the full RX config ourselves (raw SPI, no WaitMiso skipping), then
  // enter RX twice — the first SRX after power-on reads flat, the second one
  // completes the AGC/RSSI calibration and the floor reads live.
  configRadio(currentMHz);
  rawEnterRx();
  delay(800);   // extra settle so the AGC reaches a stable floor, not -12

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

  // Raw burst capture, triggered by GDO0 activity. One capture costs ~50 ms of
  // sampling plus a ~105 ms blocking serial dump, so the loop is already busy
  // ~155 ms per capture and the debounce only has to stop the next capture
  // starting in the same instant. 350 ms was needlessly conservative: it capped
  // a press at ~3 captures, and telling a complete frame from a fragment needs
  // far more windows than that. 60 ms gives ~5 captures/sec, so a 1 s press now
  // yields several windows instead of three. The serial link runs at ~50%
  // utilisation at this rate, which the blocking Serial.print self-limits.
  static unsigned long lastCap = 0;
  if (probeSignal() && millis() - lastCap > 60) {
    lastCap = millis();
    captureAndDump(SAMPLE_DELAY_US);
  }
}
