from machine import I2S, Pin
import math
import time

# 硬件配置（根据实际连接修改引脚）
bck_pin = Pin(39)   # PDM时钟线（CLK）
ws_pin = Pin(9)     # 保留引脚（PDM模式下未使用，可忽略）
sdin_pin = Pin(41)  # PDM数据线（DATA）

# 初始化I2S（PDM模式）
mic = I2S(0, sck=bck_pin, ws=ws_pin, sd=sdin_pin, mode=I2S.PDM, bits=16, format=I2S.MONO, rate=44100, ibuf=40000)

# 全局变量
BUFFER_SIZE = 1024   # 每次读取的缓冲区大小
buffer = bytearray(BUFFER_SIZE)

# 计算RMS（均方根）
def calculate_rms(data_buffer):
    samples = memoryview(data_buffer).cast('h')  # 转换为16位有符号整数
    sum_squares = 0
    for sample in samples:
        sum_squares += sample ** 2
    rms = math.sqrt(sum_squares / len(samples))
    return rms

# 计算MAV（平均绝对值）
def calculate_mav(data_buffer):
    samples = memoryview(data_buffer).cast('h')
    mav = sum(abs(s) for s in samples) / len(samples)
    return mav

# 标准化到0~100%（基于经验最大值）
def normalize_intensity(raw_value, max_expected=32768):
    normalized = min(raw_value / max_expected * 100, 100)
    return normalized

# 主循环：实时获取声音强度
try:
    print("开始监测声音强度...")
    while True:
        # 读取PDM数据
        mic.readinto(buffer)
        
        # 计算强度
        rms = calculate_rms(buffer)
        mav = calculate_mav(buffer)
        
        # 标准化输出
        normalized_rms = normalize_intensity(rms)
        normalized_mav = normalize_intensity(mav)
        
        # 打印结果
        print(
            "RMS: {:.1f} (Norm: {:.1f}%) | MAV: {:.1f} (Norm: {:.1f}%)".format(
                rms, normalized_rms, mav, normalized_mav
            )
        )
        
        # 控制输出频率
        time.sleep(0.1)

except KeyboardInterrupt:
    print("停止监测")
    mic.deinit()  # 释放I2S资源