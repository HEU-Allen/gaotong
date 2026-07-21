"""Day 11 - 为采样分析器准备的重复工作负载。"""

from day11_profile import (
    SAMPLE_COUNT,
    WINDOW_SIZE,
    generate_sensor_samples,
    moving_average_fast,
    moving_average_slow,
)


REPEAT_COUNT = 40


def run_workload() -> float:
    """重复执行两种算法，使 pyinstrument 能稳定采集到热点。"""
    samples = generate_sensor_samples(SAMPLE_COUNT)
    checksum = 0.0

    for _ in range(REPEAT_COUNT):
        checksum += moving_average_slow(samples, WINDOW_SIZE)[-1]

    for _ in range(REPEAT_COUNT):
        checksum += moving_average_fast(samples, WINDOW_SIZE)[-1]

    return checksum


if __name__ == "__main__":
    value = run_workload()
    print(f"Repeated workload complete, checksum: {value:.3f}")
