#include "Touch_CST816.h"

struct CST816_Touch touch_data = {0};
uint8_t Touch_interrupts = 0;  // Match demo: not volatile

// I2C functions matching the demo exactly
static bool I2C_Read_Touch(uint16_t Driver_addr, uint8_t Reg_addr, uint8_t *Reg_data, uint32_t Length)
{
  Wire.beginTransmission((uint8_t)Driver_addr);
  Wire.write(Reg_addr); 
  if (Wire.endTransmission(true)) {
    Serial.println("Touch I2C: endTransmission failed");
    return false;
  }
  Wire.requestFrom((uint8_t)Driver_addr, (uint8_t)Length);
  for (uint32_t i = 0; i < Length; i++) {
    *Reg_data++ = Wire.read();
  }
  return true;  // Demo always returns true
}

static bool I2C_Write_Touch(uint8_t Driver_addr, uint8_t Reg_addr, const uint8_t *Reg_data, uint32_t Length)
{
  Wire.beginTransmission(Driver_addr);
  Wire.write(Reg_addr);       
  for (uint32_t i = 0; i < Length; i++) {
    Wire.write(*Reg_data++);
  }
  if (Wire.endTransmission(true)) {
    Serial.println("Touch I2C: Write endTransmission failed");
    return false;
  }
  return true;
}

// Match demo: use ARDUINO_ISR_ATTR
void ARDUINO_ISR_ATTR Touch_CST816_ISR(void) {
  Touch_interrupts = true;
}

uint8_t Touch_Init(void) {
  Serial.println("Touch_Init: Starting...");
  
  // Reset and configure touch controller
  Serial.println("Touch_Init: Resetting touch controller...");
  CST816_Touch_Reset();
  
  // Try to read chip ID to verify communication
  Serial.println("Touch_Init: Attempting to read chip info...");
  uint16_t Verification = CST816_Read_cfg();
  
  CST816_AutoSleep(true);
   
  pinMode(CST816_INT_PIN, INPUT_PULLUP);
  attachInterrupt(CST816_INT_PIN, Touch_CST816_ISR, FALLING); 

  Serial.println("Touch_Init: Complete!");
  return true;
}

// Reset controller - match demo timing exactly
uint8_t CST816_Touch_Reset(void)
{
  Serial.println("CST816_Touch_Reset: Setting EXIO_PIN1 LOW...");
  Set_EXIO(EXIO_PIN1, Low);
  vTaskDelay(pdMS_TO_TICKS(10));
  Serial.println("CST816_Touch_Reset: Setting EXIO_PIN1 HIGH...");
  Set_EXIO(EXIO_PIN1, High);
  vTaskDelay(pdMS_TO_TICKS(50));  // Demo uses 50ms, not 100ms
  
  // Scan I2C after reset to see if CST816 appears
  Serial.println("I2C scan after touch reset...");
  for (uint8_t addr = 0x10; addr < 0x60; addr++) {
    Wire.beginTransmission(addr);
    uint8_t error = Wire.endTransmission();
    if (error == 0) {
      Serial.printf("  Device at 0x%02X\r\n", addr);
    }
  }
  
  return true;
}

uint16_t CST816_Read_cfg(void) {
  uint8_t buf[3];
  I2C_Read_Touch(CST816_ADDR, CST816_REG_Version, buf, 1);
  Serial.printf("TouchPad_Version: 0x%02x\r\n", buf[0]);
  
  I2C_Read_Touch(CST816_ADDR, CST816_REG_ChipID, buf, 3);
  Serial.printf("ChipID: 0x%02x  ProjID: 0x%02x  FwVersion: 0x%02x\r\n", buf[0], buf[1], buf[2]);
  return true;
}

void CST816_AutoSleep(bool Sleep_State) {
  CST816_Touch_Reset();
  uint8_t Sleep_State_Set = 10;
  I2C_Write_Touch(CST816_ADDR, CST816_REG_DisAutoSleep, &Sleep_State_Set, 1);
}

// Read touch data
uint8_t Touch_Read_Data(void) {
  uint8_t buf[6] = {0};
  
  if (!I2C_Read_Touch(CST816_ADDR, CST816_REG_GestureID, buf, 6)) {
    // I2C failed - don't update touch data with garbage
    return false;
  }
  
  // Validate data - coordinates must be within display range
  uint16_t x = ((buf[2] & 0x0F) << 8) + buf[3];
  uint16_t y = ((buf[4] & 0x0F) << 8) + buf[5];
  
  if (x > 360 || y > 360) {
    // Invalid coordinates - ignore this read
    return false;
  }
  
  // Touched gesture - only valid gesture codes
  uint8_t gesture = buf[0];
  if (gesture <= 5 || gesture == 0x0B || gesture == 0x0C) {
    touch_data.gesture = (GESTURE)gesture;
  }
  
  if (buf[1] != 0x00) {        
    noInterrupts(); 
    touch_data.points = (buf[1] <= CST816_LCD_TOUCH_MAX_POINTS) ? buf[1] : CST816_LCD_TOUCH_MAX_POINTS;
    touch_data.x = x;               
    touch_data.y = y;
    interrupts();
    
    // Debug: Print valid touches
    Serial.printf("Touch: X=%u Y=%u gesture=%d\r\n", touch_data.x, touch_data.y, (int)touch_data.gesture);
  }
  return true;
}

// Touch loop with debug output
void Touch_Loop(void) {
  if (Touch_interrupts) {
    Touch_interrupts = false;
    delayMicroseconds(100);  // Small delay after interrupt before I2C read
    Touch_Read_Data();
  }
}

String Touch_GestureName(void) {
  switch (touch_data.gesture) {
    case NONE: return "NONE";
    case SWIPE_DOWN: return "SWIPE DOWN";
    case SWIPE_UP: return "SWIPE UP";
    case SWIPE_LEFT: return "SWIPE LEFT";
    case SWIPE_RIGHT: return "SWIPE RIGHT";
    case SINGLE_CLICK: return "SINGLE CLICK";
    case DOUBLE_CLICK: return "DOUBLE CLICK";
    case LONG_PRESS: return "LONG PRESS";
    default: return "UNKNOWN";
  }
}
