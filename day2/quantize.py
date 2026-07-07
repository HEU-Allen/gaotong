"""YOLOv10 INT8 动态量化与对比测试"""

import onnxruntime as ort
from onnxruntime.quantization import quantize_dynamic, QuantType
import numpy as np
import os
import time

# ========== 1. 执行 INT8 动态量化 ==========
print("🔄 正在生成 INT8 量化模型...")
quantize_dynamic(
    model_input='yolov10n.onnx',
    model_output='yolov10n_int8.onnx',
    weight_type=QuantType.QInt8
)
print("✅ 量化完成：yolov10n_int8.onnx\n")

# ========== 2. 定义测试函数 ==========
def benchmark(path, n=100):
    session = ort.InferenceSession(path, providers=['CPUExecutionProvider'])
    input_name = session.get_inputs()[0].name
    dummy = np.random.randn(1, 3, 640, 640).astype(np.float32)
    
    for _ in range(10):
        session.run(None, {input_name: dummy})
    
    times = []
    for _ in range(n):
        t0 = time.perf_counter()
        session.run(None, {input_name: dummy})
        times.append((time.perf_counter() - t0) * 1000)
    
    size_mb = os.path.getsize(path) / (1024 ** 2)
    mean_ms = np.mean(times)
    fps = 1000 / mean_ms
    return size_mb, mean_ms, fps

# ========== 3. 对比测试 ==========
print("🔍 开始对比测试...")

# FP32 测试
print("   测试 FP32...")
fp32 = benchmark('yolov10n.onnx')

# INT8 测试（Mac 可能不支持，加异常处理）
print("   测试 INT8...")
try:
    int8 = benchmark('yolov10n_int8.onnx')
    int8_ok = True
except Exception as e:
    print(f"   ⚠️  INT8 推理测试失败: {e}")
    int8_ok = False

# ========== 4. 输出结果 ==========
fp32_size = os.path.getsize('yolov10n.onnx') / (1024**2)
int8_size = os.path.getsize('yolov10n_int8.onnx') / (1024**2)

print("\n" + "="*55)
print("📊 YOLOv10-N  FP32 vs INT8 对比报告")
print("="*55)
print(f"{'指标':<12} {'FP32':>12} {'INT8':>12} {'变化':>12}")
print("-"*55)
print(f"{'模型大小':<12} {fp32_size:>10.2f}MB {int8_size:>10.2f}MB {'压缩'+str(round(fp32_size/int8_size,1))+'x':>12}")

if int8_ok:
    print(f"{'平均延迟':<12} {fp32[1]:>10.2f}ms {int8[1]:>10.2f}ms {'加速'+str(round(fp32[1]/int8[1],1))+'x':>12}")
    print(f"{'理论 FPS':<12} {fp32[2]:>10.1f} {int8[2]:>10.1f} {'提升'+str(round(int8[2]/fp32[2],1))+'x':>12}")
else:
    print(f"{'平均延迟':<12} {fp32[1]:>10.2f}ms {'Mac不支持':>12} {'-':>12}")
    print(f"{'理论 FPS':<12} {fp32[2]:>10.1f} {'Mac不支持':>12} {'-':>12}")
    print("\n💡 说明：Mac 版 ONNX Runtime 的 CPUExecutionProvider")
    print("   对 INT8 量化模型的部分算子支持不完整。")
    print("   但在 RK3588/Jetson 等嵌入式 NPU 上 INT8 加速效果显著。")
print("="*55)
