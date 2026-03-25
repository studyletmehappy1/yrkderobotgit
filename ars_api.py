#!/usr/bin/env python3
"""
ASR 语音识别模块 (耳朵)
功能：调用本机/蓝牙麦克风录音 -> 自动截断 -> 调用免费 API -> 返回纯文本
"""

import speech_recognition as sr

def listen_and_recognize():
    """
    监听麦克风并返回识别到的文本。
    """
    # 初始化语音识别器
    recognizer = sr.Recognizer()

    # sr.Microphone() 会自动抓取 Windows 系统的“默认录音设备”
    # 只要连了蓝牙耳机并设为默认，这里就会自动通过蓝牙收音
    with sr.Microphone() as source:
        print("\n[耳朵] 🎤 正在校准环境底噪，请保持安静 1 秒钟...")
        # 自动适应当前环境底噪，防止把风扇声当成说话声
        recognizer.adjust_for_ambient_noise(source, duration=1.0)
        
        print("[耳朵] 🟢 校准完成！主人，我在听，请说话...")
        try:
            # 开始录音：
            # timeout=5: 如果 5 秒内没检测到说话的声音，就放弃
            # phrase_time_limit=15: 限制一句话最多录 15 秒，防止一直录下去
            audio = recognizer.listen(source, timeout=5, phrase_time_limit=15)
            
            print("[耳朵] ⏳ 录音结束，正在请求云端翻译...")
            
            # 调用内置的纯免费 Google Web API (识别语言设置为简体中文)
            text = recognizer.recognize_google(audio, language='zh-CN')
            print(f"[耳朵] ✅ 听懂了: {text}")
            
            return text
            
        except sr.WaitTimeoutError:
            print("[耳朵] ⚠️ 等了半天没听到声音哦。")
            return ""
        except sr.UnknownValueError:
            print("[耳朵] ❓ 刚才的话没听清或者只有杂音，能再说一遍吗？")
            return ""
        except sr.RequestError as e:
            print(f"[耳朵] ❌ 网络请求失败，请检查网络是否通畅: {e}")
            return ""
        except Exception as e:
            print(f"[耳朵] ❌ 发生未知错误: {e}")
            return ""

# ========== 独立测试模块 ==========
if __name__ == "__main__":
    print("=== ASR 模块独立测试 ===")
    print("提示：如果你戴着蓝牙耳机，请确保它是 Windows 默认录音设备。")
    result = listen_and_recognize()
    if result:
        print(f"\n最终返回给大模型的数据: '{result}'")
    print("=== 测试结束 ===")