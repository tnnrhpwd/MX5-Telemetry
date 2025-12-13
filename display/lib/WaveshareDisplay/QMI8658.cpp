/*
 * QMI8658 IMU Driver Implementation
 * For Waveshare ESP32-S3-Touch-LCD-1.85
 */

#include <Arduino.h>
#include "QMI8658.h"

QMI8658::QMI8658() {
    _wire = nullptr;
    _addr = QMI8658_ADDRESS;
    _accelScale = 2.0f / 32768.0f;  // Default ±2G
    _gyroScale = 16.0f / 32768.0f;  // Default ±16 dps
    ax = ay = az = 0;
    gx = gy = gz = 0;
    temp = 0;
}

bool QMI8658::begin(TwoWire &wire, uint8_t addr) {
    _wire = &wire;
    _addr = addr;
    
    // Check if device responds
    if (!isConnected()) {
        Serial.println("QMI8658: Device not found!");
        return false;
    }
    
    // Reset and configure
    reset();
    delay(50);
    configure();
    
    Serial.println("QMI8658: IMU initialized successfully!");
    return true;
}

bool QMI8658::isConnected() {
    uint8_t whoami = readRegister(QMI8658_WHO_AM_I);
    Serial.printf("QMI8658: WHO_AM_I = 0x%02X (expected 0x%02X)\n", whoami, QMI8658_WHO_AM_I_VALUE);
    return (whoami == QMI8658_WHO_AM_I_VALUE);
}

void QMI8658::reset() {
    writeRegister(QMI8658_RESET, 0xB0);  // Reset command
    delay(10);
}

void QMI8658::configure() {
    // CTRL1: Address auto-increment enabled, Big endian
    writeRegister(QMI8658_CTRL1, 0x40);
    
    // CTRL2: Accelerometer ±4G, 250Hz ODR
    writeRegister(QMI8658_CTRL2, 0x15);  // FS = ±4G, ODR = 250Hz
    _accelScale = 4.0f / 32768.0f;
    
    // CTRL3: Gyroscope ±512 dps, 250Hz ODR
    writeRegister(QMI8658_CTRL3, 0x55);  // FS = ±512 dps, ODR = 250Hz
    _gyroScale = 512.0f / 32768.0f;
    
    // CTRL5: Enable low-pass filter
    writeRegister(QMI8658_CTRL5, 0x00);
    
    // CTRL7: Enable accelerometer and gyroscope
    writeRegister(QMI8658_CTRL7, 0x03);  // aEN = 1, gEN = 1
    
    delay(10);
}

void QMI8658::setAccelScale(QMI8658_AccScale scale) {
    uint8_t ctrl2 = readRegister(QMI8658_CTRL2);
    ctrl2 = (ctrl2 & 0x8F) | (scale << 4);
    writeRegister(QMI8658_CTRL2, ctrl2);
    
    switch(scale) {
        case QMI8658_ACC_RANGE_2G:  _accelScale = 2.0f / 32768.0f;  break;
        case QMI8658_ACC_RANGE_4G:  _accelScale = 4.0f / 32768.0f;  break;
        case QMI8658_ACC_RANGE_8G:  _accelScale = 8.0f / 32768.0f;  break;
        case QMI8658_ACC_RANGE_16G: _accelScale = 16.0f / 32768.0f; break;
    }
}

void QMI8658::setAccelODR(QMI8658_ODR odr) {
    uint8_t ctrl2 = readRegister(QMI8658_CTRL2);
    ctrl2 = (ctrl2 & 0xF0) | odr;
    writeRegister(QMI8658_CTRL2, ctrl2);
}

void QMI8658::setGyroScale(QMI8658_GyroScale scale) {
    uint8_t ctrl3 = readRegister(QMI8658_CTRL3);
    ctrl3 = (ctrl3 & 0x8F) | (scale << 4);
    writeRegister(QMI8658_CTRL3, ctrl3);
    
    switch(scale) {
        case QMI8658_GYR_RANGE_16DPS:   _gyroScale = 16.0f / 32768.0f;   break;
        case QMI8658_GYR_RANGE_32DPS:   _gyroScale = 32.0f / 32768.0f;   break;
        case QMI8658_GYR_RANGE_64DPS:   _gyroScale = 64.0f / 32768.0f;   break;
        case QMI8658_GYR_RANGE_128DPS:  _gyroScale = 128.0f / 32768.0f;  break;
        case QMI8658_GYR_RANGE_256DPS:  _gyroScale = 256.0f / 32768.0f;  break;
        case QMI8658_GYR_RANGE_512DPS:  _gyroScale = 512.0f / 32768.0f;  break;
        case QMI8658_GYR_RANGE_1024DPS: _gyroScale = 1024.0f / 32768.0f; break;
        case QMI8658_GYR_RANGE_2048DPS: _gyroScale = 2048.0f / 32768.0f; break;
    }
}

void QMI8658::setGyroODR(QMI8658_ODR odr) {
    uint8_t ctrl3 = readRegister(QMI8658_CTRL3);
    ctrl3 = (ctrl3 & 0xF0) | odr;
    writeRegister(QMI8658_CTRL3, ctrl3);
}

void QMI8658::readAccelRaw(int16_t *ax, int16_t *ay, int16_t *az) {
    uint8_t buf[6];
    readRegisters(QMI8658_AX_L, buf, 6);
    
    *ax = (int16_t)((buf[1] << 8) | buf[0]);
    *ay = (int16_t)((buf[3] << 8) | buf[2]);
    *az = (int16_t)((buf[5] << 8) | buf[4]);
}

void QMI8658::readGyroRaw(int16_t *gx, int16_t *gy, int16_t *gz) {
    uint8_t buf[6];
    readRegisters(QMI8658_GX_L, buf, 6);
    
    *gx = (int16_t)((buf[1] << 8) | buf[0]);
    *gy = (int16_t)((buf[3] << 8) | buf[2]);
    *gz = (int16_t)((buf[5] << 8) | buf[4]);
}

void QMI8658::readAccel(float *ax, float *ay, float *az) {
    int16_t rawX, rawY, rawZ;
    readAccelRaw(&rawX, &rawY, &rawZ);
    
    *ax = rawX * _accelScale;
    *ay = rawY * _accelScale;
    *az = rawZ * _accelScale;
}

void QMI8658::readGyro(float *gx, float *gy, float *gz) {
    int16_t rawX, rawY, rawZ;
    readGyroRaw(&rawX, &rawY, &rawZ);
    
    *gx = rawX * _gyroScale;
    *gy = rawY * _gyroScale;
    *gz = rawZ * _gyroScale;
}

float QMI8658::getAccelX() {
    int16_t raw;
    uint8_t buf[2];
    readRegisters(QMI8658_AX_L, buf, 2);
    raw = (int16_t)((buf[1] << 8) | buf[0]);
    return raw * _accelScale;
}

float QMI8658::getAccelY() {
    int16_t raw;
    uint8_t buf[2];
    readRegisters(QMI8658_AY_L, buf, 2);
    raw = (int16_t)((buf[1] << 8) | buf[0]);
    return raw * _accelScale;
}

float QMI8658::getAccelZ() {
    int16_t raw;
    uint8_t buf[2];
    readRegisters(QMI8658_AZ_L, buf, 2);
    raw = (int16_t)((buf[1] << 8) | buf[0]);
    return raw * _accelScale;
}

float QMI8658::getGyroX() {
    int16_t raw;
    uint8_t buf[2];
    readRegisters(QMI8658_GX_L, buf, 2);
    raw = (int16_t)((buf[1] << 8) | buf[0]);
    return raw * _gyroScale;
}

float QMI8658::getGyroY() {
    int16_t raw;
    uint8_t buf[2];
    readRegisters(QMI8658_GY_L, buf, 2);
    raw = (int16_t)((buf[1] << 8) | buf[0]);
    return raw * _gyroScale;
}

float QMI8658::getGyroZ() {
    int16_t raw;
    uint8_t buf[2];
    readRegisters(QMI8658_GZ_L, buf, 2);
    raw = (int16_t)((buf[1] << 8) | buf[0]);
    return raw * _gyroScale;
}

float QMI8658::getTemperature() {
    uint8_t buf[2];
    readRegisters(QMI8658_TEMP_L, buf, 2);
    int16_t raw = (int16_t)((buf[1] << 8) | buf[0]);
    return raw / 256.0f;  // Temperature in °C
}

void QMI8658::update() {
    // Read all sensor data in one burst
    uint8_t buf[12];
    readRegisters(QMI8658_AX_L, buf, 12);
    
    int16_t rawAx = (int16_t)((buf[1] << 8) | buf[0]);
    int16_t rawAy = (int16_t)((buf[3] << 8) | buf[2]);
    int16_t rawAz = (int16_t)((buf[5] << 8) | buf[4]);
    int16_t rawGx = (int16_t)((buf[7] << 8) | buf[6]);
    int16_t rawGy = (int16_t)((buf[9] << 8) | buf[8]);
    int16_t rawGz = (int16_t)((buf[11] << 8) | buf[10]);
    
    ax = rawAx * _accelScale;
    ay = rawAy * _accelScale;
    az = rawAz * _accelScale;
    gx = rawGx * _gyroScale;
    gy = rawGy * _gyroScale;
    gz = rawGz * _gyroScale;
    
    // Read temperature
    temp = getTemperature();
}

void QMI8658::writeRegister(uint8_t reg, uint8_t val) {
    _wire->beginTransmission(_addr);
    _wire->write(reg);
    _wire->write(val);
    _wire->endTransmission();
}

uint8_t QMI8658::readRegister(uint8_t reg) {
    _wire->beginTransmission(_addr);
    _wire->write(reg);
    _wire->endTransmission(false);
    _wire->requestFrom(_addr, (uint8_t)1);
    return _wire->read();
}

void QMI8658::readRegisters(uint8_t reg, uint8_t *buf, uint8_t len) {
    _wire->beginTransmission(_addr);
    _wire->write(reg);
    _wire->endTransmission(false);
    _wire->requestFrom(_addr, len);
    for (uint8_t i = 0; i < len; i++) {
        buf[i] = _wire->read();
    }
}
