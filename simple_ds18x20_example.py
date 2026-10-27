# 简单的DS18x20水温传感器使用示例

from machine import Pin
import time
from ds18x20 import DS18X20
from onewire import OneWire

# 硬件连接说明：
# DS18x20传感器连接到引脚1
# VCC -> 3.3V
# GND -> GND  
# DATA -> 引脚1

# 初始化引脚
pin = Pin(1, Pin.IN, Pin.PULL_UP)

# 初始化OneWire总线
ow = OneWire(pin)

# 初始化DS18x20传感器
ds = DS18X20(ow)

# 扫描传感器
roms = ds.scan()
print(f"找到 {len(roms)} 个DS18x20传感器")

if roms:
    # 获取第一个传感器
    rom = roms[0]
    print(f"传感器地址: {[hex(x) for x in rom]}")
    
    # 连续读取温度
    while True:
        try:
            # 开始温度转换
            ds.convert_temp()
            
            # 等待转换完成（DS18x20需要750ms）
            time.sleep_ms(750)
            
            # 读取温度
            temp = ds.read_temp(rom)
            
            print(f"水温: {temp:.2f}°C")
            
            # 等待2秒后再次读取
            time.sleep(2)
            
        except Exception as e:
            print(f"读取温度时出错: {e}")
            time.sleep(1)
else:
    print("未找到DS18x20传感器，请检查连接") 