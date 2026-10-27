## start webserver
```python
import network
sta = network.WLAN(network.STA_IF)
sta.active(1)
sta.connect("Kittenbot","kittenbot428")
sta.ifconfig()
sta.webserver()
```
## irq
```python
from machine import Pin
import time

# 常量定义
MAX_PULSES = 68  # 最大脉冲数
PULSE_THRESHOLD = 2000  # 脉冲时间阈值(μs)
START_INDEX = 4  # 跳过前导脉冲

def decode_ir_pulse(pin):
    """解码红外接收信号"""
    state = pin.value()
    pulses = []
    start_time = time.ticks_us()
    count = 0
    
    while count < MAX_PULSES:
        current_value = pin.value()
        if current_value != state:
            count += 1
            pulse_time = time.ticks_diff(time.ticks_us(), start_time)
            pulses.append(pulse_time)
            start_time = time.ticks_us()
            state = current_value
    
    # 解码数据
    data_pulses = pulses[START_INDEX:]  # 跳过前导脉冲
    decoded_value = 0
    
    for i in range(0, len(data_pulses), 2):
        # 检查是否有足够的脉冲对
        if i+1 >= len(data_pulses):
            break
            
        # 解码逻辑
        if data_pulses[i] + data_pulses[i+1] > PULSE_THRESHOLD:
            decoded_value = (decoded_value << 1) | 0
        else:
            decoded_value = (decoded_value << 1) | 1
    
    print(f"Raw pulses: {pulses}")
    print(f"Decoded value: 0x{decoded_value:08X}")
    return decoded_value

# 初始化红外接收引脚
ir_pin = Pin(4, Pin.IN, Pin.PULL_UP)

# 设置中断处理
def ir_handler(pin):
    """中断处理函数"""
    print("IR signal detected")
    decode_ir_pulse(pin)

ir_pin.irq(trigger=Pin.IRQ_FALLING, handler=ir_handler)

print("IR receiver ready...")
```