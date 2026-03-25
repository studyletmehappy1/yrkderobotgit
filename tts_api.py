#!/usr/bin/env python3
"""
TTS 语音合成模块 (Edge TTS 封装) - 远程测试版
功能：接收文本 -> 异步请求微软接口生成 MP3 -> 保存到本地（不播放）
"""

import asyncio
import os
import edge_tts

# 设定语音角色
# zh-CN-XiaoxiaoNeural: 温暖自然的成熟女声（适合管家）
VOICE = "zh-CN-XiaoxiaoNeural"
# 语速微调
RATE = "+0%"
# 临时音频文件存储路径
OUTPUT_FILE = "temp_reply.mp3"

async def _generate_audio(text: str, output_file: str):
    """底层异步函数：调用 Edge TTS 接口生成音频文件"""
    communicate = edge_tts.Communicate(text, VOICE, rate=RATE)
    await communicate.save(output_file)

def speak(text: str):
    """
    测试版：只生成 MP3，不调用声卡播放
    """
    if not text or len(text.strip()) == 0:
        return

    print(f"\n[TTS] 正在请求微软云端合成语音...")
    
    # 1. 异步转同步：等待音频文件生成落地
    asyncio.run(_generate_audio(text, OUTPUT_FILE))
    
    # 2. 打印绝对路径，方便你通过 SFTP 下载
    abs_path = os.path.abspath(OUTPUT_FILE)
    print(f"[TTS] ✅ 音频合成成功！文件已保存至: {abs_path}")
    print("[TTS] 💡 提示: 请使用 VS Code 侧边栏或 Xshell/MobaXterm 的文件传输功能，将该 .mp3 下载到 Windows 试听。")

    # ==========================================
    # ⚠️ 恢复播放功能
    # ==========================================
    import pygame
    import time
    try:
        pygame.mixer.init()
        pygame.mixer.music.load(OUTPUT_FILE)
        pygame.mixer.music.play()
        print("[TTS] 🔊 正在播放语音...")
        while pygame.mixer.music.get_busy():
            time.sleep(0.1)
    except Exception as e:
        print(f"[TTS 报错] 音频播放失败: {e}")
    finally:
        if pygame.mixer.get_init():
            pygame.mixer.quit()
        if os.path.exists(OUTPUT_FILE):
            os.remove(OUTPUT_FILE)

# ========== 独立测试模块 ==========
