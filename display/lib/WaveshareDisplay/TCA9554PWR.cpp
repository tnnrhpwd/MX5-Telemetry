#include "TCA9554PWR.h"

uint8_t Read_REG(uint8_t REG)
{
  Wire.beginTransmission(TCA9554_ADDRESS);                
  Wire.write(REG);                                        
  uint8_t result = Wire.endTransmission();               
  if (result != 0) {                                     
    printf("Data Transfer Failure !!!\r\n");
  }
  Wire.requestFrom(TCA9554_ADDRESS, 1);                   
  uint8_t bitsStatus = Wire.read();                        
  return bitsStatus;                                     
}

uint8_t Write_REG(uint8_t REG, uint8_t Data)
{
  Wire.beginTransmission(TCA9554_ADDRESS);                
  Wire.write(REG);                                        
  Wire.write(Data);                                       
  uint8_t result = Wire.endTransmission();                  
  if (result != 0) {    
    printf("Data write failure!!!\r\n");
    return -1;
  }
  return 0;                                             
}

void Mode_EXIO(uint8_t Pin, uint8_t State)
{
  uint8_t bitsStatus = Read_REG(TCA9554_CONFIG_REG);      
  uint8_t Data = (0x01 << (Pin-1)) | bitsStatus;   
  uint8_t result = Write_REG(TCA9554_CONFIG_REG, Data); 
  if (result != 0) { 
    printf("I/O Configuration Failure !!!\r\n");
  }
}

void Mode_EXIOS(uint8_t PinState)
{
  uint8_t result = Write_REG(TCA9554_CONFIG_REG, PinState);  
  if (result != 0) {   
    printf("I/O Configuration Failure !!!\r\n");
  }
}

uint8_t Read_EXIO(uint8_t Pin)
{
  uint8_t inputBits = Read_REG(TCA9554_INPUT_REG);          
  uint8_t bitStatus = (inputBits >> (Pin-1)) & 0x01; 
  return bitStatus;                                  
}

uint8_t Read_EXIOS(uint8_t REG)
{
  uint8_t inputBits = Read_REG(REG);                     
  return inputBits;     
}

void Set_EXIO(uint8_t Pin, uint8_t State)
{
  uint8_t Data;
  if (State < 2 && Pin < 9 && Pin > 0) {  
    uint8_t bitsStatus = Read_EXIOS(TCA9554_OUTPUT_REG);
    if (State == 1)                                     
      Data = (0x01 << (Pin-1)) | bitsStatus; 
    else if (State == 0)                  
      Data = (~(0x01 << (Pin-1))) & bitsStatus;      
    uint8_t result = Write_REG(TCA9554_OUTPUT_REG, Data);  
    if (result != 0) {                         
      printf("Failed to set GPIO!!!\r\n");
    }
  } else {
    printf("Parameter error, please enter the correct parameter!\r\n");
  }
}

void Set_EXIOS(uint8_t PinState)
{
  uint8_t result = Write_REG(TCA9554_OUTPUT_REG, PinState); 
  if (result != 0) {                  
    printf("Failed to set GPIO!!!\r\n");
  }
}

void Set_Toggle(uint8_t Pin)
{
  uint8_t bitsStatus = Read_EXIO(Pin);                 
  Set_EXIO(Pin, (bool)!bitsStatus); 
}

void TCA9554PWR_Init(uint8_t PinState)
{                  
  Mode_EXIOS(PinState);      
}
