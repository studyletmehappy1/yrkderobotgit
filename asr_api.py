#!/usr/bin/env python3
"""
ASR 语音识别模块 (耳朵) - 阿里云+VAD状态机版
功能：后台常驻静默监听 -> VAD秒级响应 -> 连线阿里云 -> 唤醒词判定 -> 触发打断
"""

import pyaudio
import threading
import time
import json
import nls
import os
import numpy as np
import torch
import atexit
import shared_state # 引入全局状态机

# ================= 阿里云实时语音识别 SDK 配置 =================
APPKEY = "nmxAhyFvtY4dQHz0"  
TOKEN = "be4f563e545a4017aeca6e23ba68ed09"  

# ================= 录音与 VAD 配置 =================
FORMAT = pyaudio.paInt16
CHANNELS = 1
RATE = 16000
CHUNK = 512

# --- 全局单例 ---
_asr_singleton = None
_asr_lock = threading.Lock()

def start_background_listening():
    """暴露给外部的启动接口 (供 main.py 调用)"""
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
                "❌ 找不到 silero_vad.jit。请下载后放到项目根目录，或传入绝对路径。"
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
    """阿里云连接器"""
    def __init__(self, result_callback):
        self.appkey = APPKEY
        self.token = TOKEN
        self.url = "wss://nls-gateway-cn-shanghai.aliyuncs.com/ws/v1"
        self.result_callback = result_callback
        self.transcriber = None

    def _on_result_changed(self, message, *args):
        # ⚡ 究极优化：在阿里云返回中间结果时就进行实时检测，实现极低延迟打断！
        try:
            data = json.loads(message)
            text = data.get("payload", {}).get("result", "")
            # ✅ 修改点 1：将打断词改为“小艺小艺”
            if "小艺小艺" in text and shared_state.current_state in [shared_state.RobotState.SPEAKING, shared_state.RobotState.THINKING]:
                print("\n[系统] ⚡ (毫秒级响应) 听到唤醒词 '小艺小艺'！紧急刹车！")
                shared_state.interrupt_flag = True
                shared_state.current_state = shared_state.RobotState.LISTENING
        except:
            pass

    def _on_completed(self, message, *args):
        # 完整句子识别结束
        try:
            data = json.loads(message)
            result_text = data.get("payload", {}).get("result", "")
            self.result_callback(result_text)
        except:
            self.result_callback("")

    def _on_error(self, message, *args):
        # 屏蔽无关紧要的网络波动报错，保持清爽
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
            enable_intermediate_result=True,  # 必须设为 True 才能实时打断
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
        if not text.strip(): return

        print(f"\n[ASR 阿里云解析] {text}")

        # ==== 核心：状态机与唤醒词过滤 ====
        if shared_state.current_state in [shared_state.RobotState.SPEAKING, shared_state.RobotState.THINKING, shared_state.RobotState.IDLE]:
            # ✅ 修改点 2：将唤醒词改为“小艺小艺”
            if "小艺小艺" in text:
                # 状态切换与打断标记 (如果在 _on_result_changed 里没触发，这里兜底)
                if not shared_state.interrupt_flag:
                    print(f"\n[系统] ⚡ 听到唤醒词 '小艺小艺'！强行打断！")
                    shared_state.interrupt_flag = True
                    shared_state.current_state = shared_state.RobotState.LISTENING
                
                # ✅ 修改点 3：裁剪文本时，把“小艺小艺”剔除掉，避免传给大模型变成复读机
                command = text.replace("小艺小艺", "").replace("，", "").replace("。", "").strip()
                if command:
                    shared_state.text_queue.put(command)
            else:
                # 没听到小艺小艺，当作没听见（过滤掉环境音和机器人自己的声音）
                pass 

        elif shared_state.current_state == shared_state.RobotState.LISTENING:
            print(f"[系统] ✅ 接收到有效指令，提交给大脑...")
            shared_state.text_queue.put(text)
            # 收音完毕，进入思考保护状态
            shared_state.current_state = shared_state.RobotState.THINKING

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
        max_silence_chunks = 10 

        try:
            while self.is_listening:
                audio_data = self.stream.read(CHUNK, exception_on_overflow=False)
                has_speech = self.vad_detector.is_speech(audio_data)

                if state == "WAITING":
                    if has_speech:
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

                    if silence_chunks > max_silence_chunks:
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