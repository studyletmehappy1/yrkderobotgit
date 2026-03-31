#!/usr/bin/env python3
"""
ASR 语音识别模块 (耳朵) - 究极后台打断版 (VAD + 阿里云 NLS SDK)
功能：后台常驻静默监听 -> VAD秒级响应 -> 拉响打断警报 -> 连线阿里云 -> 返回识别文本
"""

import pyaudio
import threading
import queue
import time
import json
import nls
import os
import numpy as np
import torch
import atexit

# ================= 阿里云实时语音识别 SDK 配置 =================
APPKEY = "nmxAhyFvtY4dQHz0"  # 你的 AppKey
TOKEN = "be4f563e545a4017aeca6e23ba68ed09"  # 你的 Access Token (务必确保是最新的)

# ================= 录音与 VAD 配置 =================
FORMAT = pyaudio.paInt16
CHANNELS = 1
RATE = 16000
# 【关键修改】Silero VAD 强制要求帧数必须是 512, 1024, 或 1536
CHUNK = 1536

# --- 全局单例与通信枢纽 ---
_asr_singleton = None
_asr_lock = threading.Lock()
_recognition_results = queue.Queue(maxsize=10) # 存放最终识别的句子

# 【核心：打断警报器】专门用来通知主线程和 TTS 停止播放
interrupt_flag = threading.Event()

def get_global_asr_engine():
    """获取全局唯一的 ASR 引擎实例，并启动后台监听"""
    global _asr_singleton
    with _asr_lock:
        if _asr_singleton is None:
            _asr_singleton = SileroVADRealTimeASR_Background()
            _asr_singleton.start_listening_in_background()
            atexit.register(stop_global_asr_engine)
        return _asr_singleton

def stop_global_asr_engine():
    """程序退出时释放资源"""
    global _asr_singleton
    if _asr_singleton:
        _asr_singleton.stop_listening()
        _asr_singleton = None

class SileroVAD:
    """本地语音活动检测器（纯 JIT 模式）。"""
    def __init__(self, threshold=0.5, model_path="silero_vad.jit"):
        self.threshold = threshold
        self.model = None

        base_dir = os.path.dirname(os.path.abspath(__file__))
        jit_abs = model_path if os.path.isabs(model_path) else os.path.join(base_dir, model_path)

        print(f"[VAD] 正在从本地加载离线 JIT 模型: {jit_abs}")

        if not os.path.exists(jit_abs):
            raise FileNotFoundError(
                "❌ 找不到 silero_vad.jit。请下载后放到项目根目录，"
                "或在 SileroVAD(model_path=...) 里传入绝对路径。"
            )

        self.model = torch.jit.load(jit_abs, map_location="cpu")
        self.model.eval()
        torch.set_num_threads(1)

    def is_speech(self, audio_chunk_bytes):
        audio_int16 = np.frombuffer(audio_chunk_bytes, dtype=np.int16)
        audio_float32 = audio_int16.astype(np.float32) / 32768.0
        tensor_chunk = torch.from_numpy(audio_float32)
        return self.model(tensor_chunk, RATE).item() > self.threshold

class AliyunRealTimeASR_SDK:
    """阿里云连接器 (只负责把 VAD 喂过来的声音发上云)"""
    def __init__(self, result_callback):
        self.appkey = APPKEY
        self.token = TOKEN
        self.url = "wss://nls-gateway-cn-shanghai.aliyuncs.com/ws/v1"
        self.result_callback = result_callback
        self.transcriber = None

    def _on_result_changed(self, message, *args):
        pass # 屏蔽中间结果疯狂刷屏，保持控制台清爽

    def _on_completed(self, message, *args):
        try:
            data = json.loads(message)
            result_text = data.get("payload", {}).get("result", "")
            self.result_callback(result_text)
        except:
            self.result_callback("")

    def _on_error(self, message, *args):
        print(f"\n[阿里云] ❌ 出现错误: {message}")
        self.result_callback("")

    def start_connection(self):
        self.transcriber = nls.NlsSpeechTranscriber(
            url=self.url, token=self.token, appkey=self.appkey,
            on_result_changed=self._on_result_changed,
            on_completed=self._on_completed, on_error=self._on_error,
            callback_args=[]
        )
        self.transcriber.start(
            aformat="pcm", sample_rate=RATE, ch=CHANNELS,
            enable_intermediate_result=True,
            enable_punctuation_prediction=True,
            enable_inverse_text_normalization=True
        )

    def send_audio(self, data):
        if self.transcriber:
            self.transcriber.send_audio(data)

    def stop_connection(self):
        if self.transcriber:
            self.transcriber.stop()
            self.transcriber.shutdown()

class SileroVADRealTimeASR_Background:
    """后台监听器类"""
    def __init__(self):
        self.is_listening = False
        self.background_thread = None
        self.vad_detector = None
        self.stream = None
        self.pyaudio_instance = None
        self.current_asr_engine = None

    def _process_recognition_result(self, text):
        if text.strip():
            print(f"\n[ASR 后台] ✅ 最终听懂: {text}")
            try:
                _recognition_results.put_nowait(text)
            except queue.Full:
                pass

    def start_listening_in_background(self):
        if self.is_listening: return
        self.is_listening = True
        self.vad_detector = SileroVAD(threshold=0.5)
        self.background_thread = threading.Thread(target=self._run_vad_detection_loop, daemon=True)
        self.background_thread.start()

    def _run_vad_detection_loop(self):
        self.pyaudio_instance = pyaudio.PyAudio()
        self.stream = self.pyaudio_instance.open(
            format=FORMAT, channels=CHANNELS, rate=RATE,
            input=True, frames_per_buffer=CHUNK
        )
        print("[ASR 后台] 🟢 麦克风已开启，7x24小时全天候静默监听...")

        state = "WAITING"
        silence_chunks = 0
        max_silence_chunks = 10 # 约1秒静音判定为说完了一句话

        try:
            while self.is_listening:
                audio_data = self.stream.read(CHUNK, exception_on_overflow=False)
                has_speech = self.vad_detector.is_speech(audio_data)

                if state == "WAITING":
                    if has_speech:
                        # ⚡⚡⚡ 究极核心：听到人声的瞬间，拉响打断警报！通知 TTS 闭嘴！
                        interrupt_flag.set()
                        print("\n[VAD] ⚡ 检测到人声！警报已拉响！连线阿里云...")
                        self.current_asr_engine = AliyunRealTimeASR_SDK(self._process_recognition_result)
                        self.current_asr_engine.start_connection()
                        self.current_asr_engine.send_audio(audio_data)
                        state = "RECORDING"
                        silence_chunks = 0

                elif state == "RECORDING":
                    self.current_asr_engine.send_audio(audio_data)
                    
                    if not has_speech:
                        silence_chunks += 1
                    else:
                        silence_chunks = 0

                    # 连续1秒没有声音，判定说话结束
                    if silence_chunks > max_silence_chunks:
                        print("[VAD] 🛑 判定说话结束！立刻切断录音。")
                        self.current_asr_engine.stop_connection()
                        self.current_asr_engine = None
                        state = "WAITING"
                        silence_chunks = 0
                        
        except Exception as e:
            print(f"[ASR 后台] 发生异常: {e}")
        finally:
            if self.stream:
                self.stream.stop_stream()
                self.stream.close()
            if self.pyaudio_instance:
                self.pyaudio_instance.terminate()

    def stop_listening(self):
        self.is_listening = False

# ================= 核心接口：供 main.py 调用 =================
def listen_and_recognize():
    """
    主程序获取文字的接口 (带 0.5 秒超时保护的阻塞获取)。
    彻底解决了 while True 导致 CPU 100% 暴走的 Bug。
    """
    get_global_asr_engine() 
    while True:
        try:
            # 阻塞等0.5秒，给了系统喘息的空间，也随时响应队列中的结果
            text = _recognition_results.get(timeout=0.5)
            return text
        except queue.Empty:
            # 没听到字就继续等，这样也允许你用 Ctrl+C 随时中断程序
            continue