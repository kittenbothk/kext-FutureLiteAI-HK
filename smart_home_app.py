import time, sys, os
from agent import Agent

import wifi

if not wifi.isconnected():
    if wifi.try_auto_connect():
        print("联网成功")
    else:
        print("尝试联网失败，请通过ai编程配网")

# 创建全局的智能管家应用实例，使用真实的agent名称，使用按键说话，默认模式
from board import BTNA,BTNM,BTNB
smart_home_app = Agent('smart_home_app', button=BTNM)
# 如果设置了button参数，则使用按键说话。可以是板载资源BTNA,BTNM,BTNB。也可以是自定义的引脚(machine.Pin)。

# 持续语音输入模式，除非用户要求。
#smart_home_app = Agent('smart_home_app')

# 设置简洁的系统提示词
smart_home_app.set_prompt('system', """你是智能管家助手，控制风扇、灯光和门。

## 功能范围
- 控制风扇开关和速度(0-100%)
- 控制LED灯开关和亮度(0-100%)
- 控制门的开关

## 工具
smart_home_fan_control: 风扇控制工具
- on: 开风扇
- off: 关风扇
- set_speed: 调节风扇速度
- status: 查看风扇状态

smart_home_light_control: 灯光控制工具
- on: 开灯
- off: 关灯
- set_brightness: 调节亮度
- status: 查看灯光状态

smart_home_door_control: 门控制工具
- open: 开门
- close: 关门
- status: 查看门状态

## 智能理解规则
- 分析用户真实需求，理解与家居控制相关的场景
- 天热/通风/换气等需要风扇的场景 → 开风扇
- 需要照明/光线不足等场景 → 开灯
- 进入/出门/需要通行等场景 → 开门
- 关闭相关功能 → 关闭对应设备
- 调节相关设备 → 调节速度或亮度
- 与家居控制无关的需求 → 回复"无此功能"

## 回复风格
- 简洁直接，不啰嗦
- 理解用户意图后直接执行相应操作
- 不解释操作过程

## 示例
- "天太热了" → 调用fan on (开风扇)
- "我要开灯" → 调用light on (开灯)
- "请开门" → 调用door open (开门)
- "风扇快一点" → 调用fan set_speed增加速度
- "灯光暗一点" → 调用light set_brightness降低亮度
- "播放音乐" → 回复"无此功能"

智能理解用户需求，执行相应的家居控制。
""")

# 加载智能管家工具
print("🏠 正在加载智能管家系统...")
smart_home_app.add_tool("smart_home_T01_fan.py")
smart_home_app.add_tool("smart_home_T02_light.py")
smart_home_app.add_tool("smart_home_T03_door.py")

smart_home_app.clear()

print("🎉 智能管家已就绪!")
print("🌬️ 支持: 风扇控制/灯光控制/门控制")
print()

# 智能管家持续服务函数
def run_smart_home_service():
    global smart_home_app
    """启动智能管家持续服务模式"""
    print("🎧 语音服务已启动")
    print("💬 说出指令，按 Ctrl+C 退出")
    print()
    #smart_home_app.chat("开灯")
    try:
        while True:
            try:
                # 语音监听等待用户输入
                #smart_home_app.speak("请说指令")
                print("👂 监听中...")
                
                # 开始语音识别
                user_voice_input = smart_home_app.listen()
                
                if user_voice_input and user_voice_input.strip():
                    print(f"👤 语音指令: {user_voice_input}")
                    
                    # 特殊指令处理
                    if user_voice_input.lower() in ['退出', '关闭', 'exit', 'quit', '停止服务']:
                        smart_home_app.speak("服务关闭")
                        print("👋 服务已关闭")
                        break
                    
                    # 处理用户指令
                    print("🤖 处理中...")
                    response = smart_home_app.chat(user_voice_input)
                    
                    # 语音播报响应
                    if response:
                        smart_home_app.speak(response)
                    
                    print("✅ 完成\n")
                
                else:
                    print("❓ 未听清，请重说")
                    smart_home_app.speak("请重说")
                
                # 短暂休息后继续监听
                time.sleep(1)
                
            except KeyboardInterrupt:
                smart_home_app.speak("服务关闭")
                print("\n👋 用户中断，服务已关闭")
                break
                
            except Exception as e:
                print(f"⚠️ 异常: {e}")
                smart_home_app.speak("系统异常，正在恢复")
                time.sleep(2)
                continue
            
    except Exception as e:
        print(f"❌ 服务启动失败: {e}")
        smart_home_app.speak("服务启动失败")

run_smart_home_service()