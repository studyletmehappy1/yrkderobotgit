# shared_state.py
import queue

class RobotState:
    IDLE = "IDLE"           # 待机中：只听“小艺”，忽略其他一切
    LISTENING = "LISTENING" # 倾听中：听到什么都发给大脑
    THINKING = "THINKING"   # 思考中：保护状态，只有听到“小艺”才打断
    SPEAKING = "SPEAKING"   # 说话中：保护状态，只有听到“小艺”才打断

# 全局变量
current_state = RobotState.IDLE 
interrupt_flag = False          # 打断 TTS 播放的急刹车信号
text_queue = queue.Queue()      # 安全的队列，耳朵听到话后塞到这里给大脑