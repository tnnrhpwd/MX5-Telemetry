// Rainbow LED Strip - Arduino Nano
// 20x WS2812B LED Strip - Continuous Rainbow Flow
// ================================================

#include <Arduino.h>
#include <Adafruit_NeoPixel.h>

// Configuration
#define LED_PIN     6       // Data pin connected to LED strip
#define LED_COUNT   20      // Number of LEDs in strip
#define BRIGHTNESS  150     // 0-255, adjust as needed

// Create NeoPixel object
Adafruit_NeoPixel strip(LED_COUNT, LED_PIN, NEO_GRB + NEO_KHZ800);

// Rainbow position counter
uint16_t rainbowHue = 0;

// Function prototype
void rainbowCycle();

void setup() {
  strip.begin();
  strip.setBrightness(BRIGHTNESS);
  strip.show(); // Initialize all pixels to off
}

void loop() {
  // Rainbow cycle - flows continuously through the strip
  rainbowCycle();
  delay(10); // Speed control - lower = faster
}

// Creates a flowing rainbow that moves along the strip
void rainbowCycle() {
  for (int i = 0; i < LED_COUNT; i++) {
    // Calculate hue for each pixel, offset by position for flowing effect
    // 65536 is the full color wheel in NeoPixel library
    uint16_t pixelHue = rainbowHue + (i * 65536L / LED_COUNT);
    strip.setPixelColor(i, strip.gamma32(strip.ColorHSV(pixelHue)));
  }
  strip.show();
  
  // Move the rainbow along
  rainbowHue += 256; // Increment for smooth flow
}
