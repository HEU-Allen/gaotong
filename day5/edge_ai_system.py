
"""
Day 5：边缘 AI 视觉检测系统综合项目
功能：YOLOv10 ONNX 推理 + 性能监控 + 结果记录 + 曲线保存
说明：为了保证新手环境稳定，本版本先使用随机图像模拟视频帧，不依赖摄像头权限。
"""

import json
import time
from datetime import datetime

import cv2
import numpy as np
import onnxruntime as ort
import psutil
import matplotlib.pyplot as plt


class PerformanceMonitor:
    """性能监控器：记录 FPS、延迟、CPU、内存"""

    def __init__(self, window=100):
        self.window = window
        self.fps_list = []
        self.lat_list = []
        self.cpu_list = []
        self.mem_list = []
        self.start_time = time.time()

    def update(self, fps, latency_ms):
        self.fps_list.append(fps)
        self.lat_list.append(latency_ms)
        self.cpu_list.append(psutil.cpu_percent())
        self.mem_list.append(psutil.virtual_memory().percent)

        if len(self.fps_list) > self.window:
            self.fps_list.pop(0)
            self.lat_list.pop(0)
            self.cpu_list.pop(0)
            self.mem_list.pop(0)

    def stats(self):
        if not self.fps_list:
            return {}

        return {
            "avg_fps": float(np.mean(self.fps_list)),
            "avg_latency_ms": float(np.mean(self.lat_list)),
            "p95_latency_ms": float(np.percentile(self.lat_list, 95)),
            "avg_cpu_percent": float(np.mean(self.cpu_list)),
            "avg_mem_percent": float(np.mean(self.mem_list)),
            "runtime_s": float(time.time() - self.start_time),
        }

    def save_plot(self, path="perf_monitor.png"):
        if not self.fps_list:
            return

        plt.figure(figsize=(12, 8))

        plt.subplot(2, 2, 1)
        plt.plot(self.fps_list)
        plt.title("FPS")
        plt.xlabel("Frame")
        plt.ylabel("FPS")
        plt.grid(True)

        plt.subplot(2, 2, 2)
        plt.plot(self.lat_list)
        plt.title("Latency")
        plt.xlabel("Frame")
        plt.ylabel("ms")
        plt.grid(True)

        plt.subplot(2, 2, 3)
        plt.plot(self.cpu_list)
        plt.title("CPU Usage")
        plt.xlabel("Frame")
        plt.ylabel("%")
        plt.grid(True)

        plt.subplot(2, 2, 4)
        plt.plot(self.mem_list)
        plt.title("Memory Usage")
        plt.xlabel("Frame")
        plt.ylabel("%")
        plt.grid(True)

        plt.tight_layout()
        plt.savefig(path, dpi=150)
        print(f"✅ 性能曲线已保存：{path}")


class EdgeAISystem:
    """边缘 AI 视觉检测系统"""

    def __init__(self, model_path="yolov10n.onnx", conf=0.25, input_size=640):
        self.model_path = model_path
        self.conf = conf
        self.input_size = input_size
        self.monitor = PerformanceMonitor()
        self.logs = []

        print("🔧 正在加载 ONNX 模型...")
        self.session = ort.InferenceSession(
            model_path,
            providers=["CPUExecutionProvider"]
        )
        self.input_name = self.session.get_inputs()[0].name
        print(f"✅ 模型加载完成：{model_path}")
        print(f"✅ 输入节点名称：{self.input_name}")

    def preprocess(self, frame):
        """Letterbox 预处理：保持比例缩放到 640×640"""
        h, w = frame.shape[:2]
        size = self.input_size

        scale = min(size / h, size / w)
        new_h, new_w = int(h * scale), int(w * scale)

        resized = cv2.resize(frame, (new_w, new_h))
        pad = np.full((size, size, 3), 114, dtype=np.uint8)

        ph = (size - new_h) // 2
        pw = (size - new_w) // 2
        pad[ph:ph + new_h, pw:pw + new_w] = resized

        tensor = pad.astype(np.float32) / 255.0
        tensor = np.transpose(tensor, (2, 0, 1))[np.newaxis, :]

        return tensor

    def count_detections(self, outputs):
        """
        简化版后处理：统计置信度超过阈值的检测数量。
        不同 YOLO 导出格式输出形状可能不同，这里做兼容处理。
        """
        if not outputs:
            return 0

        arr = outputs[0]
        arr = np.array(arr)

        try:
            arr = np.squeeze(arr)

            # 情况1：形状类似 [N, 6]，每行是 x1,y1,x2,y2,conf,cls
            if arr.ndim == 2 and arr.shape[-1] >= 6:
                confs = arr[:, 4]
                return int(np.sum(confs > self.conf))

            # 情况2：形状类似 [84, N]，常见 YOLO 输出格式
            if arr.ndim == 2 and arr.shape[0] < arr.shape[1]:
                arr = arr.T
                if arr.shape[-1] > 5:
                    class_scores = arr[:, 4:]
                    confs = np.max(class_scores, axis=1)
                    return int(np.sum(confs > self.conf))

            return 0

        except Exception:
            return 0

    def process_one_frame(self, frame):
        """处理单帧：预处理 + 推理 + 简化后处理"""
        t0 = time.perf_counter()

        tensor = self.preprocess(frame)

        t1 = time.perf_counter()
        outputs = self.session.run(None, {self.input_name: tensor})
        t2 = time.perf_counter()

        latency_ms = (t2 - t0) * 1000
        infer_ms = (t2 - t1) * 1000
        fps = 1000 / latency_ms if latency_ms > 0 else 0
        n_det = self.count_detections(outputs)

        return {
            "latency_ms": latency_ms,
            "infer_ms": infer_ms,
            "fps": fps,
            "n_det": n_det,
        }

    def run(self, n=200):
        """运行 n 帧测试"""
        print(f"\n🚀 开始运行边缘 AI 综合系统，共处理 {n} 帧")
        print("说明：当前使用随机图像模拟视频帧，目的是稳定验证系统集成逻辑。\n")

        for i in range(n):
            # 模拟一帧 480×640 RGB 图像
            frame = np.random.randint(0, 255, (480, 640, 3), dtype=np.uint8)

            result = self.process_one_frame(frame)
            self.monitor.update(result["fps"], result["latency_ms"])

            log_item = {
                "frame": i + 1,
                "latency_ms": round(result["latency_ms"], 2),
                "infer_ms": round(result["infer_ms"], 2),
                "fps": round(result["fps"], 2),
                "n_det": result["n_det"],
                "time": datetime.now().isoformat(timespec="seconds"),
            }
            self.logs.append(log_item)

            if (i + 1) % 50 == 0:
                s = self.monitor.stats()
                print(
                    f"已处理 {i + 1:>3} 帧 | "
                    f"平均 FPS: {s['avg_fps']:.1f} | "
                    f"平均延迟: {s['avg_latency_ms']:.1f} ms | "
                    f"P95延迟: {s['p95_latency_ms']:.1f} ms"
                )

        summary = self.monitor.stats()

        print("\n" + "=" * 50)
        print("📊 Day 5 边缘 AI 视觉检测系统性能报告")
        print("=" * 50)
        print(f"模型文件       : {self.model_path}")
        print(f"处理帧数       : {n}")
        print(f"平均 FPS       : {summary['avg_fps']:.2f}")
        print(f"平均延迟       : {summary['avg_latency_ms']:.2f} ms")
        print(f"P95 延迟       : {summary['p95_latency_ms']:.2f} ms")
        print(f"平均 CPU 占用  : {summary['avg_cpu_percent']:.2f}%")
        print(f"平均内存占用   : {summary['avg_mem_percent']:.2f}%")
        print(f"运行时间       : {summary['runtime_s']:.2f} s")
        print("=" * 50)

        # 保存结果 JSON
        result_data = {
            "summary": summary,
            "logs_last_20": self.logs[-20:]
        }

        with open("results.json", "w", encoding="utf-8") as f:
            json.dump(result_data, f, indent=2, ensure_ascii=False)

        print("✅ 结果日志已保存：results.json")

        # 保存性能曲线
        self.monitor.save_plot("perf_monitor.png")


if __name__ == "__main__":
    system = EdgeAISystem(model_path="yolov10n.onnx")
    system.run(n=200)
