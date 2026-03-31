#!/usr/bin/env python3
import asyncio
import os
import edge_tts
import pygame
import time
import shared_state  # 引入全局状态机

VOICE = "zh-CN-XiaoxiaoNeural"
RATE = "+0%"
OUTPUT_FILE = "temp_reply.mp3"

async def _generate_audio(text: str, output_file: str):
    communicate = edge_tts.Communicate(text, VOICE, rate=RATE)
    await communicate.save(output_file)

def speak(text: str):
    if not text or len(text.strip()) == 0:
        return

    print(f"\n[TTS] 正在请求微软云端合成语音...")
    asyncio.run(_generate_audio(text, OUTPUT_FILE))
    print(f"[TTS] ✅ 音频合成成功！")

    try:
        pygame.mixer.init()
        pygame.mixer.music.load(OUTPUT_FILE)
        pygame.mixer.music.play()
        print("[TTS] 🔊 正在播放语音...")
        
        # ⚠️ 核心修改：播放期间循环检测打断标志
        while pygame.mixer.music.get_busy():
            if shared_state.interrupt_flag:
                print("\n[TTS] 🛑 收到 '小艺' 打断信号，嘴巴急刹车！停止播放！")
                pygame.mixer.music.stop()
                break
            time.sleep(0.05) # 每 50 毫秒看一眼红绿灯
            
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