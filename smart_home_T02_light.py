# 智能管家灯光控制工具 - 控制LED灯的开关和亮度

from future import MeowPin
from sugar import *

# 初始化LED引脚 - 接口3
led_pin = MeowPin("P3", "OUT")
brightness_pin = MeowPin("P3", "PWM")  # PWM控制亮度

def execute_smart_home_light_control(action, brightness=50):
    """
    控制智能LED灯
    
    Args:
        action: LED灯控制动作 (on, off, set_brightness, status)
        brightness: LED灯亮度 (0-100)
        
    Returns:
        str: 控制结果
    """
    try:
        if action == "on":
            # 开灯
            if not (0 <= brightness <= 100):
                brightness = 50  # 默认亮度
            
            # 使用PWM控制亮度
            brightness_pin.setFrequency(1000)  # 设置1kHz频率
            # 将0-100的百分比转换为0-4095的PWM值
            pwm_value = int(brightness * 4095 / 100)
            print(pwm_value)
            brightness_pin.setAnalog(pwm_value)
            
            return f"✅ 灯光已开启 (亮度: {brightness}%)"
        
        elif action == "off":
            # 关灯
            brightness_pin.setAnalog(0)  # PWM值为0关闭灯光
            return "✅ 灯光已关闭"
        
        elif action == "set_brightness":
            # 设置灯光亮度
            if not (0 <= brightness <= 100):
                return "❌ 错误：亮度必须在0-100之间"
            
            # 使用PWM控制亮度
            brightness_pin.setFrequency(1000)  # 设置1kHz频率
            # 将0-100的百分比转换为0-4095的PWM值
            pwm_value = int(brightness * 4095 / 100)
            brightness_pin.setAnalog(pwm_value)
            
            return f"✅ 灯光亮度已调节 (亮度: {brightness}%)"
        
        elif action == "status":
            # 查看灯光状态
            # 由于无法直接读取当前PWM值，返回状态信息
            return "📊 灯光状态: 运行中 (请通过控制指令确认当前亮度)"
        
        else:
            return f"❌ 错误：不支持的动作 '{action}'，支持的动作：on, off, set_brightness, status"
        
    except Exception as e:
        return f"❌ 灯光控制失败: {str(e)}"

# 工具定义
FUNTOOL = {
    "name": "smart_home_light_control",
    "description": "智能灯光控制工具，控制LED灯的开关和亮度",
    "parameters": {
        "type": "object",
        "properties": {
            "action": {
                "type": "string",
                "enum": ["on", "off", "set_brightness", "status"],
                "description": "灯光控制动作：on=开灯, off=关灯, set_brightness=调节亮度, status=查看状态"
            },
            "brightness": {
                "type": "number",
                "minimum": 0,
                "maximum": 100,
                "description": "灯光亮度(0-100%)，默认50%"
            }
        },
        "required": ["action"]
    }
}