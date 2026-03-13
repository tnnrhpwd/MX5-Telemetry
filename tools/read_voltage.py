#!/usr/bin/env python3
"""Quick ADS1115 voltage reading test"""
import smbus, struct, time
bus = smbus.SMBus(1)
bus.write_i2c_block_data(0x48, 0x01, [0xC3, 0x83])
time.sleep(0.01)
raw = bus.read_i2c_block_data(0x48, 0x00, 2)
val = struct.unpack(">h", bytes(raw))[0]
adc_v = val * 4.096 / 32768
src_v = adc_v * (24700 / 4700)
print("ADC raw: %d" % val)
print("ADC voltage: %.4f V" % adc_v)
print("Source voltage: %.2f V" % src_v)
