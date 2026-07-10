import json
import time

import numpy as np

from edge_ai_system import EdgeAISystem


def run_one_resolution(system, frame_size, n=100):
    h, w = frame_size

    print(f"\n开始测试输入画面分辨率：{w}x{h}，共 {n} 帧")

    latencies = []
    infer_times = []
    fps_list = []

    frames = [
        np.random.randint(0, 255, (h, w, 3), dtype=np.uint8)
        for _ in range(n)
    ]

    start = time.perf_counter()

    for frame in frames:
        result = system.process_one_frame(frame)
        latencies.append(result["latency_ms"])
        infer_times.append(result["infer_ms"])
        fps_list.append(result["fps"])

    end = time.perf_counter()

    summary = {
        "input_resolution": f"{w}x{h}",
        "frames": n,
        "total_time_s": round(end - start, 3),
        "avg_latency_ms": round(float(np.mean(latencies)), 3),
        "avg_infer_ms": round(float(np.mean(infer_times)), 3),
        "p95_latency_ms": round(float(np.percentile(latencies, 95)), 3),
        "avg_fps": round(float(np.mean(fps_list)), 3),
    }

    print(
        f"完成 {w}x{h} | "
        f"平均延迟: {summary['avg_latency_ms']} ms | "
        f"推理耗时: {summary['avg_infer_ms']} ms | "
        f"平均 FPS: {summary['avg_fps']}"
    )

    return summary


def main():
    system = EdgeAISystem(model_path="yolov10n.onnx")

    # 注意：这里测试的是输入画面分辨率，不是 ONNX 模型输入尺寸。
    # 模型内部仍统一使用 edge_ai_system.py 中的 640x640 预处理尺寸。
    resolutions = [
        (320, 320),
        (416, 416),
        (640, 640),
    ]

    results = []

    for frame_size in resolutions:
        summary = run_one_resolution(system, frame_size, n=100)
        results.append(summary)

    with open("resolution_benchmark.json", "w", encoding="utf-8") as f:
        json.dump(results, f, indent=2, ensure_ascii=False)

    print("\n" + "=" * 60)
    print("分辨率权衡测试结果")
    print("=" * 60)
    print("| 输入画面分辨率 | 平均延迟(ms) | 推理耗时(ms) | P95延迟(ms) | 平均FPS |")
    print("|---|---:|---:|---:|---:|")

    for r in results:
        print(
            f"| {r['input_resolution']} | "
            f"{r['avg_latency_ms']} | "
            f"{r['avg_infer_ms']} | "
            f"{r['p95_latency_ms']} | "
            f"{r['avg_fps']} |"
        )

    print("=" * 60)
    print("✅ 分辨率测试结果已保存：resolution_benchmark.json")


if __name__ == "__main__":
    main()