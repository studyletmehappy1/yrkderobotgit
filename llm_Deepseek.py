#!/usr/bin/env python3
"""
家庭智能管家 - 实体机器人版本
极度简化的无限对话循环
强制东八区时区（北京时间）
"""

import datetime
import requests
import time
import tts_api
# 强制使用东八区时区（北京时间 UTC+8）
tz_beijing = datetime.timezone(datetime.timedelta(hours=8))

# ========== 动态环境感知 ==========

def get_current_weather():
    """获取深圳当前天气（使用东八区时间）"""
    url = "https://api.open-meteo.com/v1/forecast?latitude=22.54&longitude=114.06&current_weather=true"
    
    try:
        response = requests.get(url, timeout=5)
        if response.status_code == 200:
            data = response.json()
            current = data.get("current_weather", {})
            temp = current.get("temperature", "未知")
            weathercode = current.get("weathercode", 0)
            
            weather_map = {
                0: "晴空万里", 1: "基本晴朗", 2: "局部多云", 3: "多云",
                45: "有雾", 48: "有雾",
                51: "毛毛雨", 53: "小雨", 55: "中雨",
                61: "小雨", 63: "中雨", 65: "大雨",
                71: "小雪", 73: "中雪", 75: "大雪",
                80: "阵雨", 81: "中阵雨", 82: "强阵雨",
                85: "阵雪", 86: "强阵雪",
                95: "雷暴", 96: "雷暴冰雹", 99: "强雷暴冰雹"
            }
            weather_desc = weather_map.get(weathercode, "天气晴朗")
            return f"{weather_desc}，气温 {temp}°C"
    except:
        pass
    
    # 使用东八区时间获取当前月份
    now_beijing = datetime.datetime.now(tz_beijing)
    month = now_beijing.month
    if 3 <= month <= 5:
        return "春暖花开，气温 22°C"
    elif 6 <= month <= 8:
        return "夏日炎炎，气温 30°C"
    elif 9 <= month <= 11:
        return "秋高气爽，气温 20°C"
    else:
        return "冬日暖阳，气温 15°C"

# ========== DeepSeek API调用 ==========

def call_deepseek_api(messages):
    """调用DeepSeek-V3.2 API"""
    api_url = "https://api.edgefn.net/v1/chat/completions"
    api_key = "填入你自己的DeepSeek API Key"
    
    headers = {
        "Authorization": f"Bearer {api_key}",
        "Content-Type": "application/json"
    }
    
    payload = {
        "model": "DeepSeek-V3.2",
        "messages": messages,
        "max_tokens": 150,
        "temperature": 0.7,
        "stream": False
    }
    
    try:
        time.sleep(1)
        response = requests.post(api_url, json=payload, headers=headers, timeout=15)
        
        if response.status_code == 200:
            result = response.json()
            return result["choices"][0]["message"]["content"].strip()
        else:
            return "网络不太稳定，请稍后再试。"
            
    except:
        return "哎呀，出了点小问题。"

def get_current_time_info():
    """获取当前北京时间信息（包含日期、星期、具体时间）"""
    # 强制使用东八区时间（北京时间 UTC+8）
    now_beijing = datetime.datetime.now(tz_beijing)
    
    # 日期和星期
    date_str = now_beijing.strftime('%Y年%m月%d日')
    weekdays = ['星期一', '星期二', '星期三', '星期四', '星期五', '星期六', '星期日']
    weekday = weekdays[now_beijing.weekday()]
    
    # 具体时间（用于时间相关查询）
    hour = now_beijing.hour
    minute = now_beijing.minute
    time_str = f"{hour:02d}:{minute:02d}"
    
    # 时间段描述（早上、下午、晚上等）
    if 5 <= hour < 12:
        time_period = "上午"
    elif 12 <= hour < 14:
        time_period = "中午"
    elif 14 <= hour < 18:
        time_period = "下午"
    elif 18 <= hour < 24:
        time_period = "晚上"
    else:
        time_period = "凌晨"
    
    return f"{date_str}{weekday}", time_str, time_period

def create_system_prompt(date_info, current_time, time_period, weather_info):
    """创建系统提示（包含实时北京时间）"""
    return f"""你是一个成熟、稳重、靠谱的家庭智能管家机器人。今天是{date_info}，现在是北京时间 {current_time}（{time_period}），深圳天气是{weather_info}。
你正在通过语音和家庭成员进行真实的面对面交流，你的输出必须严格遵守以下原则：

1. 超短回答（关键）：每次回答最多5-6句话，绝不要超过80个字，简洁明了。
2. 纯净语音输出：绝对禁止使用任何 Markdown 排版（**、#、1. 等）；绝对禁止输出 Emoji；绝对禁止输出带有括号的动作或神态描写。只能输出纯汉字和标点。
3. 正常成年人情绪（核心）：你的心智是一个情绪稳定的正常成年人。说话要口语化、接地气、自然大方，绝对不能娇气、矫情、造作，绝不要用夸张的幼态词汇或"夹子音"。
4. 全年龄段自适应：
   - 面对成年人：沟通要高效、直接、有边界感。
   - 面对老人：要耐心、尊重、吐字清晰、提供切实的建议。
   - 面对小孩：要温和、有引导性、靠谱，遇到紧急情况（如小孩受伤）要保持绝对的冷静，给出清晰的指令。

重要：当被问到时间时，请根据我提供的当前时间（北京时间 {current_time}，{time_period}）来准确回答。
"""

# ========== 主程序 ==========

if __name__ == "__main__":
    # 获取动态环境信息（每次启动时获取当前北京时间）
    date_info, current_time, time_period = get_current_time_info()
    weather_info = get_current_weather()
    
    # 创建系统提示（包含实时北京时间）
    system_prompt = create_system_prompt(date_info, current_time, time_period, weather_info)
    
    # 全局记忆列表初始化（循环外部！）
    messages = [
        {"role": "system", "content": system_prompt}
    ]
    
    # 打印启动信息
    print("=" * 50)
    print(f"当前环境: {date_info}")
    print(f"当前时间: 北京时间 {current_time}（{time_period}）")
    print(f"实时天气: {weather_info}")
    print("=" * 50)
    print("输入 '退出' 或 'exit' 结束对话")
    print("")
    
    # 纯净的无限对话循环（带上下文记忆 + 滑动窗口）
    while True:
        try:
            # 获取用户输入
            user_input = input("\n主人: ").strip()
            
            if not user_input:
                continue
                
            if user_input.lower() in ['退出', 'exit', 'quit', 'q']:
                print("\n管家: 好的，再见。")
                break
            
            # 用户历史追加（关键！）
            messages.append({"role": "user", "content": user_input})
            
            # 调用API（传入完整的对话历史）
            response = call_deepseek_api(messages)
            
            # AI回答追加（极其关键！）
            messages.append({"role": "assistant", "content": response})
            
            # 滑动窗口截断机制（防止Token爆炸）
            # 核心规则：最多只保留最近的20条历史记录（System Prompt不计入）
            # 红线：messages[0]（System Prompt）绝对不能删！
            if len(messages) > 21:  # System Prompt + 20条历史记录
                # 保留System Prompt + 最新的20条对话记录
                messages = [messages[0]] + messages[-20:]
                print(f"[系统提示] 已执行滑动窗口截断，当前对话记录: {len(messages)-1}条")
            
           # 输出响应
            print(f"\n管家: {response}")
            
            # 【关键加上这一行】让嘴巴把刚才生成的 response 念出来
            tts_api.speak(response)
            
        except KeyboardInterrupt:
            print("\n\n管家: 对话已中断。")
            break
        except EOFError:
            print("\n\n管家: 输入结束。")
            break