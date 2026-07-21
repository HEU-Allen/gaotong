"""Day 11 - Python 性能分析：cProfile 与 timeit。"""

import cProfile
import pstats
import random
import timeit


SAMPLE_COUNT = 80_000
WINDOW_SIZE = 80


def generate_sensor_samples(count: int) -> list[float]:
    """生成可重复的温度传感器样本。"""
    random.seed(11)
    return [25.0 + random.uniform(-2.0, 2.0) for _ in range(count)]


def moving_average_slow(samples: list[float], window: int) -> list[float]:
    """基线实现：每个位置都重新求窗口和，时间复杂度约为 O(n*w)。"""
    result = []
    for index in range(len(samples) - window + 1):
        result.append(sum(samples[index:index + window]) / window)
    return result


def moving_average_fast(samples: list[float], window: int) -> list[float]:
    """优化实现：维护滑动窗口和，时间复杂度约为 O(n)。"""
    result = []
    window_sum = sum(samples[:window])
    result.append(window_sum / window)

    for index in range(window, len(samples)):
        window_sum += samples[index]
        window_sum -= samples[index - window]
        result.append(window_sum / window)
    return result


def profile_function(label: str, function, samples: list[float], stats_file: str) -> None:
    """采集并打印累计耗时最高的函数。"""
    profiler = cProfile.Profile()
    profiler.enable()
    output = function(samples, WINDOW_SIZE)
    profiler.disable()
    profiler.dump_stats(stats_file)

    print(f"\n--- cProfile: {label} ---")
    print(f"Output samples: {len(output)}, last value: {output[-1]:.3f} C")
    print(f"Profile saved: {stats_file}")
    pstats.Stats(profiler).strip_dirs().sort_stats("cumulative").print_stats(12)


def benchmark(label: str, function, samples: list[float]) -> float:
    """用 timeit 多次测试，取平均时间。"""
    timings = timeit.repeat(
        lambda: function(samples, WINDOW_SIZE),
        repeat=3,
        number=1,
    )
    average = sum(timings) / len(timings)
    print(f"{label:<18}: {average * 1000:.2f} ms (3 次平均)")
    return average


def main() -> None:
    samples = generate_sensor_samples(SAMPLE_COUNT)

    print("=== Day 11: Python Performance Profiling ===")
    print(f"Samples: {SAMPLE_COUNT}, moving-average window: {WINDOW_SIZE}")

    profile_function("baseline / slow", moving_average_slow, samples, "day11_slow.prof")
    profile_function("optimized / fast", moving_average_fast, samples, "day11_fast.prof")

    print("\n--- timeit benchmark ---")
    slow_time = benchmark("baseline / slow", moving_average_slow, samples)
    fast_time = benchmark("optimized / fast", moving_average_fast, samples)
    print(f"Speedup: {slow_time / fast_time:.1f}x")


if __name__ == "__main__":
    main()
