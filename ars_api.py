#!/usr/bin/env python3
"""
ASR 语音识别模块 (耳朵) - 实时识别版 (使用阿里云 NLS SDK)
功能：调用本机/蓝牙麦克风录音 -> 实时流式识别 (SDK) -> 返回纯文本
"""

import pyaudio
import threading
import queue
import time
import nls # 导入阿里云 NLS SDK

# ================= 阿里云实时语音识别 SDK 配置 =================
# 请替换为你自己的阿里云账号信息
APPKEY = "nmxAhyFvtY4dQHz0"  # 你的 AppKey
TOKEN = "be4f563e545a4017aeca6e23ba68ed09"  # 你的 Access Token (请替换为实际获取的Token)
# 如何获取Token: 参考 https://help.aliyun.com/zh/isi/getting-started/obtain-an-access-token

# ================= 录音配置 =================
# PyAudio 配置
FORMAT = pyaudio.paInt16
CHANNELS = 1
RATE = 16000
CHUNK = 6400  # 每次读取的帧数，6400帧约0.4秒 (16000hz * 0.4s)，适合流式发送

class AliyunRealTimeASR_SDK:
    def __init__(self):
        self.appkey = APPKEY
        self.token = TOKEN
        self.url = "wss://nls-gateway-cn-shanghai.aliyuncs.com/ws/v1" # 默认上海节点
        
        self.audio_queue = queue.Queue()
        self.result_queue = queue.Queue()
        self.is_listening = False
        self.is_recording = False
        self.stream = None
        self.pyaudio_instance = None
        self.transcriber = None # SDK 实例

    def _on_start(self, message, *args):
        print(f"[ASR SDK] 连接已就绪: {message}")

    def _on_sentence_begin(self, message, *args):
        print("[ASR SDK] 检测到语音开始。")

    def _on_sentence_end(self, message, *args):
        print("[ASR SDK] 检测到语音结束。")

    def _on_result_changed(self, message, *args):
        # 实时显示中间结果
        print(f"[ASR SDK] 🔄 识别中: {message}", end='\r')

    def _on_completed(self, message, *args):
        print(f"\n[ASR SDK] 识别完成: {message}")
        try:
            import json
            # 假设 message 是 JSON 字符串，提取 result
            data = json.loads(message)
            result_text = data.get("payload", {}).get("result", "")
            print(f"[ASR SDK] ✅ 最终识别结果: {result_text}")
            self.result_queue.put(result_text)
        except json.JSONDecodeError:
            print("[ASR SDK] 解析最终结果失败，返回原始消息。")
            self.result_queue.put(message)
        except Exception as e:
            print(f"[ASR SDK] 处理最终结果时出错: {e}")
            self.result_queue.put("")
        finally:
            self.stop_listening()

    def _on_error(self, message, *args):
        print(f"[ASR SDK] 出现错误: {message}, args: {args}")
        self.result_queue.put(None) # 发送错误信号
        self.stop_listening()

    def _on_close(self, *args):
        print("[ASR SDK] WebSocket 连接已关闭。")

    def start_listening(self):
        """启动录音和SDK连接"""
        if self.is_listening:
            print("[ASR SDK] 正在监听中，请勿重复启动。")
            return

        print("\n[ASR SDK] 🎤 正在启动实时语音识别 (SDK)...")
        
        # 检查Token是否已配置
        if self.token == "YOUR_TOKEN_HERE":
            print("[ASR SDK] ❌ 请先在 ars_api.py 顶部填入你的阿里云 TOKEN。")
            print("[ASR SDK]     请参考文档获取TOKEN: https://help.aliyun.com/zh/isi/getting-started/obtain-an-access-token")
            return

        self.is_listening = True
        
        # 1. 初始化SDK实例
        try:
            self.transcriber = nls.NlsSpeechTranscriber(
                url=self.url,
                token=self.token,
                appkey=self.appkey,
                on_start=self._on_start,
                on_sentence_begin=self._on_sentence_begin,
                on_sentence_end=self._on_sentence_end,
                on_result_changed=self._on_result_changed,
                on_completed=self._on_completed,
                on_error=self._on_error,
                on_close=self._on_close,
                callback_args=[]
            )
        except Exception as e:
            print(f"[ASR SDK] 初始化 SDK 失败: {e}")
            self.is_listening = False
            return

        # 2. 启动SDK连接
        try:
            success = self.transcriber.start(
                aformat="pcm", # 音频格式
                sample_rate=RATE, # 采样率
                ch=CHANNELS, # 声道数
                enable_intermediate_result=True, # 开启中间结果
                enable_punctuation_prediction=True, # 开启标点预测
                enable_inverse_text_normalization=True # 开启ITN
            )
            if not success:
                print("[ASR SDK] 启动识别会话失败。")
                self.is_listening = False
                return
        except Exception as e:
            print(f"[ASR SDK] 启动识别会话时出错: {e}")
            self.is_listening = False
            return

        # 3. 初始化PyAudio录音
        try:
            self.pyaudio_instance = pyaudio.PyAudio()
            self.stream = self.pyaudio_instance.open(
                format=FORMAT,
                channels=CHANNELS,
                rate=RATE,
                input=True,
                frames_per_buffer=CHUNK
            )
        except Exception as e:
            print(f"[ASR SDK] 初始化录音失败: {e}")
            self.transcriber.shutdown() # 启动失败也要关闭SDK
            self.is_listening = False
            return

        self.is_recording = True
        print("[ASR SDK] 🟢 开始录音！请说话...")

        # 4. 启动录音线程
        record_thread = threading.Thread(target=self._record_and_send_audio)
        record_thread.daemon = True
        record_thread.start()

    def _record_and_send_audio(self):
        """内部录音函数，将音频数据读取并发送给SDK"""
        while self.is_recording:
            try:
                # 从麦克风读取音频数据
                data = self.stream.read(CHUNK, exception_on_overflow=False)
                # 将音频数据发送给SDK
                if not self.transcriber.send_audio(data):
                    print("[ASR SDK] 发送音频数据失败，停止录音。")
                    self.is_recording = False
                    break
            except Exception as e:
                print(f"[ASR SDK] 录音或发送数据时出错: {e}")
                self.is_recording = False
                break

    def stop_listening(self):
        """停止录音和SDK连接"""
        if not self.is_listening:
            return
            
        print("\n[ASR SDK] 🛑 停止录音和识别...")
        self.is_recording = False
        self.is_listening = False
        
        # 停止录音流
        if self.stream:
            self.stream.stop_stream()
            self.stream.close()
        if self.pyaudio_instance:
            self.pyaudio_instance.terminate()
        
        # 停止SDK识别 (这会触发 on_completed 或 on_error)
        if self.transcriber:
            try:
                # 使用 stop 会等待服务端最终结果返回
                # self.transcriber.stop(timeout=10) 
                # 使用 shutdown 强行关闭连接，适用于我们等待队列的逻辑
                self.transcriber.shutdown()
            except Exception as e:
                print(f"[ASR SDK] 关闭 transcriber 时出错: {e}")

    def get_result(self):
        """获取识别结果，阻塞直到有结果或连接关闭"""
        try:
            result = self.result_queue.get(timeout=30) # 设置30秒超时
            return result if result is not None else ""
        except queue.Empty:
            print("[ASR SDK] ⚠️ 获取识别结果超时。")
            return ""

def listen_and_recognize():
    """
    监听麦克风并返回识别到的文本。
    这个函数与 main.py 的调用方式完全兼容。
    """
    asr_engine = AliyunRealTimeASR_SDK()
    
    try:
        asr_engine.start_listening()
        # 等待识别结果
        text = asr_engine.get_result()
        
        if text:
            print(f"[ASR SDK] ✅ 识别成功: {text}")
        else:
            print("[ASR SDK] ❌ 识别失败或超时。")
        
        return text
    
    except KeyboardInterrupt:
        print("\n[ASR SDK] 识别被用户中断。")
        asr_engine.stop_listening()
        return ""
    except Exception as e:
        print(f"[ASR SDK] 发生未知错误: {e}")
        asr_engine.stop_listening()
        return ""
    finally:
        # 确保资源被清理
        asr_engine.stop_listening()


# ========== 独立测试模块 ==========
if __name__ == "__main__":
    print("=== ASR SDK 实时识别模块独立测试 ===")
    print("提示：请先配置好阿里云 TOKEN。")
    print("提示：说话结束后，等待几秒钟以接收最终识别结果。")
    
    result = listen_and_recognize()
    if result:
        print(f"\n最终返回给大模型的数据: '{result}'")
    print("=== 测试结束 ===")