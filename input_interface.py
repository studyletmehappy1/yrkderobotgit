# input_manager.py
import pyaudio
import wave
import base64
import time
import asr_api  # 导入您现有的 ASR 模块

class InputManager:
    """
    统一的用户输入管理器，支持 ASR 模式和 NLU 模式。
    通过修改 self.mode，可以在两种模式之间切换。
    """
    def __init__(self, mode='asr', audio_config=None):
        """
        Args:
            mode (str): 'asr' or 'nlu'.
            audio_config (dict): 录音配置参数。
        """
        self.mode = mode
        self.audio_config = audio_config or {
            "format": pyaudio.paInt16,
            "channels": 1,
            "rate": 16000,
            "chunk": 1024,
        }

    def get_user_input(self):
        """
        统一的获取用户输入的入口。
        Returns:
            str or dict: ASR模式返回文本; NLU模式返回包含音频数据的字典。
        """
        if self.mode == 'asr':
            # 使用现有的 ASR SDK 模块
            print("[InputManager] Using ASR mode...")
            return asr_api.listen_and_recognize()
        
        elif self.mode == 'nlu':
            # NLU 模式：录制完整音频，返回 base64 数据
            print("[InputManager] Using NLU mode...")
            audio_b64 = self._record_full_audio()
            return {
                "type": "audio",
                "data": audio_b64
            }
        else:
            raise ValueError(f"Unsupported mode: {self.mode}")

    def _record_full_audio(self, max_duration=10):
        """
        录制一段完整的音频。在真实场景中，这里可能需要集成本地 VAD
        来自动判断何时停止录音。
        """
        print("[InputManager] Please speak now... (Recording for up to {} seconds)".format(max_duration))
        
        p = pyaudio.PyAudio()
        stream = p.open(
            format=self.audio_config["format"],
            channels=self.audio_config["channels"],
            rate=self.audio_config["rate"],
            input=True,
            frames_per_buffer=self.audio_config["chunk"]
        )

        frames = []
        start_time = time.time()

        while time.time() - start_time < max_duration:
            data = stream.read(self.audio_config["chunk"])
            frames.append(data)

        print("[InputManager] Recording finished.")
        
        stream.stop_stream()
        stream.close()
        p.terminate()

        # 将录制的数据编码为 WAV 格式，再转为 base64
        import io
        wav_buffer = io.BytesIO()
        wf = wave.open(wav_buffer, 'wb')
        wf.setnchannels(self.audio_config["channels"])
        wf.setsampwidth(p.get_sample_size(self.audio_config["format"]))
        wf.setframerate(self.audio_config["rate"])
        wf.writeframes(b''.join(frames))
        wf.close()

        wav_data = wav_buffer.getvalue()
        return base64.b64encode(wav_data).decode('utf-8')

# --- 便捷函数 ---
def get_asr_input():
    manager = InputManager(mode='asr')
    return manager.get_user_input()

def get_nlu_input():
    manager = InputManager(mode='nlu')
    return manager.get_user_input()