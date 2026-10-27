# 智能管家风扇控制工具 - 控制风扇的开关和速度

from future import Motor

# 初始化电机对象
motor = Motor()

def execute_smart_home_fan_control(action, speed=50):
    """
    控制智能风扇
    
    Args:
        action: 风扇控制动作 (on, off, set_speed, status)
        speed: 风扇速度 (0-100)
        
    Returns:
        str: 控制结果
    """
    try:
        if action == "on":
            # 开风扇
            if not (0 <= speed <= 100):
                speed = 50  # 默认速度
            
            motor.setSpeed(2, speed)  # 电机口2控制风扇
            return f"✅ 风扇已开启 (速度: {speed}%)"
        
        elif action == "off":
            # 关风扇
            motor.setSpeed(2, 0)  # 速度为0停止风扇
            return "✅ 风扇已关闭"
        
        elif action == "set_speed":
            # 设置风扇速度
            if not (0 <= speed <= 100):
                return "❌ 错误：速度必须在0-100之间"
            
            motor.setSpeed(2, speed)  # 电机口2控制风扇
            return f"✅ 风扇速度已调节 (速度: {speed}%)"
        
        elif action == "status":
            # 查看风扇状态
            # 由于无法直接读取当前速度，返回状态信息
            return "📊 风扇状态: 运行中 (请通过控制指令确认当前速度)"
        
        else:
            return f"❌ 错误：不支持的动作 '{action}'，支持的动作：on, off, set_speed, status"
        
    except Exception as e:
        return f"❌ 风扇控制失败: {str(e)}"

# 工具定义
FUNTOOL = {
    "name": "smart_home_fan_control",
    "description": "智能风扇控制工具，控制风扇的开关和速度",
    "parameters": {
        "type": "object",
        "properties": {
            "action": {
                "type": "string",
                "enum": ["on", "off", "set_speed", "status"],
                "description": "风扇控制动作：on=开风扇, off=关风扇, set_speed=调节速度, status=查看状态"
            },
            "speed": {
                "type": "number",
                "minimum": 0,
                "maximum": 100,
                "description": "风扇速度(0-100%)，默认50%"
            }
        },
        "required": ["action"]
    }
}