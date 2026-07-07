"""YOLOv10 ONNX Runtime 基准测试（Mac 适配版）"""

import onnxruntime as ort
import numpy as np
import time

# 加载模型
session = ort.InferenceSession('yolov10n.onnx', providers=['CPUExecutionProvider'])
input_name = session.get_inputs()[0].name

# 造一张假图片：1张, 3通道(RGB), 640x640
dummy = np.random.randn(1, 3, 640, 640).astype(np.float32)

# 预热 
print("预热中（10次）...")
for _ in range(10):
    session.run(None, {input_name: dummy})

# 正式计时（100次）
print("正式测试（100次）...")
times = []
for _ in range(100):
    t0 = time.perf_counter()
    session.run(None, {input_name: dummy})
    t1 = time.perf_counter()
    times.append((t1 - t0) * 1000)

# 计算指标 
mean_ms = np.mean(times)
p95_ms = np.percentile(times, 95)
fps = 1000 / mean_ms

# 输出结果
print("\n" + "="*40)
print("YOLOv10-N ONNX Runtime 基准测试")
print("="*40)
print(f"   测试平台 : Mac CPU")
print(f"   测试次数 : 100次")
print(f"   平均延迟 : {mean_ms:.2f} ms")
print(f"   P95 延迟 : {p95_ms:.2f} ms")
print(f"   理论 FPS : {fps:.1f}")
print("="*40)
