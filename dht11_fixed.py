from microbit import *
import utime

# 全局变量存储读数
dht11_humidity = 0
dht11_temperature = 0

class DHT11Type:
    TemperatureC = 0
    TemperatureF = 1
    Humidity = 2

def DHT11(pin, read_type):
    global dht11_humidity, dht11_temperature
    
    # 使用更宽松的时序参数
    DHT11_TIMEOUT = 5000  # 增加到5毫秒
    
    # 初始化引脚状态
    pin.set_pull(pin.NO_PULL)
    pin.write_digital(1)
    sleep(1)  # 等待稳定
    
    # 1. 发送开始信号
    pin.write_digital(0)
    sleep(20)  # 保持低电平20ms
    
    # 2. 释放总线并设置上拉
    pin.write_digital(1)
    pin.set_pull(pin.PULL_UP)
    
    # 3. 等待DHT11响应（拉低总线）
    start_time = utime.ticks_us()
    while pin.read_digital() == 1:
        if utime.ticks_diff(utime.ticks_us(), start_time) > DHT11_TIMEOUT:
            print("DHT11响应超时")
            return -1
    
    # 4. 等待DHT11拉高总线
    start_time = utime.ticks_us()
    while pin.read_digital() == 0:
        if utime.ticks_diff(utime.ticks_us(), start_time) > DHT11_TIMEOUT:
            print("DHT11响应信号异常")
            return -1
    
    # 5. 等待DHT11再次拉低（数据开始）
    start_time = utime.ticks_us()
    while pin.read_digital() == 1:
        if utime.ticks_diff(utime.ticks_us(), start_time) > DHT11_TIMEOUT:
            print("DHT11数据开始信号异常")
            return -1
    
    # 6. 读取40位数据 - 使用更宽松的时序
    buffer = [0] * 40
    for i in range(40):
        # 等待数据位开始（低电平）
        start_time = utime.ticks_us()
        while pin.read_digital() == 0:
            if utime.ticks_diff(utime.ticks_us(), start_time) > DHT11_TIMEOUT:
                print("数据位开始信号超时: ",i)
                return -1
        
        # 等待数据位结束（高电平）- 增加超时时间
        start_time = utime.ticks_us()
        timeout_count = 0
        while pin.read_digital() == 1:
            if utime.ticks_diff(utime.ticks_us(), start_time) > DHT11_TIMEOUT:
                # 如果超时，尝试继续读取而不是直接返回错误
                print("数据位", i, "超时，尝试继续...")
                break
        
        # 根据高电平持续时间判断数据位
        high_duration = utime.ticks_diff(utime.ticks_us(), start_time)
        if high_duration > 80:  # 降低阈值到80微秒
            buffer[i] = 1
    
    # 7. 将40位数据转换为5个字节
    data = [0, 0, 0, 0, 0]
    for i in range(5):
        for j in range(8):
            if buffer[8 * i + j] == 1:
                data[i] += 2 ** (7 - j)
    
    # 8. 验证校验和
    checksum = (data[0] + data[1] + data[2] + data[3]) & 0xFF
    if checksum == data[4]:
        dht11_humidity = data[0] + data[1] * 0.1
        dht11_temperature = data[2] + data[3] * 0.1
        
        # 返回请求的值
        if read_type == DHT11Type.TemperatureC:
            return round(dht11_temperature)
        elif read_type == DHT11Type.TemperatureF:
            return round(dht11_temperature * 1.8 + 32)
        elif read_type == DHT11Type.Humidity:
            return round(dht11_humidity)
        else:
            return 0
    else:
        print("DHT11校验和错误")
        return -1

# 简化的DHT11读取函数（备选方案）
def simple_dht11_read(pin):
    """使用更简单的方法读取DHT11"""
    try:
        # 初始化
        pin.set_pull(pin.NO_PULL)
        pin.write_digital(1)
        sleep(1)
        
        # 发送开始信号
        pin.write_digital(0)
        sleep(25)  # 25ms低电平
        
        # 释放总线
        pin.write_digital(1)
        pin.set_pull(pin.PULL_UP)
        
        # 等待响应
        start = utime.ticks_us()
        while pin.read_digital() == 1:
            if utime.ticks_diff(utime.ticks_us(), start) > 10000:
                return None, None
        
        # 等待响应结束
        start = utime.ticks_us()
        while pin.read_digital() == 0:
            if utime.ticks_diff(utime.ticks_us(), start) > 10000:
                return None, None
        
        # 等待数据开始
        start = utime.ticks_us()
        while pin.read_digital() == 1:
            if utime.ticks_diff(utime.ticks_us(), start) > 10000:
                return None, None
        
        # 读取数据位
        data = []
        for _ in range(40):
            # 等待位开始
            start = utime.ticks_us()
            while pin.read_digital() == 0:
                if utime.ticks_diff(utime.ticks_us(), start) > 10000:
                    return None, None
            
            # 测量高电平时间
            start = utime.ticks_us()
            while pin.read_digital() == 1:
                if utime.ticks_diff(utime.ticks_us(), start) > 10000:
                    return None, None
            
            duration = utime.ticks_diff(utime.ticks_us(), start)
            data.append(1 if duration > 60 else 0)
        
        # 转换为字节
        bytes_data = []
        for i in range(5):
            byte_val = 0
            for j in range(8):
                byte_val |= data[i * 8 + j] << (7 - j)
            bytes_data.append(byte_val)
        
        # 验证校验和
        checksum = (bytes_data[0] + bytes_data[1] + bytes_data[2] + bytes_data[3]) & 0xFF
        if checksum != bytes_data[4]:
            return None, None
        
        # 计算温湿度
        humidity = bytes_data[0] + bytes_data[1] * 0.1
        temperature = bytes_data[2] + bytes_data[3] * 0.1
        
        return temperature, humidity
        
    except Exception as e:
        print("简化读取错误:", e)
        return None, None

# 测试代码
print("开始DHT11测试...")
while True:
    # 首先尝试标准方法
    temp = DHT11(pin12, DHT11Type.TemperatureC)
    humid = DHT11(pin12, DHT11Type.Humidity)
    
    if temp != -1 and humid != -1:
        print("标准方法 - 温度:", temp, "°C, 湿度:", humid, "%")
    else:
        print("标准方法失败，尝试简化方法...")
        # 尝试简化方法
        temp, humid = simple_dht11_read(pin12)
        if temp is not None and humid is not None:
            print("简化方法 - 温度:", temp, "°C, 湿度:", humid, "%")
        else:
            print("两种方法都失败")
    
    print("---")
    sleep(3000)  # 等待3秒 