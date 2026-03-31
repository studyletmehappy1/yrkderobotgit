import time
import asr_api   # 注意：确保你的文件名拼写就是 ars_api.py
import llm_Deepseek
import tts_api
import shared_state # 引入全局状态机

def main():
    print("=== 正在启动智能管家（支持'小艺小艺'随时打断版）===")
    
    # 🌟 进阶优化：调用你 llm_Deepseek.py 里写的动态环境感知！
    print("[系统] 正在获取北京时间与深圳天气...")
    date_info, current_time, time_period = llm_Deepseek.get_current_time_info()
    weather_info = llm_Deepseek.get_current_weather()
    system_prompt = llm_Deepseek.create_system_prompt(date_info, current_time, time_period, weather_info)
    
    # 初始化带动态上下文的记忆列表
    messages = [
        {"role": "system", "content": system_prompt}
    ]
    
    # 1. 开启后台永远运行的耳朵
    ars_api.start_background_listening()
    
    print("\n💡 提示：运行过程中可按 Ctrl+C 退出程序。")
    print("当前状态：💤 待机中，请随时喊“小艺小艺”开始对话...\n")
    
    try:
        while True:
            # 2. 从队列里取用户的指令（如果没有就一直睡眠循环，不占用CPU）
            if not shared_state.text_queue.empty():
                user_text = shared_state.text_queue.get()
                
                messages.append({"role": "user", "content": user_text})
                
                # 🔒 核心修改：拿到文本的瞬间，立刻上锁进入 THINKING 状态！
                # 防止在调用 API 网络等待的这几秒钟内被环境杂音误打断
                shared_state.current_state = shared_state.RobotState.THINKING
                
                # 3. 开始思考
                print("[管家] 正在思考...")
                reply_text = llm_Deepseek.call_deepseek_api(messages)
                
                messages.append({"role": "assistant", "content": reply_text})
                print(f"[管家回复]: {reply_text}")
                
                # 🪟 引入滑动窗口截断机制（防止聊久了 Token 爆炸报错）
                if len(messages) > 21:  
                    messages = [messages[0]] + messages[-20:]
                
                # 4. 准备说话前，清理历史打断标志，并切入 SPEAKING 状态
                shared_state.interrupt_flag = False
                shared_state.current_state = shared_state.RobotState.SPEAKING
                
                # 5. 播放语音（播放期间如果耳朵听到“小艺”，会触发 interrupt_flag 急刹车）
                tts_api.speak(reply_text)
                
                # 6. 播完后的状态收尾
                if not shared_state.interrupt_flag:
                    # 如果没有被打断，平稳回到待机状态
                    shared_state.current_state = shared_state.RobotState.IDLE
                    print("\n[系统] 💤 播报完毕，进入待机，可再次喊'小艺'。")
            else:
                time.sleep(0.1)
                
    except KeyboardInterrupt:
        print("\n\n[系统] 已手动退出，再见！")

if __name__ == "__main__":
    main()