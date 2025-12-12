#include "I2C_Driver.h"

void I2C_Init(void) {
  Wire.begin(I2C_SDA_PIN, I2C_SCL_PIN);
  Wire.setClock(100000);  // 100kHz I2C clock - slower but more reliable
  
  // Scan I2C bus to see what devices respond
  Serial.println("Scanning I2C bus...");
  for (uint8_t addr = 1; addr < 127; addr++) {
    Wire.beginTransmission(addr);
    uint8_t error = Wire.endTransmission();
    if (error == 0) {
      Serial.printf("I2C device found at 0x%02X", addr);
      if (addr == 0x15) Serial.print(" (CST816 Touch)");
      else if (addr == 0x20) Serial.print(" (TCA9554 IO Expander)");
      else if (addr == 0x51) Serial.print(" (PCF85063 RTC)");
      Serial.println();
    }
  }
  Serial.println("I2C scan complete.");
}

bool I2C_Read(uint8_t Driver_addr, uint8_t Reg_addr, uint8_t *Reg_data, uint32_t Length)
{
  Wire.beginTransmission(Driver_addr);
  Wire.write(Reg_addr); 
  if (Wire.endTransmission(true)) {
    printf("The I2C transmission fails. - I2C Read\r\n");
    return false;
  }
  Wire.requestFrom(Driver_addr, Length);
  for (uint32_t i = 0; i < Length; i++) {
    *Reg_data++ = Wire.read();
  }
  return true;
}

bool I2C_Write(uint8_t Driver_addr, uint8_t Reg_addr, const uint8_t *Reg_data, uint32_t Length)
{
  Wire.beginTransmission(Driver_addr);
  Wire.write(Reg_addr);       
  for (uint32_t i = 0; i < Length; i++) {
    Wire.write(*Reg_data++);
  }
  if (Wire.endTransmission(true)) {
    printf("The I2C transmission fails. - I2C Write\r\n");
    return false;
  }
  return true;
}
