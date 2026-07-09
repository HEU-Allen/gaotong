"""多线程实时视频处理框架 (Mac 本地)"""

import cv2
import numpy as np
import threading
import queue
import time
from dataclasses import dataclass
from typing import Optional

# Mac 中文字体修复
import matplotlib.pyplot as plt
plt.rcParams['font.sans-serif'] = ['PingFang SC', 'Heiti SC', 'Arial Unicode MS']
plt.rcParams['axes.unicode_minus'] = False


@dataclass
class Frame:
    frame_id: int
    image: np.ndarray
    timestamp: float
    detections: Optional[list] = None


class AsyncVideoCapture:
    """异步视频捕获：生产者-消费者模式"""
    
    def __init__(self, source=0, buf_size=3):
        self.cap = cv2.VideoCapture(source)
        self.buf = queue.Queue(maxsize=buf_size)
        self.fid = 0
        self.running = False
        self._thread = None
        self.use_fake = False  # 是否使用随机帧回退
        
        if not self.cap.isOpened():
            print(f"⚠️  无法打开视频源: {source}")
            print("   将使用随机帧模拟（无需摄像头）")
            self.use_fake = True
            self.cap = None
        else:
            self.fps = self.cap.get(cv2.CAP_PROP_FPS)
            self.w = int(self.cap.get(cv2.CAP_PROP_FRAME_WIDTH))
            self.h = int(self.cap.get(cv2.CAP_PROP_FRAME_HEIGHT))
            print(f"🎥 视频源已打开: {self.w}x{self.h} @ {self.fps:.1f}FPS")

    def start(self):
        self.running = True
        self._thread = threading.Thread(target=self._loop, daemon=True)
        self._thread.start()
        print("▶️  异步采集线程已启动")

    def _loop(self):
        """生产者线程"""
        while self.running:
            if self.use_fake:
                # 模拟模式：生成随机彩色帧（480x640）
                frame = np.random.randint(0, 255, (480, 640, 3), dtype=np.uint8)
                time.sleep(0.033)  # 模拟 30FPS
            else:
                ret, frame = self.cap.read()
                if not ret:
                    print("⏹️  视频流结束")
                    break
            
            # 帧丢弃策略
            if self.buf.full():
                try:
                    self.buf.get_nowait()
                except queue.Empty:
                    pass
            
            self.buf.put(Frame(self.fid, frame, time.perf_counter()))
            self.fid += 1

    def get(self, timeout=0.1):
        try:
            return self.buf.get(timeout=timeout)
        except queue.Empty:
            return None

    def stop(self):
        self.running = False
        if self._thread:
            self._thread.join(timeout=1.0)
        if self.cap:
            self.cap.release()
        print("⏹️  采集线程已停止")


def main():
    # 0 = 摄像头；或改成视频文件路径
    source = 0
    
    cap = AsyncVideoCapture(source=source, buf_size=3)
    cap.start()
    
    frame_count = 0
    t0 = time.perf_counter()
    
    print("按 Q 退出...")
    
    try:
        while True:
            frame_obj = cap.get(timeout=0.5)
            if frame_obj is None:
                continue
            
            # ---- 模拟处理（下午替换为 YOLOv10 推理）----
            t_proc = time.perf_counter()
            display = frame_obj.image.copy()
            
            cv2.putText(display, f"Frame #{frame_obj.frame_id}", (10, 30),
                       cv2.FONT_HERSHEY_SIMPLEX, 0.8, (0, 255, 0), 2)
            
            e2e_latency = (time.perf_counter() - frame_obj.timestamp) * 1000
            proc_time = (time.perf_counter() - t_proc) * 1000
            
            cv2.putText(display, f"E2E: {e2e_latency:.1f}ms", (10, 60),
                       cv2.FONT_HERSHEY_SIMPLEX, 0.6, (0, 0, 255), 2)
            cv2.putText(display, f"Proc: {proc_time:.1f}ms", (10, 85),
                       cv2.FONT_HERSHEY_SIMPLEX, 0.6, (255, 0, 0), 2)
            
            cv2.imshow("Day 4 - Async Video Capture", display)
            frame_count += 1
            
            if cv2.waitKey(1) & 0xFF == ord('q'):
                break
                
    except KeyboardInterrupt:
        print("\n收到中断信号")
    finally:
        cap.stop()
        cv2.destroyAllWindows()
        
        total_time = time.perf_counter() - t0
        print(f"\n{'='*30}")
        print(f"📊 运行统计")
        print(f"   总帧数: {frame_count}")
        print(f"   总时间: {total_time:.1f}s")
        print(f"   平均FPS: {frame_count/total_time:.1f}" if total_time > 0 else "   N/A")
        print(f"{'='*30}")


if __name__ == "__main__":
    main()