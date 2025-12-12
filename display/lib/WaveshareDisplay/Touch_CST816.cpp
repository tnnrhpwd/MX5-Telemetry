#include "Touch_CST816.h"

struct CST816_Touch touch_data = {0};
volatile uint8_t Touch_interrupts = 0;

// Touch controller uses same I2C bus as IO expander (Wire)
static bool I2C_Read_Touch(uint16_t Driver_addr, uint8_t Reg_addr, uint8_t *Reg_data, uint32_t Length)
{
  Wire.beginTransmission((uint8_t)Driver_addr);
  Wire.write(Reg_addr); 
  if (Wire.endTransmission(true)) {  // true = send stop
    return false;
  }
  Wire.requestFrom((uint8_t)Driver_addr, (uint8_t)Length);
  uint32_t i = 0;
  while (Wire.available() && i < Length) {
    *Reg_data++ = Wire.read();
    i++;
  }
  return (i == Length);  // Return true only if we got all bytes
}

static bool I2C_Write_Touch(uint8_t Driver_addr, uint8_t Reg_addr, const uint8_t *Reg_data, uint32_t Length)
{
  Wire.beginTransmission(Driver_addr);
  Wire.write(Reg_addr);       
  for (uint32_t i = 0; i < Length; i++) {
    Wire.write(*Reg_data++);
  }
  if (Wire.endTransmission(true)) {
    return false;
  }
  return true;
}

void IRAM_ATTR Touch_CST816_ISR(void) {
  Touch_interrupts = true;
}

uint8_t Touch_Init(void) {
  // I2C is already initialized by I2C_Init() on Wire
  CST816_Touch_Reset();
  CST816_Read_cfg();
  CST816_AutoSleep(true);
   
  pinMode(CST816_INT_PIN, INPUT_PULLUP);
  attachInterrupt(CST816_INT_PIN, Touch_CST816_ISR, FALLING); 

  Serial.println("Touch initialized!");
  return true;
}

uint8_t CST816_Touch_Reset(void)
{
  Serial.println("Touch: Resetting CST816 via EXIO_PIN1...");
  Set_EXIO(EXIO_PIN1, Low);
  vTaskDelay(pdMS_TO_TICKS(10));
  Set_EXIO(EXIO_PIN1, High);
  vTaskDelay(pdMS_TO_TICKS(100));  // Wait longer for touch controller to boot
  
  // Scan for touch controller after reset
  Serial.println("Touch: Scanning I2C for CST816...");
  Wire.beginTransmission(CST816_ADDR);
  uint8_t result = Wire.endTransmission();
  Serial.printf("Touch: CST816 at 0x%02X - %s\n", CST816_ADDR, result == 0 ? "FOUND" : "NOT FOUND");
  
  return result == 0;
}

uint16_t CST816_Read_cfg(void) {
  uint8_t buf[3] = {0};
  bool ok1 = I2C_Read_Touch(CST816_ADDR, CST816_REG_Version, buf, 1);
  Serial.printf("TouchPad_Version: 0x%02x (read %s)\r\n", buf[0], ok1 ? "OK" : "FAILED");
  
  bool ok2 = I2C_Read_Touch(CST816_ADDR, CST816_REG_ChipID, buf, 3);
  Serial.printf("ChipID: 0x%02x  ProjID: 0x%02x  FwVersion: 0x%02x (read %s)\r\n", 
                buf[0], buf[1], buf[2], ok2 ? "OK" : "FAILED");
  return ok1 && ok2;
}

void CST816_AutoSleep(bool Sleep_State) {
  CST816_Touch_Reset();
  uint8_t Sleep_State_Set = 10;
  I2C_Write_Touch(CST816_ADDR, CST816_REG_DisAutoSleep, &Sleep_State_Set, 1);
}

uint8_t Touch_Read_Data(void) {
  static bool i2cErrorReported = false;
  uint8_t buf[6] = {0};  // Initialize to zero
  if (!I2C_Read_Touch(CST816_ADDR, CST816_REG_GestureID, buf, 6)) {
    if (!i2cErrorReported) {
      Serial.println("Touch I2C read failed! (further errors suppressed)");
      i2cErrorReported = true;
    }
    return false;
  }
  i2cErrorReported = false;  // Reset so we can report again if it starts failing
  
  // Only update if we have a valid gesture (0-5, 0x0B, 0x0C)
  uint8_t gesture = buf[0];
  if (gesture <= 5 || gesture == 0x0B || gesture == 0x0C) {
    touch_data.gesture = (GESTURE)gesture;
  }
  
  uint8_t points = buf[1];
  if (points > 0 && points <= CST816_LCD_TOUCH_MAX_POINTS) {        
    noInterrupts(); 
    touch_data.points = points;
    touch_data.x = ((buf[2] & 0x0F) << 8) + buf[3];               
    touch_data.y = ((buf[4] & 0x0F) << 8) + buf[5];
    interrupts(); 
  }
  return true;
}

void Touch_Loop(void) {
  if (Touch_interrupts) {
    Touch_interrupts = false;
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
