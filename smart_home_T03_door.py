# 智能管家门控制工具 - 控制舵机门的开关

from future import geekservo9g

def execute_smart_home_door_control(action, angle=90):
    """
    控制智能门
    
    Args:
        action: 门控制动作 (open, close, status)
        angle: 舵机角度 (0-180)
        
    Returns:
        str: 控制结果
    """
    try:
        if action == "open":
            # 开门
            open_angle = 180  # 开门角度
            geekservo9g('P4', open_angle)  # 接口4控制舵机
            return f"✅ 门已开启 (角度: {open_angle}°)"
        
        elif action == "close":
            # 关门
            close_angle = 0  # 关门角度
            geekservo9g('P4', close_angle)  # 接口4控制舵机
            return f"✅ 门已关闭 (角度: {close_angle}°)"
        
        elif action == "status":
            # 查看门状态
            # 由于无法直接读取舵机当前角度，返回状态信息
            return "📊 门状态: 请通过控制指令确认当前状态"
        
        else:
            return f"❌ 错误：不支持的动作 '{action}'，支持的动作：open, close, status"
        
    except Exception as e:
        return f"❌ 门控制失败: {str(e)}"

# 工具定义
FUNTOOL = {
    "name": "smart_home_door_control",
    "description": "智能门控制工具，控制舵机门的开关",
    "parameters": {
        "type": "object",
        "properties": {
            "action": {
                "type": "string",
                "enum": ["open", "close", "status"],
                "description": "门控制动作：open=开门, close=关门, status=查看状态"
            },
            "angle": {
                "type": "number",
                "minimum": 0,
                "maximum": 180,
                "description": "舵机角度(0-180°)，默认90°"
            }
        },
        "required": ["action"]
    }
}