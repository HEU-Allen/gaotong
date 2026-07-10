import cProfile
import pstats
import io
import time

import numpy as np

from edge_ai_system import EdgeAISystem


def run_profile_test():
    system = EdgeAISystem(model_path="yolov10n.onnx")

    n = 100
    frames = [
        np.random.randint(0, 255, (480, 640, 3), dtype=np.uint8)
        for _ in range(n)
    ]

    print(f"\n开始 cProfile 性能分析，共处理 {n} 帧...\n")

    start = time.perf_counter()

    for frame in frames:
        system.process_one_frame(frame)

    end = time.perf_counter()

    total_time = end - start
    avg_time_ms = total_time / n * 1000
    avg_fps = n / total_time

    print("=" * 50)
    print("cProfile 性能分析基础结果")
    print("=" * 50)
    print(f"处理帧数       : {n}")
    print(f"总耗时         : {total_time:.2f} s")
    print(f"平均单帧耗时   : {avg_time_ms:.2f} ms")
    print(f"平均 FPS       : {avg_fps:.2f}")
    print("=" * 50)


if __name__ == "__main__":
    profiler = cProfile.Profile()
    profiler.enable()

    run_profile_test()

    profiler.disable()

    s = io.StringIO()
    stats = pstats.Stats(profiler, stream=s)
    stats.strip_dirs()
    stats.sort_stats("cumulative")
    stats.print_stats(30)

    report = s.getvalue()

    with open("profile_report.txt", "w", encoding="utf-8") as f:
        f.write(report)

    print("\n✅ cProfile 报告已保存：profile_report.txt")
    print("\n下面显示耗时最高的前 30 项：\n")
    print(report)