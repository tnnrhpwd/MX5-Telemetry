/*
 * QMI8658 IMU Driver for ESP32-S3-Touch-LCD-1.85
 * 6-axis IMU (3-axis accelerometer + 3-axis gyroscope)
 * I2C interface on GPIO10 (SCL) and GPIO11 (SDA)
 */

#ifndef QMI8658_H
#define QMI8658_H

#include <Wire.h>

// QMI8658 I2C Address
#define QMI8658_ADDRESS     0x6B  // Default address

// Register addresses
#define QMI8658_WHO_AM_I    0x00
#define QMI8658_REVISION    0x01
#define QMI8658_CTRL1       0x02  // Serial interface and sensor enable
#define QMI8658_CTRL2       0x03  // Accelerometer settings
#define QMI8658_CTRL3       0x04  // Gyroscope settings
#define QMI8658_CTRL5       0x06  // Sensor data processing settings
#define QMI8658_CTRL7       0x08  // Enable sensors
#define QMI8658_CTRL9       0x0A  // Host commands
#define QMI8658_STATUS0     0x2E
#define QMI8658_STATUS1     0x2F
#define QMI8658_TIMESTAMP_L 0x30
#define QMI8658_TEMP_L      0x33
#define QMI8658_TEMP_H      0x34
#define QMI8658_AX_L        0x35
#define QMI8658_AX_H        0x36
#define QMI8658_AY_L        0x37
#define QMI8658_AY_H        0x38
#define QMI8658_AZ_L        0x39
#define QMI8658_AZ_H        0x3A
#define QMI8658_GX_L        0x3B
#define QMI8658_GX_H        0x3C
#define QMI8658_GY_L        0x3D
#define QMI8658_GY_H        0x3E
#define QMI8658_GZ_L        0x3F
#define QMI8658_GZ_H        0x40
#define QMI8658_RESET       0x60

// Expected WHO_AM_I value
#define QMI8658_WHO_AM_I_VALUE  0x05

// Accelerometer full scale range
enum QMI8658_AccScale {
    QMI8658_ACC_RANGE_2G  = 0,
    QMI8658_ACC_RANGE_4G  = 1,
    QMI8658_ACC_RANGE_8G  = 2,
    QMI8658_ACC_RANGE_16G = 3
};

// Gyroscope full scale range
enum QMI8658_GyroScale {
    QMI8658_GYR_RANGE_16DPS   = 0,
    QMI8658_GYR_RANGE_32DPS   = 1,
    QMI8658_GYR_RANGE_64DPS   = 2,
    QMI8658_GYR_RANGE_128DPS  = 3,
    QMI8658_GYR_RANGE_256DPS  = 4,
    QMI8658_GYR_RANGE_512DPS  = 5,
    QMI8658_GYR_RANGE_1024DPS = 6,
    QMI8658_GYR_RANGE_2048DPS = 7
};

// Output data rate
enum QMI8658_ODR {
    QMI8658_ODR_8000HZ  = 0,
    QMI8658_ODR_4000HZ  = 1,
    QMI8658_ODR_2000HZ  = 2,
    QMI8658_ODR_1000HZ  = 3,
    QMI8658_ODR_500HZ   = 4,
    QMI8658_ODR_250HZ   = 5,
    QMI8658_ODR_125HZ   = 6,
    QMI8658_ODR_62_5HZ  = 7,
    QMI8658_ODR_31_25HZ = 8
};

class QMI8658 {
public:
    QMI8658();
    
    // Initialize the IMU
    bool begin(TwoWire &wire = Wire, uint8_t addr = QMI8658_ADDRESS);
    
    // Check if device is connected
    bool isConnected();
    
    // Configure accelerometer
    void setAccelScale(QMI8658_AccScale scale);
    void setAccelODR(QMI8658_ODR odr);
    
    // Configure gyroscope
    void setGyroScale(QMI8658_GyroScale scale);
    void setGyroODR(QMI8658_ODR odr);
    
    // Read raw sensor data
    void readAccelRaw(int16_t *ax, int16_t *ay, int16_t *az);
    void readGyroRaw(int16_t *gx, int16_t *gy, int16_t *gz);
    
    // Read scaled sensor data (in G and degrees/sec)
    void readAccel(float *ax, float *ay, float *az);
    void readGyro(float *gx, float *gy, float *gz);
    
    // Convenience methods for G-force
    float getAccelX();
    float getAccelY();
    float getAccelZ();
    float getGyroX();
    float getGyroY();
    float getGyroZ();
    
    // Read temperature
    float getTemperature();
    
    // Update all readings at once (more efficient)
    void update();
    
    // Get last read values (after update())
    float ax, ay, az;  // Accelerometer (G)
    float gx, gy, gz;  // Gyroscope (deg/s)
    float temp;        // Temperature (°C)
    
private:
    TwoWire *_wire;
    uint8_t _addr;
    float _accelScale;
    float _gyroScale;
    
    void writeRegister(uint8_t reg, uint8_t val);
    uint8_t readRegister(uint8_t reg);
    void readRegisters(uint8_t reg, uint8_t *buf, uint8_t len);
    void reset();
    void configure();
};

#endif // QMI8658_H
