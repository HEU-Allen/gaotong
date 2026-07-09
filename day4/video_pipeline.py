"""YOLOv10 实时检测流水线 (Mac 本地)"""

import cv2
import numpy as np
import onnxruntime as ort
import time
import threading
import queue
from dataclasses import dataclass
from typing import Optional, List, Tuple


# ========== 中文字体配置 ==========
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
    """异步视频捕获（同上午）"""
    
    def __init__(self, source=0, buf_size=3):
        self.cap = cv2.VideoCapture(source)
        self.buf = queue.Queue(maxsize=buf_size)
        self.fid = 0
        self.running = False
        self.use_fake = False
        
        if not self.cap.isOpened():
            print(f"⚠️  无法打开视频源: {source}，使用随机帧模拟")
            self.use_fake = True
            self.cap = None
        else:
            w = int(self.cap.get(cv2.CAP_PROP_FRAME_WIDTH))
            h = int(self.cap.get(cv2.CAP_PROP_FRAME_HEIGHT))
            print(f"🎥 视频源: {w}x{h}")

    def start(self):
        self.running = True
        threading.Thread(target=self._loop, daemon=True).start()
        print("▶️  采集线程已启动")

    def _loop(self):
        while self.running:
            if self.use_fake:
                frame = np.random.randint(0, 255, (480, 640, 3), dtype=np.uint8)
                time.sleep(0.033)
            else:
                ret, frame = self.cap.read()
                if not ret:
                    break
            
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
        if self.cap:
            self.cap.release()


class YOLOv10Detector:
    """YOLOv10-N ONNX 检测器"""
    
    # COCO 80 类名称（部分常用）
    NAMES = {0: 'person', 1: 'bicycle', 2: 'car', 3: 'motorcycle', 4: 'airplane',
             5: 'bus', 6: 'train', 7: 'truck', 8: 'boat', 9: 'traffic light',
             10: 'fire hydrant', 11: 'stop sign', 12: 'parking meter', 13: 'bench',
             14: 'bird', 15: 'cat', 16: 'dog', 17: 'horse', 18: 'sheep', 19: 'cow',
             20: 'elephant', 21: 'bear', 22: 'zebra', 23: 'giraffe', 24: 'backpack',
             25: 'umbrella', 26: 'handbag', 27: 'tie', 28: 'suitcase', 29: 'frisbee',
             30: 'skis', 31: 'snowboard', 32: 'sports ball', 33: 'kite',
             34: 'baseball bat', 35: 'baseball glove', 36: 'skateboard',
             37: 'surfboard', 38: 'tennis racket', 39: 'bottle', 40: 'wine glass',
             41: 'cup', 42: 'fork', 43: 'knife', 44: 'spoon', 45: 'bowl',
             46: 'banana', 47: 'apple', 48: 'sandwich', 49: 'orange',
             50: 'broccoli', 51: 'carrot', 52: 'hot dog', 53: 'pizza', 54: 'donut',
             55: 'cake', 56: 'chair', 57: 'couch', 58: 'potted plant', 59: 'bed',
             60: 'dining table', 61: 'toilet', 62: 'tv', 63: 'laptop', 64: 'mouse',
             65: 'remote', 66: 'keyboard', 67: 'cell phone', 68: 'microwave',
             69: 'oven', 70: 'toaster', 71: 'sink', 72: 'refrigerator', 73: 'book',
             74: 'clock', 75: 'vase', 76: 'scissors', 77: 'teddy bear',
             78: 'hair drier', 79: 'toothbrush'}
    
    def __init__(self, model_path: str, conf: float = 0.25, size: int = 640):
        self.conf = conf
        self.size = size
        self.sess = ort.InferenceSession(model_path, providers=['CPUExecutionProvider'])
        self.iname = self.sess.get_inputs()[0].name
        print(f"✅ 检测器初始化完成: {model_path}")

    def preprocess(self, img: np.ndarray) -> Tuple[np.ndarray, float, int, int]:
        """Letterbox 预处理：保持宽高比缩放 + 灰色填充"""
        h, w = img.shape[:2]
        scale = min(self.size / h, self.size / w)
        nh, nw = int(h * scale), int(w * scale)
        
        resized = cv2.resize(img, (nw, nh), interpolation=cv2.INTER_LINEAR)
        
        # 创建灰色画布 (114, 114, 114)
        pad = np.full((self.size, self.size, 3), 114, dtype=np.uint8)
        ph, pw = (self.size - nh) // 2, (self.size - nw) // 2
        pad[ph:ph + nh, pw:pw + nw] = resized
        
        # 归一化 + CHW + batch
        tensor = pad.astype(np.float32) / 255.0
        tensor = np.transpose(tensor, (2, 0, 1))[np.newaxis, ...]
        return tensor, scale, ph, pw

    def detect(self, img: np.ndarray) -> Tuple[List[dict], float]:
        """推理 + 后处理 + 坐标映射"""
        t0 = time.perf_counter()
        tensor, scale, ph, pw = self.preprocess(img)
        outs = self.sess.run(None, {self.iname: tensor})
        latency = (time.perf_counter() - t0) * 1000
        
        dets = []
        if outs and outs[0] is not None:
            # YOLOv10 无 NMS，输出直接可用
            for box in outs[0][0]:
                if len(box) >= 6 and box[4] >= self.conf:
                    # 坐标映射：从 640x640 还原到原始图像
                    x1 = (box[0] - pw) / scale
                    y1 = (box[1] - ph) / scale
                    x2 = (box[2] - pw) / scale
                    y2 = (box[3] - ph) / scale
                    
                    dets.append({
                        'bbox': [float(x1), float(y1), float(x2), float(y2)],
                        'conf': float(box[4]),
                        'cls': int(box[5])
                    })
        return dets, latency


def draw_detections(img: np.ndarray, dets: List[dict], names: dict) -> np.ndarray:
    """在图像上绘制检测框"""
    colors = [(0, 255, 0), (255, 0, 0), (0, 0, 255), (255, 255, 0),
              (255, 0, 255), (0, 255, 255)]
    
    for det in dets:
        x1, y1, x2, y2 = map(int, det['bbox'])
        cls_id = det['cls']
        conf = det['conf']
        color = colors[cls_id % len(colors)]
        label = names.get(cls_id, f"class_{cls_id}")
        
        cv2.rectangle(img, (x1, y1), (x2, y2), color, 2)
        text = f"{label}: {conf:.2f}"
        (tw, th), _ = cv2.getTextSize(text, cv2.FONT_HERSHEY_SIMPLEX, 0.5, 1)
        cv2.rectangle(img, (x1, y1 - th - 4), (x1 + tw, y1), color, -1)
        cv2.putText(img, text, (x1, y1 - 2), cv2.FONT_HERSHEY_SIMPLEX, 0.5, (0, 0, 0), 1)
    
    return img


def main():
    # ========== 配置 ==========
    source = 0                    # 0=摄像头，或视频文件路径
    model_path = 'yolov10n.onnx'  # 确保这个文件在 week1/ 文件夹里
    conf = 0.25
    buf_size = 3
    
    # ========== 初始化 ==========
    print("=" * 40)
    print("YOLOv10-N 实时检测流水线")
    print("=" * 40)
    
    cap = AsyncVideoCapture(source=source, buf_size=buf_size)
    detector = YOLOv10Detector(model_path=model_path, conf=conf)
    cap.start()
    
    frame_count = 0
    total_infer_time = 0.0
    t0 = time.perf_counter()
    
    print("\n按 Q 退出...")
    
    try:
        while True:
            # ---- 取帧 ----
            frame_obj = cap.get(timeout=0.5)
            if frame_obj is None:
                continue
            
            # ---- 推理 ----
            dets, infer_lat = detector.detect(frame_obj.image)
            total_infer_time += infer_lat
            
            # ---- 画框 ----
            display = frame_obj.image.copy()
            display = draw_detections(display, dets, detector.NAMES)
            
            # ---- 信息叠加 ----
            e2e_lat = (time.perf_counter() - frame_obj.timestamp) * 1000
            avg_infer = total_infer_time / (frame_count + 1)
            
            info_lines = [
                f"Frame: {frame_count}",
                f"Detections: {len(dets)}",
                f"Infer: {infer_lat:.1f}ms",
                f"Avg Infer: {avg_infer:.1f}ms",
                f"E2E: {e2e_lat:.1f}ms",
            ]
            for i, line in enumerate(info_lines):
                cv2.putText(display, line, (10, 30 + i * 25),
                           cv2.FONT_HERSHEY_SIMPLEX, 0.6, (0, 255, 255), 2)
            
            cv2.imshow("Day 4 - YOLOv10 Detection", display)
            frame_count += 1
            
            if cv2.waitKey(1) & 0xFF == ord('q'):
                break
                
    except KeyboardInterrupt:
        print("\n收到中断信号")
    finally:
        cap.stop()
        cv2.destroyAllWindows()
        
        total_time = time.perf_counter() - t0
        print(f"\n{'='*40}")
        print(f"📊 运行统计")
        print(f"   总帧数: {frame_count}")
        print(f"   总时间: {total_time:.1f}s")
        print(f"   平均FPS: {frame_count/total_time:.1f}" if total_time > 0 else "   N/A")
        print(f"   平均推理延迟: {avg_infer:.1f}ms" if frame_count > 0 else "   N/A")
        print(f"{'='*40}")


if __name__ == "__main__":
    main()