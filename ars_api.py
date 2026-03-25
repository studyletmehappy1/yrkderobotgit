#!/usr/bin/env python3
"""
ASR 语音识别模块 (耳朵)
功能：调用本机/蓝牙麦克风录音 -> 自动截断 -> 调用免费 API -> 返回纯文本
"""

import speech_recognition as sr
import requests
import json

# ================= 百度短语音识别 API 配置 =================
# 请前往百度智能云 (console.bce.baidu.com) -> 产品服务 -> 语音技术 -> 创建应用
# 在应用列表可以获取以下两个 Key。个人认证每日免费额度足够普通测试。
BAIDU_API_KEY = "填写你的_API_KEY_在这里"
BAIDU_SECRET_KEY = "填写你的_SECRET_KEY_在这里"

def recognize_baidu(audio):
    """调用百度短语音识别 REST API (纯PCM直传版本)"""
    if BAIDU_API_KEY.startswith("填写你的"):
        print("[耳朵] ❌ 请先在 ars_api.py 顶部填入你的百度 API_KEY 和 SECRET_KEY")
        return ""

    # 第一步：获取针对当前会话的 Access Token
    token_url = f"https://aip.baidubce.com/oauth/2.0/token?grant_type=client_credentials&client_id={BAIDU_API_KEY}&client_secret={BAIDU_SECRET_KEY}"
    try:
        token_response = requests.post(token_url, headers={'Content-Type': 'application/json'}, timeout=5)
        token = token_response.json().get("access_token", "")
        if not token:
            print(f"[耳朵] ❌ 获取百度鉴权Token失败，请检查 Key 是否正确，或是否开通了语音技术服务。")
            return ""
    except Exception as e:
        print(f"[耳朵] ❌ 请求百度鉴权接口网络异常: {e}")
        return ""

    # 第二步：将语音转码发给百度 ASR 识别服务器
    # dev_pid=1537 代表普通话输入
    asr_url = f"http://vop.baidu.com/server_api?dev_pid=1537&cuid=my_smart_home&token={token}"
    
    # 将录音数据转换为百度强制要求的标准格式数据：16kHz采样率, 16bit位深, 单声道, PCM编码
    pcm_data = audio.get_raw_data(convert_rate=16000, convert_width=2)
    
    headers = {
        'Content-Type': 'audio/pcm;rate=16000',
        'Accept': 'application/json'
    }
    
    try:
        asr_response = requests.post(asr_url, headers=headers, data=pcm_data, timeout=10)
        result = asr_response.json()
        
        # 返回 JSON 中 err_no 为 0 代表识别成功
        if result.get("err_no") == 0:
            return result.get("result", [""])[0] 
        else:
            print(f"[耳朵] ❌ 百度识别出错 (错误码:{result.get('err_no')}): {result.get('err_msg')}")
            return ""
    except Exception as e:
        print(f"[耳朵] ❌ 请求百度ASR接口网络异常: {e}")
        return ""

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
            
            text = ""
            
            # 策略：双端降级容灾机制
            # 优先尝试免费且带强力自适应的 Google API (需要网络环境允许)
            try:
                print("[耳朵] 正在尝试连接 Google ASR...")
                text = recognizer.recognize_google(audio, language='zh-CN')
            except Exception as e:
                print(f"[耳朵] ⚠️ Google API 访问失败 ({e})，立即切换至百度国内通道...")
                text = ""
            
            # 如果 Google 失败或者返回空，作为备用退线路由，启用百度 ASR
            if not text:
                print("[耳朵] 正在使用百度 ASR 兜底识别...")
                text = recognize_baidu(audio)
            
            if text:
                print(f"[耳朵] ✅ 听懂了: {text}")
                return text
            else:
                return ""
            
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