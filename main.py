import time
import llm_Deepseek
import tts_api
from input_interface import InputManager

def main():
    print("=== 正在启动智能管家（ASR -> LLM -> TTS）===")
    input_manager = InputManager(mode='asr')
    
    # 获取动态环境信息（当前北京时间和天气）
    date_info, current_time, time_period = llm_Deepseek.get_current_time_info()
    weather_info = llm_Deepseek.get_current_weather()
    print(f"[系统] 当前时间: {date_info} {current_time}（{time_period}）")
    print(f"[系统] 深圳天气: {weather_info}\n")
    
    # 生成动态系统提示词（包含实时时间和天气）
    system_prompt = llm_Deepseek.create_system_prompt(date_info, current_time, time_period, weather_info)
    
    # 设定管家的人设上下文（现在包含动态时间信息）
    messages = [
        {"role": "system", "content": system_prompt}
    ]
    
    print("\n💡 提示：运行过程中可按 Ctrl+C 退出程序。")
    print("开始进入语音对话模式...\n")

    pending_user_text = ""
    
    try:
        while True:
            # 1. 统一输入层：优先消费被打断时留下的文本，否则继续监听麦克风
            if pending_user_text:
                user_text = pending_user_text
                pending_user_text = ""
            else:
                user_text = input_manager.get_user_input()
            
            # 如果没听到或者抛错了，就跳过这一轮继续监听
            if not user_text:
                continue

            # 若用户在播报中开口，则立即打断当前语音播放
            if tts_api.is_speaking():
                print("[系统] 检测到打断输入，正在停止当前播报...")
                tts_api.stop_speaking(wait=False)
                
            # 将用户最新意图加入历史对话记录
            messages.append({"role": "user", "content": user_text})
            
            # 2. 将文字发给 LLM 思考回答
            print("[管家] 正在思考...")
            reply_text = llm_Deepseek.call_deepseek_api(messages)
            
            # 将模型的回答也加入历史，保持多轮记忆
            messages.append({"role": "assistant", "content": reply_text})
            print(f"[管家回复]: {reply_text}")
            
            # 3. 异步播报：播报期间继续监听，支持用户说话打断
            tts_api.speak_async(reply_text)
            while tts_api.is_speaking():
                interrupt_text = input_manager.get_user_input()
                if interrupt_text:
                    print("[系统] 已打断当前播报，进入下一轮对话。")
                    tts_api.stop_speaking(wait=False)
                    pending_user_text = interrupt_text
                    break
                time.sleep(0.05)
            
    except KeyboardInterrupt:
        tts_api.stop_speaking(wait=False)
        print("\n\n[系统] 已手动退出，再见！")

if __name__ == "__main__":
    main()

