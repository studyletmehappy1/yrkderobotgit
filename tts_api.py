#!/usr/bin/env python3
"""
TTS 语音合成模块 (Edge TTS 封装) - 远程测试版
功能：接收文本 -> 异步请求微软接口生成 MP3 -> 保存到本地（不播放）
"""

import asyncio
import os
import tempfile
import threading
import time
import edge_tts
import pygame

# 设定语音角色
# zh-CN-XiaoxiaoNeural: 温暖自然的成熟女声（适合管家）
VOICE = "zh-CN-XiaoxiaoNeural"
# 语速微调
RATE = "+0%"
# 临时音频文件存储路径
OUTPUT_FILE = "temp_reply.mp3"

_playback_lock = threading.Lock()
_stop_event = threading.Event()
_playback_thread = None

async def _generate_audio(text: str, output_file: str):
    """底层异步函数：调用 Edge TTS 接口生成音频文件"""
    communicate = edge_tts.Communicate(text, VOICE, rate=RATE)
    await communicate.save(output_file)


def _play_audio_file(output_file: str):
    """播放本地音频文件，可被 stop 事件中断。"""
    try:
        pygame.mixer.init()
        pygame.mixer.music.load(output_file)
        pygame.mixer.music.play()
        print("[TTS] 🔊 正在播放语音...")
        while pygame.mixer.music.get_busy():
            if _stop_event.is_set():
                pygame.mixer.music.stop()
                break
            time.sleep(0.05)
    except Exception as e:
        print(f"[TTS 报错] 音频播放失败: {e}")
    finally:
        if pygame.mixer.get_init():
            pygame.mixer.quit()
        if os.path.exists(output_file):
            os.remove(output_file)


def _speak_worker(text: str):
    output_file = ""
    try:
        with tempfile.NamedTemporaryFile(delete=False, suffix=".mp3") as temp_audio:
            output_file = temp_audio.name

        print("\n[TTS] 正在请求微软云端合成语音...")
        asyncio.run(_generate_audio(text, output_file))
        print(f"[TTS] ✅ 音频合成成功！文件已保存至: {os.path.abspath(output_file)}")
        _play_audio_file(output_file)
    except Exception as e:
        print(f"[TTS 报错] 语音合成失败: {e}")
        if output_file and os.path.exists(output_file):
            os.remove(output_file)


def speak_async(text: str):
    """异步播放：立即返回，适合在主循环里边播边监听。"""
    global _playback_thread
    if not text or len(text.strip()) == 0:
        return

    with _playback_lock:
        stop_speaking(wait=True)
        _stop_event.clear()
        _playback_thread = threading.Thread(target=_speak_worker, args=(text,), daemon=True)
        _playback_thread.start()


def stop_speaking(wait=False):
    """停止当前播报。"""
    global _playback_thread
    _stop_event.set()
    try:
        if pygame.mixer.get_init():
            pygame.mixer.music.stop()
    except Exception:
        pass

    if wait and _playback_thread and _playback_thread.is_alive():
        _playback_thread.join(timeout=2)


def is_speaking():
    """当前是否处于播报中。"""
    return _playback_thread is not None and _playback_thread.is_alive()

def speak(text: str):
    """
    兼容旧调用：阻塞直到播报结束。
    """
    if not text or len(text.strip()) == 0:
        return
    speak_async(text)
    while is_speaking():
        time.sleep(0.05)

# ========== 独立测试模块 ==========
