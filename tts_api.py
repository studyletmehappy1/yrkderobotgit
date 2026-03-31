#!/usr/bin/env python3
"""
TTS 语音合成模块 (Edge TTS 封装)
功能：生成 MP3 -> 调用 pygame 播放 -> 支持被 VAD 瞬间打断
"""

import asyncio
import os
import warnings
import edge_tts

os.environ.setdefault("PYGAME_HIDE_SUPPORT_PROMPT", "1")
warnings.filterwarnings(
    "ignore",
    message="pkg_resources is deprecated as an API",
    category=UserWarning,
)

import pygame
import time

VOICE = "zh-CN-XiaoxiaoNeural"
RATE = "+0%"
OUTPUT_FILE = "temp_reply.mp3"

async def _generate_audio(text: str, output_file: str):
    """底层异步函数：调用 Edge TTS 接口生成音频文件"""
    communicate = edge_tts.Communicate(text, VOICE, rate=RATE)
    await communicate.save(output_file)

def speak(text: str, interrupt_flag=None):
    """
    增加 interrupt_flag 参数，用于接收打断信号
    """
    if not text or len(text.strip()) == 0:
        return

    print(f"\n[TTS] 正在请求微软云端合成语音...")
    
    # 异步转同步：等待音频文件生成落地
    asyncio.run(_generate_audio(text, OUTPUT_FILE))

    try:
        pygame.mixer.init()
        pygame.mixer.music.load(OUTPUT_FILE)
        pygame.mixer.music.play()
        print("[TTS] 🔊 开始播放 (随时可被打断)...")
        
        # 动态检查播放状态
        while pygame.mixer.music.get_busy():
            # 【究极核心】：如果外面拉响了打断警报，瞬间闭嘴！
            if interrupt_flag and interrupt_flag.is_set():
                print("\n[嘴巴] 收到打断信号，瞬间闭嘴 ！！！")
                pygame.mixer.music.stop()
                break # 瞬间跳出循环，播放停止
                
            time.sleep(0.05) # 极高频 (50毫秒) 检查一次警报
            
    except Exception as e:
        print(f"[TTS 报错] 音频播放失败: {e}")
    finally:
        if pygame.mixer.get_init():
            pygame.mixer.quit()
        if os.path.exists(OUTPUT_FILE):
            try:
                os.remove(OUTPUT_FILE)
            except:
                pass