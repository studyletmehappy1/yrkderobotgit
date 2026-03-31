import time
import asr_api
import llm_Deepseek
import tts_api
from input_interface import InputManager

def main():
    print("=== 正在启动智能管家究极形态 (真·多线程打断架构) ===")
    
    input_manager = InputManager(mode='asr')
    
    # 提前唤醒后台耳朵，让它开始静默监听
    input_manager.start_background_listening()
    
    # 获取时间与天气 (调用你在 llm_Deepseek.py 里的函数)
    date_info, current_time, time_period = llm_Deepseek.get_current_time_info()
    weather_info = llm_Deepseek.get_current_weather()
    system_prompt = llm_Deepseek.create_system_prompt(date_info, current_time, time_period, weather_info)
    
    messages = [{"role": "system", "content": system_prompt}]
    
    print("\n💡 提示：运行过程中可按 Ctrl+C 退出程序。")
    print("开始进入语音对话模式...\n")
    
    try:
        while True:
            # 1. 【核心动作】：在等待主人下达新指令前，通过接口把上一轮的打断警报器解除！
            input_manager.clear_interrupt()
            
            # 2. 阻塞在这里，静静等待后台耳朵把听懂的话传过来
            user_text = input_manager.get_user_input()
            
            if not user_text:
                continue
                
            if user_text.lower() in ['退出', 'exit', 'quit', 'q']:
                print("\n[系统] 收到退出指令，再见！")
                break
                
            messages.append({"role": "user", "content": user_text})
            
            # 3. 大脑思考
            print("[管家] 正在思考...")
            reply_text = llm_Deepseek.call_deepseek_api(messages)
            
            # 滑动窗口截断机制（防止Token爆炸）
            messages.append({"role": "assistant", "content": reply_text})
            if len(messages) > 21:  
                messages = [messages[0]] + messages[-20:]
                
            print(f"[管家回复]: {reply_text}")
            
            # 4. 把刚刚解除的警报器，通过接口拿出来塞进嘴巴里！
            tts_api.speak(reply_text, interrupt_flag=input_manager.get_interrupt_flag())
            
    except KeyboardInterrupt:
        print("\n\n[系统] 已手动退出，再见！")

if __name__ == "__main__":
    main()